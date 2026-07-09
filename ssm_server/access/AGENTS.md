# ssm_server/access — Agent Guide

> Nearest-scope guide for `ssm_server/access/`. Read the [root `AGENTS.md`](../../AGENTS.md)
> and the parent [`ssm_server/AGENTS.md`](../AGENTS.md) first for cross-cutting
> principles and the memory protocol. This file captures only what is **not
> obvious from the code** in this scope. `CLAUDE.md` here is a symlink to this
> file — edit this one.

## Responsibility

The authentication + authorization boundary: prove who's calling (token or
userpass) and decide whether that actor may perform a given action, optionally
scoped to a project or config.

| Module | Answers |
| --- | --- |
| `is_auth.py` | How does a request get authenticated and gated behind a scope? Where does the audit-log event get written? |
| `tokens.py` | How are tokens created, hashed, verified, and revoked? Where does a personal token's *effective* scope come from? |
| `userpass.py` | How is a username/password registered and verified? What's the password policy? |
| `onboarding.py` | What happens on first run — who becomes the initial admin, and how is "already bootstrapped" enforced? |
| `policy.py` | Given an actor and an action, is it allowed? (pure scope-matching, no I/O) |
| `scopes.py` | What are the canonical action-scope strings, and how does a "global" scopes payload get built? |

## Non-obvious decisions

- **Two header shapes are both first-class.** `is_auth.py::_extract_token`
  accepts `Authorization: Bearer <token>` or `X-API-KEY: <token>`. Both are
  relied on by existing clients — don't drop either.
- **Tokens are stored hashed, never raw.** `tokens.py` keeps a unique index
  on `token_hash`; `authenticate`/`is_authorized` hash the presented token
  before every lookup. Never log or persist the plaintext token — it only
  ever exists in the `create_token`/`generate` return value.
- **`authorize()` double-gates personal API tokens.** It first checks the
  actor's *effective* `scopes` (which, for personal tokens, come from the
  injected `personal_actor_resolver` — i.e. `RBAC.resolve_personal_actor` in
  `ssm_server/engines/rbac.py`, derived from workspace/project role). If the actor also
  carries `token_scopes` (set only when `type == "personal"` and
  `purpose == "api"`), the action must *additionally* satisfy those declared
  token scopes. Session-purpose tokens have `token_scopes = None`, so only
  the role-derived scopes apply. This is how an "api"-purpose personal token
  can be scoped down below what its owner's role would otherwise allow.
- **Scope-entry matching has no explicit precedence — it's first-match.**
  In `policy.py::_has_scope`, a scope entry with `config_id` only grants for
  that exact config; one with `project_id` (no `config_id`) grants for any
  request against that project; one with neither grants globally regardless
  of the requested project/config. Entries are scanned in list order and the
  first one whose action+scope matches wins. If you hand-construct a scope
  list, put narrower entries first if you mean for them to matter.
- **`policy.py` is intentionally pure.** `authorize()`/`_has_scope()` take
  only `(actor, action, project_id, config_id)` — no DB, no `flask.g`, no
  `request`. That's what makes it the one piece of this package testable
  without mocking Mongo or a request context; keep new authorization logic
  here rather than folding it into `is_auth.py`.
- **`scopes.py` is the single source of action strings.**
  `DEFAULT_TOKEN_ACTION_SCOPES` is what bootstrap tokens and `global_scopes()`
  grant. `ssm_server/engines/rbac.py`'s `PROJECT_ROLE_ACTIONS` /
  `WORKSPACE_ROLE_GLOBAL_ACTIONS` must use the identical strings — a new
  action added to one but not the other means a role can silently never use
  it (or a bootstrap-issued token silently can't).
- **`is_auth.py` is the one place in this package that reaches for a
  global instead of taking a constructor argument** — it does
  `from ssm_server.api.core import conn, api`, so `ssm_server.access` depends
  back on `ssm_server.api.core` (see [`../api/AGENTS.md`](../api/AGENTS.md),
  "Dependency direction"). `Tokens`, `Onboarding`, and `User_Pass` all take
  their collaborators (collection, resolver, other engines) as constructor
  args instead. This is a known, accepted coupling — follow the injection
  pattern for anything new; don't add more of it.
- **`Tokens.SESSION_TOKEN_TTL_SECONDS` (24h) and
  `Onboarding.BOOTSTRAP_TOKEN_TTL_SECONDS` (~183 days) are unrelated
  constants for unrelated purposes** — a short-lived UI session token vs. a
  long-lived bootstrap/API token. They're not meant to converge.

## Session Lessons (Non-Trivial)

- Werkzeug's `generate_password_hash` treats `method="sha256"` and
  `method="pbkdf2:sha256"` as different, non-interchangeable scheme names —
  the short form is a distinct (weaker, unsalted-style) hasher, not an
  abbreviation of PBKDF2. `userpass.py` was fixed to always pass the full
  `"pbkdf2:sha256"` (see history on this file). If you ever touch the hash
  method here, spell out the full method name.
