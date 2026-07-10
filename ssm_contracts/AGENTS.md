# ssm_contracts — Agent Guide

> Nearest-scope guide for `ssm_contracts/`. Read the [root `AGENTS.md`](../AGENTS.md)
> first for cross-cutting principles and the memory protocol. This file
> captures only what is **not obvious from the code** in this scope.
> `CLAUDE.md` here is a symlink to this file — edit this one.

## Responsibility

Typed cross-service contracts — the single source of truth for wire formats
shared across the HTTP boundary. Today: the reload report/status models
(`reload.py`) used by both `ssm_server` and `ssm_reload`.

| Module | Answers |
| --- | --- |
| `reload.py` | The `POST /reload/report` body (`ReloadReport` + nested `Reporter`/`UnitStatus`) and the `GET /reload/status` response models (`ReloadConfigStatus`/`ReloadInstanceStatus`/`ReloadUnitStatus`), plus `summarize_validation_error`. |
| `__init__.py` | Re-exports the public model + type-alias surface. |

## Non-obvious decisions

- **This is a LEAF.** It depends only on `pydantic` and imports NO other
  project package — import-linter enforces it (`ssm_contracts is a leaf`).
  Both the server and the reloader may import it; it imports neither. That is
  what lets it be the one shared definition without coupling the two sides or
  breaking the reloader's backend isolation.
- **camelCase wire, snake_case Python.** `_CamelModel` sets
  `alias_generator=to_camel` + `populate_by_name=True`, so models construct by
  field name (snake_case) yet validate/serialize by alias (camelCase). The
  server validates snake_case Mongo docs with `model_validate` (accepted by
  name) and dumps camelCase JSON with `model_dump(by_alias=True)`.
- **Strict-but-tolerant.** `extra="ignore"` drops unknown fields so a newer
  reloader posting extra keys never hard-fails an older server (and vice
  versa). Enum-valued fields use `Literal[...]`, so a genuinely new
  trigger/outcome value IS rejected — those are real contract changes.
- **The slug regex is duplicated from `ssm_server.engines.common`, on
  purpose.** Importing the server's validator would break the leaf rule, so
  `_SLUG_PATTERN` is a copy — keep the two in sync if the slug shape changes.
- **`revision` is opaque.** The validator only trims whitespace and maps empty
  to `None`; it never parses the ETag (quotes included) — the reloader replays
  it verbatim and the server owns its shape.

