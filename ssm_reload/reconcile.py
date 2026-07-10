"""Platform-agnostic decision loop.

:class:`Reconciler` is the whole brain of the service and is deliberately
free of any Docker or HTTP detail -- it drives a :class:`ReloadDriver`, an
:class:`SsmClient` and a :class:`Projector`, all injected. It is pure
orchestration, so it can be unit-tested with fakes and reused verbatim by a
future Kubernetes driver.

Guarantees:

* **Dedup:** units are grouped by :class:`ConfigRef` so N containers on one
  config cause exactly ONE conditional export.
* **Deliver first, converge second:** a changed config is PROJECTED (written
  to its dotenv sink) before any container is touched. Delivery is what lets
  the next container be *born* with the right secrets; convergence only
  exists for the ones already running.
* **SSM never takes a container away from its owner.** A container another
  tool created, one still settling from a deploy in flight, or one whose
  network namespace another owner's container lives inside, is REPORTED as
  divergent and left alone.
* **Fail-safe:** any SSM/network error while exporting a config skips that
  config and mutates nothing -- a healthy container is never torn down
  because the API was briefly unreachable. A ``403`` is logged and skipped
  (never "fail open"). On any ambiguity, report and act on nothing.
* **Transparent:** EVERY pass emits one status report per config group --
  including the steady-state 304 path -- so the server's fleet view reflects
  every poll, not only the cycles that recreated something. Human-readable
  logging and OTel events sit side by side at each decision point.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar, Iterator, Literal

import ssm_telemetry
from ssm_contracts import (
    GroupOutcome,
    ReloadReport,
    Reporter,
    Trigger,
    UnitOutcome,
    UnitStatus,
)
from ssm_reload import __version__
from ssm_reload.errors import SsmClientError, SsmReloadError
from ssm_reload.models import Binding, ConfigRef, Unit
from ssm_reload.projection import Projector

if TYPE_CHECKING:
    from ssm_reload.client import SsmClient
    from ssm_reload.driver import ReloadDriver

logger = logging.getLogger("ssm_reload.reconcile")

Member = tuple[Unit, Binding]
# What the conditional export did this cycle: served a fresh body, confirmed
# the held revision, or failed.
ExportOutcome = Literal["200", "304", "error"]


@dataclass(frozen=True)
class Decision:
    """What may be done to one unit, and why.

    Built through the named constructors below rather than by hand: every
    caller then states its intent, and no caller has to re-derive meaning from
    a message string.
    """

    outcome: UnitOutcome
    should_recreate: bool = False
    adopted: bool = False
    # True when only ANOTHER owner can resolve this divergence (they must
    # redeploy). A settling container is NOT this: it resolves itself on the
    # next pass, so it must not paint the fleet view red.
    needs_owner: bool = False
    reason: str | None = None

    @classmethod
    def current(cls) -> "Decision":
        """Already holds this revision."""
        return cls(outcome="current")

    @classmethod
    def adopt(cls) -> "Decision":
        """Born correct (or made correct by its owner): keep it running."""
        return cls(outcome="current", adopted=True)

    @classmethod
    def wait(cls, reason: str) -> "Decision":
        """Transiently untouchable; the next pass will see it settled."""
        return cls(outcome="skipped", reason=reason)

    @classmethod
    def defer_to_owner(cls, reason: str) -> "Decision":
        """Divergent, and only its owner can fix it. Report, touch nothing."""
        return cls(outcome="skipped", needs_owner=True, reason=reason)

    @classmethod
    def recreate(cls) -> "Decision":
        """SSM is this unit's only owner: recreate it with fresh secrets."""
        return cls(outcome="recreated", should_recreate=True)


class AdoptionCache:
    """Process-local memory of adopted units' revisions.

    An externally-recreated container keeps its operator-set binding labels
    but loses the reloader-stamped revision label (labels are immutable, so
    only a recreate can stamp one). When such a unit's actual env already
    matches the config's current export, the reconciler ADOPTS it instead of
    recreating; this cache remembers the adopted revision keyed by unit id
    so later passes regain the ``If-None-Match``/304 fast path. It is
    process-local by design -- the no-durable-state doctrine holds, and a
    reloader restart merely re-adopts once. Unit ids are immutable, so any
    recreate (which mints a new id) self-invalidates its entry.
    """

    def __init__(self) -> None:
        self._revisions: dict[str, str] = {}

    def get(self, unit_id: str) -> str | None:
        return self._revisions.get(unit_id)

    def remember(self, unit_id: str, revision: str) -> None:
        self._revisions[unit_id] = revision

    def prune(self, live_ids: set[str]) -> None:
        """Drop entries for units no longer discovered."""
        self._revisions = {
            uid: rev for uid, rev in self._revisions.items() if uid in live_ids
        }


@dataclass
class ConfigGroup:
    """Every unit bound to one config, and what they collectively hold.

    Grouping is what makes N containers on one config cost ONE export. A group
    with no members is legitimate: a config listed for projection before
    anything is bound to it yet (an `env_file` must exist before the first
    `compose up` that names it).
    """

    ref: ConfigRef
    members: list[Member] = field(default_factory=list)

    def add(self, unit: Unit, binding: Binding) -> None:
        self.members.append((unit, binding))

    def __iter__(self) -> Iterator[Member]:
        return iter(self.members)

    def unit_ids(self) -> set[str]:
        return {unit.id for unit, _ in self.members}

    def resolve_adoptions(self, adoptions: AdoptionCache) -> None:
        """Fill stripped revision labels from the adoption cache.

        A previously-adopted unit still has no revision label (labels are
        immutable), so its remembered revision substitutes for the label --
        restoring the shared-revision/304 fast path for the whole group.
        """
        self.members = [
            (unit, self._remembered(unit, binding, adoptions))
            for unit, binding in self.members
        ]

    def shared_revision(self) -> str | None:
        """The revision every member holds, or None if they disagree.

        When all units agree we can send it as ``If-None-Match`` and enjoy a
        cheap ``304``. When they differ (or any is missing), fall back to an
        unconditional export and apply only to the units that diverge.
        """
        revisions = {binding.held_revision for _unit, binding in self.members}
        if len(revisions) == 1:
            return next(iter(revisions))
        return None

    @staticmethod
    def _remembered(
        unit: Unit, binding: Binding, adoptions: AdoptionCache
    ) -> Binding:
        if binding.held_revision is not None:
            return binding
        adopted = adoptions.get(unit.id)
        if adopted is None:
            return binding
        return Binding(
            project=binding.project,
            config=binding.config,
            held_revision=adopted,
        )


@dataclass
class GroupTally:
    """Per-unit outcomes accumulated while converging one config group."""

    units: list[UnitStatus] = field(default_factory=list)
    recreated: int = 0
    failed: int = 0
    # Delivery failed for this config (a read-only mount, an unrenderable
    # key). Set even when no container needed anything, because a config
    # nothing is bound to yet has no unit outcome that could go red.
    projection_error: str | None = None
    # The first divergence only ANOTHER owner can resolve. Captured here,
    # where the decision's flag is still in hand -- deriving it later by
    # scanning for a "skipped" unit would also match a transiently settling
    # one, and report "created 3s ago" as the thing a human must act on.
    owner_error: str | None = None

    def record(
        self,
        unit: Unit,
        binding: Binding,
        outcome: UnitOutcome,
        error: str | None = None,
    ) -> None:
        self.units.append(
            UnitStatus(
                id=unit.id,
                name=unit.name,
                held_revision=binding.held_revision,
                outcome=outcome,
                error=error,
            )
        )
        if outcome == "recreated":
            self.recreated += 1
        elif outcome == "failed":
            self.failed += 1

    def record_decision(
        self, unit: Unit, binding: Binding, decision: Decision
    ) -> None:
        self.record(unit, binding, decision.outcome, decision.reason)
        if decision.needs_owner and self.owner_error is None:
            self.owner_error = f"{unit.name}: {decision.reason}"

    def outcome(self) -> GroupOutcome:
        # Delivery failing outranks everything: the file IS the mechanism now,
        # and a container born from a stale (or absent) one is broken however
        # the recreates went.
        if self.projection_error:
            return "error"
        # A successful recreate makes the group "updated" -- the server keys
        # `revisionUpdatedAt` off that, so it must mean a real reload.
        # Otherwise a failure OR an un-actioned divergence needs attention.
        if self.recreated:
            return "updated"
        if self.failed or self.owner_error:
            return "error"
        return "current"

    def error(self) -> str | None:
        """The one thing a human has to act on, most urgent first."""
        return self.projection_error or self.owner_error


class Reconciler:
    """Runs reconciliation passes over every managed unit."""

    # How long a freshly-created container is left alone. Fixed, not a knob:
    # it exists to keep SSM out of another tool's in-flight deploy, and a
    # fleet whose operators can tune it per host is a fleet that disagrees
    # with itself about when a deploy is finished.
    SETTLE_SECONDS: ClassVar[float] = 20.0

    def __init__(
        self,
        driver: "ReloadDriver",
        client: "SsmClient",
        host: str,
        projector: Projector,
        *,
        bootstrap_configs: tuple[ConfigRef, ...] = (),
        adoptions: AdoptionCache | None = None,
    ) -> None:
        self.driver = driver
        self.client = client
        self.host = host
        self.projector = projector
        # Configs to project even when no container is bound to them yet.
        self.bootstrap_configs = bootstrap_configs
        self.adoptions = adoptions or AdoptionCache()

    def run(self, trigger: Trigger = "poll") -> None:
        """Run one reconciliation pass over all managed units."""
        ssm_telemetry.emit_event(
            "ssm_reload.cycle.started", attributes={"ssm.trigger": trigger}
        )
        groups = self._discover_groups()
        self.adoptions.prune(
            {uid for group in groups.values() for uid in group.unit_ids()}
        )
        for group in groups.values():
            # Config groups are independent: one group's unexpected failure
            # must never starve the others of exports/recreates/reports.
            try:
                report = self._process_group(group, trigger)
            except Exception:
                logger.exception(
                    "Reconcile failed for %s; continuing with the "
                    "remaining config groups",
                    group.ref,
                )
                continue
            self._send_report(report)
        ssm_telemetry.emit_event(
            "ssm_reload.cycle.completed", attributes={"ssm.trigger": trigger}
        )

    # --- discovery -----------------------------------------------------

    def _discover_groups(self) -> dict[ConfigRef, ConfigGroup]:
        """Bucket every discovered unit by the config it tracks.

        A unit with a missing/malformed binding has no config to attribute a
        report to, so it is surfaced on the telemetry channel (and the log)
        and dropped from this pass rather than forced into a group. Configs
        listed for bootstrap join as empty groups: they are exported and
        projected, and converge nothing.
        """
        groups: dict[ConfigRef, ConfigGroup] = {
            ref: ConfigGroup(ref) for ref in self.bootstrap_configs
        }
        for unit in self.driver.discover():
            try:
                binding = self.driver.read_binding(unit)
            except SsmReloadError as exc:
                logger.warning("Skipping %s: %s", unit.name, exc)
                ssm_telemetry.emit_event(
                    "ssm_reload.binding.invalid",
                    severity=ssm_telemetry.WARN,
                    attributes={
                        "container.id": unit.id,
                        "container.name": unit.name,
                        "error": str(exc),
                    },
                )
                continue
            ref = ConfigRef(binding.project, binding.config)
            groups.setdefault(ref, ConfigGroup(ref)).add(unit, binding)
        return groups

    # --- one config group ----------------------------------------------

    def _process_group(
        self, group: ConfigGroup, trigger: Trigger
    ) -> ReloadReport:
        """Export one config once, project it, converge the divergent units.

        Returns a :class:`ReloadReport` every cycle -- the 304 steady-state
        path returns one with ``outcome="current"`` and every unit listed,
        which is the whole point of the transparency feature.
        """
        group.resolve_adoptions(self.adoptions)
        held = self._held_revision(group)
        try:
            changed, secrets, new_etag = self.client.conditional_export(
                group.ref.project, group.ref.config, held
            )
        except SsmClientError as exc:
            self._log_export_failure(group.ref, exc)
            self._emit_export_decision(group.ref, "error")
            # FAIL-SAFE: mutate nothing. Units are reported "skipped".
            return self._report(
                group,
                trigger,
                revision=None,
                outcome="error",
                error=exc.message,
                units=self._all_units(group, "skipped"),
            )

        if not changed:
            self._emit_export_decision(group.ref, "304")
            return self._report(
                group,
                trigger,
                revision=held,
                outcome="current",
                error=None,
                units=self._all_units(group, "current"),
            )

        if secrets is None or new_etag is None:
            logger.warning(
                "%s changed but response lacked secrets/ETag; skipping",
                group.ref,
            )
            self._emit_export_decision(group.ref, "error")
            return self._report(
                group,
                trigger,
                revision=None,
                outcome="error",
                error="changed but response lacked secrets/ETag",
                units=self._all_units(group, "skipped"),
            )

        self._emit_export_decision(group.ref, "200")
        # DELIVERY BEFORE CONVERGENCE: write the file first, so an owner who
        # redeploys reads the current secrets even if we then decline to touch
        # their container. A failure here is reported, not raised -- the
        # containers that still need a recreate must not be held hostage to it.
        projection_error = self.projector.render(group.ref, secrets, new_etag)

        tally = self._converge(group, secrets, new_etag)
        tally.projection_error = projection_error
        return self._report(
            group,
            trigger,
            revision=new_etag,
            outcome=tally.outcome(),
            error=tally.error(),
            units=tally.units,
        )

    def _converge(
        self, group: ConfigGroup, secrets: dict[str, str], new_etag: str
    ) -> GroupTally:
        tally = GroupTally()
        for unit, binding in group:
            decision = self._decide(unit, binding, secrets, new_etag)
            if not decision.should_recreate:
                if decision.adopted:
                    # The one state change a non-recreate produces, made HERE
                    # rather than inside the guard chain: _decide answers a
                    # question, it does not change the world.
                    self.adoptions.remember(unit.id, new_etag)
                self._log_untouched(unit, group.ref, decision)
                tally.record_decision(unit, binding, decision)
                continue
            outcome, error = self._apply(
                group.ref, unit, binding, secrets, new_etag
            )
            tally.record(unit, binding, outcome, error)
        return tally

    def _decide(
        self,
        unit: Unit,
        binding: Binding,
        secrets: dict[str, str],
        new_etag: str,
    ) -> Decision:
        """Decide what may be done to one unit. The guard order IS the safety
        argument:

        1. Already at this revision -> nothing to do.
        2. Its env already matches -> ADOPT (no restart). A container born
           from the projected ``env_file`` lands here, which is why the steady
           state of this design touches nothing.
        3. Still settling -> somebody is mid-deploy. Leave it.
        4. Another tool owns it -> report, never recreate.
        5. Another owner's container lives in its network namespace ->
           recreating it would strand them; refuse and say which.
        6. Otherwise SSM is its only owner: recreate.
        """
        if binding.held_revision == new_etag:
            return Decision.current()

        if self._env_current(unit, secrets):
            return Decision.adopt()

        settling = unit.lifecycle.settling_reason(self.SETTLE_SECONDS)
        if settling is not None:
            return Decision.wait(settling)

        owner = unit.lifecycle.owner
        if owner:
            return Decision.defer_to_owner(
                f"owned by {owner}: SSM does not recreate a container it did "
                f"not create. Its env_file is projected at {new_etag} -- "
                "redeploy it (docker compose up -d) to pick up the new "
                "secrets."
            )

        stranded = unit.lifecycle.stranded_by_recreate()
        if stranded:
            return Decision.defer_to_owner(
                f"recreating this container would strand {', '.join(stranded)}"
                ", which share its network namespace and belong to another "
                "owner; redeploy that stack instead."
            )

        return Decision.recreate()

    def _apply(
        self,
        ref: ConfigRef,
        unit: Unit,
        binding: Binding,
        secrets: dict[str, str],
        new_etag: str,
    ) -> tuple[UnitOutcome, str | None]:
        """Recreate one unit; return its outcome and any error string."""
        self._emit_recreate(
            "ssm_reload.recreate.started", unit, ref, binding, new_etag
        )
        try:
            self.driver.apply(unit, secrets, new_etag)
        except SsmReloadError as exc:
            logger.error("Failed to recreate %s: %s", unit.name, exc)
            ssm_telemetry.emit_event(
                "ssm_reload.recreate.rolled_back",
                severity=ssm_telemetry.ERROR,
                attributes={
                    "container.id": unit.id,
                    "container.name": unit.name,
                    "ssm.project": ref.project,
                    "ssm.config": ref.config,
                    "error": str(exc),
                },
            )
            return ("failed", str(exc))

        logger.info(
            "Recreated %s (%s) %s -> %s",
            unit.name,
            ref,
            binding.held_revision,
            new_etag,
        )
        self._emit_recreate(
            "ssm_reload.recreate.succeeded", unit, ref, binding, new_etag
        )
        # The per-recreate audit event is a separate, established call.
        try:
            self.client.report_reload(
                {
                    "project": ref.project,
                    "config": ref.config,
                    "container": unit.name,
                    "host": self.host,
                    "from_revision": binding.held_revision,
                    "to_revision": new_etag,
                }
            )
        except SsmReloadError as exc:
            # The reload already happened; reporting is best-effort.
            logger.warning("Reload report failed for %s: %s", unit.name, exc)
        return ("recreated", None)

    # --- revision bookkeeping ------------------------------------------

    def _held_revision(self, group: ConfigGroup) -> str | None:
        """The revision to send as ``If-None-Match``, or None to force a 200.

        A missing projection file forces an unconditional export even when
        every container agrees on its revision: the RAM-backed volume is empty
        after a reboot, and a 304 would leave it that way forever.
        """
        if self.projector.needs_render(group.ref):
            return None
        if not group.members:
            # A bootstrap config has no container to read a revision from; the
            # projector's own memory restores the 304 fast path.
            return self.projector.last_revision(group.ref)
        return group.shared_revision()

    def _env_current(self, unit: Unit, secrets: dict[str, str]) -> bool:
        """True when the unit's actual env already carries this config.

        Two questions, because a subset check alone is not enough:

        * does every exported key hold the exported value? (app-native env
          alongside them never blocks -- that is the whole reason a recreate
          must merge rather than replace); and
        * is any key SSM injected on a previous recreate, but which the config
          no longer carries, still lingering? The ``<prefix>.keys`` label is
          the only thing that makes that visible.

        Any read failure means "cannot verify", so the caller recreates with
        known-good secrets -- fail safe, never fail open.
        """
        try:
            env = self.driver.read_env(unit)
            managed = self.driver.read_managed_keys(unit)
        except Exception as exc:
            logger.warning(
                "Could not read env of %s (%s); recreating instead of "
                "adopting",
                unit.name,
                exc,
            )
            return False
        if any(key in env for key in managed - set(secrets)):
            return False
        return all(env.get(key) == value for key, value in secrets.items())

    # --- reporting -------------------------------------------------------

    def _all_units(
        self, group: ConfigGroup, outcome: UnitOutcome
    ) -> list[UnitStatus]:
        tally = GroupTally()
        for unit, binding in group:
            tally.record(unit, binding, outcome)
        return tally.units

    def _report(
        self,
        group: ConfigGroup,
        trigger: Trigger,
        *,
        revision: str | None,
        outcome: GroupOutcome,
        error: str | None,
        units: list[UnitStatus],
    ) -> ReloadReport:
        return ReloadReport(
            project=group.ref.project,
            config=group.ref.config,
            reporter=Reporter(
                host=self.host,
                instance_id=ssm_telemetry.instance_id(),
                version=__version__,
            ),
            trigger=trigger,
            revision=revision,
            outcome=outcome,
            error=error,
            units=units,
        )

    def _send_report(self, report: ReloadReport) -> None:
        """POST one per-group status report.

        Best-effort: a failed heartbeat never breaks the pass.
        """
        try:
            self.client.report_status(report.model_dump(by_alias=True))
            ssm_telemetry.emit_event(
                "ssm_reload.report.sent",
                attributes={
                    "ssm.project": report.project,
                    "ssm.config": report.config,
                    "ssm.outcome": report.outcome,
                    "ssm.trigger": report.trigger,
                },
            )
        except SsmReloadError as exc:
            logger.warning(
                "Status report failed for %s/%s: %s",
                report.project,
                report.config,
                exc,
            )

    def _log_untouched(
        self, unit: Unit, ref: ConfigRef, decision: Decision
    ) -> None:
        if decision.adopted:
            logger.info(
                "Adopted %s (%s) -- env already current, no restart needed",
                unit.name,
                ref,
            )
            ssm_telemetry.emit_event(
                "ssm_reload.unit.adopted",
                attributes={
                    "container.id": unit.id,
                    "container.name": unit.name,
                    "ssm.project": ref.project,
                    "ssm.config": ref.config,
                },
            )
            return
        if decision.reason is None:
            return

        logger.warning(
            "Not touching %s (%s): %s", unit.name, ref, decision.reason
        )
        ssm_telemetry.emit_event(
            "ssm_reload.unit.diverged",
            severity=ssm_telemetry.WARN,
            attributes={
                "container.id": unit.id,
                "container.name": unit.name,
                "ssm.project": ref.project,
                "ssm.config": ref.config,
                "ssm.owner": unit.lifecycle.owner or "",
                "reason": decision.reason,
            },
        )

    def _log_export_failure(self, ref: ConfigRef, exc: SsmClientError) -> None:
        if exc.status_code == 403:
            logger.warning("Token cannot authorize %s (403); skipping", ref)
        else:
            logger.warning(
                "Export failed for %s: %s; leaving containers untouched",
                ref,
                exc,
            )

    def _emit_export_decision(
        self, ref: ConfigRef, outcome: ExportOutcome
    ) -> None:
        ssm_telemetry.emit_event(
            "ssm_reload.export.decision",
            severity=(
                ssm_telemetry.ERROR
                if outcome == "error"
                else ssm_telemetry.INFO
            ),
            attributes={
                "ssm.project": ref.project,
                "ssm.config": ref.config,
                "ssm.outcome": outcome,
            },
        )

    def _emit_recreate(
        self,
        event: str,
        unit: Unit,
        ref: ConfigRef,
        binding: Binding,
        new_etag: str,
    ) -> None:
        ssm_telemetry.emit_event(
            event,
            attributes={
                "container.id": unit.id,
                "container.name": unit.name,
                "ssm.project": ref.project,
                "ssm.config": ref.config,
                "ssm.revision.from": binding.held_revision or "",
                "ssm.revision.to": new_etag,
            },
        )
