"""Platform-agnostic decision loop.

``reconcile`` is the whole brain of the service and is deliberately free
of any Docker or HTTP detail -- it drives a :class:`ReloadDriver` and an
:class:`SsmClient`. It is pure orchestration so it can be unit-tested with
fakes and reused verbatim by a future Kubernetes driver.

Guarantees:

* **Dedup:** units are grouped by ``(project, config)`` so N containers on
  one config cause exactly ONE conditional export.
* **Fail-safe:** any SSM/network error while exporting a config skips that
  config and mutates nothing -- a healthy container is never torn down
  because the API was briefly unreachable. A ``403`` is logged and skipped
  (never "fail open").
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ssm_reload.errors import SsmClientError, SsmReloadError
from ssm_reload.models import Binding, Unit

if TYPE_CHECKING:
    from ssm_reload.client import SsmClient
    from ssm_reload.driver import ReloadDriver

logger = logging.getLogger("ssm_reload.reconcile")

Group = list[tuple[Unit, Binding]]


def reconcile(driver: "ReloadDriver", client: "SsmClient", host: str) -> None:
    """Run one reconciliation pass over all managed units."""
    groups = _group_by_config(driver)
    for (project, config), members in groups.items():
        _process_group(driver, client, host, project, config, members)


def _group_by_config(
    driver: "ReloadDriver",
) -> dict[tuple[str, str], Group]:
    """Discover units and bucket them by ``(project, config)``."""
    groups: dict[tuple[str, str], Group] = {}
    for unit in driver.discover():
        try:
            binding = driver.read_binding(unit)
        except SsmReloadError as exc:
            logger.warning("Skipping %s: %s", unit.name, exc)
            continue
        key = (binding.project, binding.config)
        groups.setdefault(key, []).append((unit, binding))
    return groups


def _process_group(
    driver: "ReloadDriver",
    client: "SsmClient",
    host: str,
    project: str,
    config: str,
    members: Group,
) -> None:
    """Export one config once, then recreate every divergent unit."""
    held = _shared_revision(members)
    try:
        changed, secrets, new_etag = client.conditional_export(
            project, config, held
        )
    except SsmClientError as exc:
        _log_export_failure(project, config, exc)
        return  # FAIL-SAFE: mutate nothing on any SSM/network error.

    if not changed:
        return  # 304: every unit is already current.
    if secrets is None or new_etag is None:
        logger.warning(
            "%s/%s changed but response lacked secrets/ETag; skipping",
            project,
            config,
        )
        return

    for unit, binding in members:
        if binding.held_revision == new_etag:
            continue  # Already at the fresh revision.
        _apply_and_report(
            driver,
            client,
            host,
            project,
            config,
            unit,
            binding,
            secrets,
            new_etag,
        )


def _apply_and_report(
    driver: "ReloadDriver",
    client: "SsmClient",
    host: str,
    project: str,
    config: str,
    unit: Unit,
    binding: Binding,
    secrets: dict[str, str],
    new_etag: str,
) -> None:
    try:
        driver.apply(unit, secrets, new_etag)
    except SsmReloadError as exc:
        logger.error("Failed to recreate %s: %s", unit.name, exc)
        return

    logger.info(
        "Recreated %s (%s/%s) %s -> %s",
        unit.name,
        project,
        config,
        binding.held_revision,
        new_etag,
    )
    try:
        client.report_reload(
            {
                "project": project,
                "config": config,
                "container": unit.name,
                "host": host,
                "from_revision": binding.held_revision,
                "to_revision": new_etag,
            }
        )
    except SsmReloadError as exc:
        # The reload already happened; reporting is best-effort.
        logger.warning("Reload report failed for %s: %s", unit.name, exc)


def _shared_revision(members: Group) -> str | None:
    """Return the common held revision, or ``None`` if units disagree.

    When every unit on a config holds the same non-null revision we can
    send it as ``If-None-Match`` and enjoy a cheap ``304`` fast-path. When
    revisions differ (or some are missing), we fall back to an
    unconditional export and later apply only to the units that diverge.
    """
    revisions = {binding.held_revision for _unit, binding in members}
    if len(revisions) == 1:
        return next(iter(revisions))
    return None


def _log_export_failure(
    project: str, config: str, exc: SsmClientError
) -> None:
    if exc.status_code == 403:
        logger.warning(
            "Token cannot authorize %s/%s (403); skipping",
            project,
            config,
        )
    else:
        logger.warning(
            "Export failed for %s/%s: %s; leaving containers untouched",
            project,
            config,
            exc,
        )
