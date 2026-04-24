# zehut sub-users — v1 → v2 schema change

**Date:** 2026-04-24
**Supersedes (partially):** `2026-04-24-zehut-cli-design.md` §5.3 (users.json),
§5.1 (backings), and the CLI verbs in §4.
**Status:** Landed (zehut 1.0.0).

## 1. Motivation

v1 shipped two backings: `system` (a real OS account) and `logical`
(metadata only). Logical users were conceived as "a zehut identity for
accounting or email allocation but don't want an OS account to manage".
In practice, every intended use case for logical users has the same
shape:

> one OS user owns several dependent identities — e.g. a culture agent
> running under its own OS account owns a handful of bots. Each bot
> gets a distinct email and ULID, but they are not independent
> principals; they are delegated roles under a single human/agent.

v1 had no way to express that ownership. A compromised or abandoned
logical user had no natural deletion trigger — nothing tied its
lifecycle to the entity that created it. Secrets issued against a
logical user could outlive any real accountable party.

v2 replaces `logical` with `subuser`, which **requires** a
system-backed parent and is **cascade-deleted** when the parent is
deleted. The backing is narrower (no standalone metadata users) but
the resulting identity graph is enforceable and auditable.

## 2. Decisions

| Question | Answer |
|---|---|
| Does the `logical` backing survive? | No. Removed. Only `system` and `subuser`. |
| What can be a sub-user's parent? | **Only** a system-backed user. |
| Can sub-users nest? | No. Flat hierarchy. Parent must be top-level. |
| Privilege inheritance scope? | Documented, not implemented. The secrets CLI consuming this registry is expected to scope issuance against the parent. |

## 3. Schema change (users.json: v1 → v2)

Two changes:

1. Every record gains a `parent_id` field (ULID or `null`).
   - `null` for system-backed users.
   - Non-null, pointing at a system-backed user's `id`, for sub-users.
2. Records with `backend == "logical"` are no longer valid. Loading a
   v1 file raises `EXIT_STATE` with a migration hint.

Shape:

```json
{
  "schema_version": 2,
  "users": [
    {
      "id": "01HYA9...",
      "name": "agent",
      "nick": null,
      "about": null,
      "email": "agent@agents.example.com",
      "backend": "system",
      "system_user": "agent",
      "system_uid": 1001,
      "parent_id": null,
      "created_at": "2026-04-24T12:00:00Z",
      "updated_at": "2026-04-24T12:00:00Z"
    },
    {
      "id": "01HYAB...",
      "name": "bot1",
      "nick": null,
      "about": "scrapes inventory",
      "email": "bot1@agents.example.com",
      "backend": "subuser",
      "system_user": null,
      "system_uid": null,
      "parent_id": "01HYA9...",
      "created_at": "2026-04-24T12:05:00Z",
      "updated_at": "2026-04-24T12:05:00Z"
    }
  ]
}
```

No automatic migration ships in 0.2.0 — the prior release had no
production footprint. A future `zehut migrate` verb will land if needed.

## 4. CLI surface

```sh
# System parent (unchanged).
zehut user create agent --system

# Sub-user — requires --parent.
zehut user create bot1 --subuser --parent agent [--nick ...] [--about ...]

# Rejected:
zehut user create bot1 --subuser                 # EXIT_USER_ERROR: --parent required
zehut user create bot1 --subuser --parent ghost  # EXIT_USER_ERROR: no such parent
zehut user create bot2 --subuser --parent bot1   # EXIT_USER_ERROR: parent must be system-backed
zehut user create other --system --parent agent  # EXIT_USER_ERROR: --parent only with --subuser

# Cascade delete: 'agent' and every sub-user under it vanish in one
# transaction. The names of cascaded children are returned in the
# result payload as 'cascaded_subusers'.
zehut user delete agent
```

`zehut user switch <subuser>` continues to print
`export ZEHUT_IDENTITY=<name>` (same as v1's logical-user switch).

## 5. Validation

Enforced in `zehut.users._resolve_parent` (inside the exclusive lock,
before any backend call):

- `backend == "subuser"` requires `parent_name`.
- Parent must exist.
- Parent's `backend` must be `system`.
- Parent's `parent_id` must be `null` (belt-and-suspenders for
  tampered `users.json`).
- For any non-`subuser` backend, `parent_name` must be `None`.

`zehut doctor` adds `subuser_parents_valid` — a drift detector that
catches hand-edited `users.json` files violating the invariants above.
The old `logical_names_free` check is now `subuser_names_free`.

## 6. Threat model delta

A compromised sub-user must not be able to escalate to its parent.
`zehut` itself does not grant anything — it just records identity —
but the contract for downstream consumers (the forthcoming secrets
CLI) is:

- Privileges flow **from** parent **to** sub-user, never the other
  direction.
- The parent's `system_uid` is the trust anchor. A sub-user's
  credentials must be scoped to the subset of the parent's
  permissions that have been explicitly delegated.
- Deleting the parent atomically revokes every sub-user in the same
  transaction (cascade). Callers waiting on eventual consistency are
  wrong — the registry write is the revocation.

See `docs/threat-model.md` for the wider threat model.

## 7. Reference implementation

- `zehut/users.py` — `UserRecord.parent_id`, `_resolve_parent`,
  `remove()` cascade.
- `zehut/backend/subuser.py` — `SubUserBackend` (renamed from
  `LogicalBackend`, semantically identical: no-op provisioning).
- `zehut/cli/_commands/user.py` — `--subuser`, `--parent`, cascade
  reporting in delete output.
- `zehut/cli/_commands/doctor.py` — `_check_subuser_parents_valid`.
- Tests — see `tests/unit/test_users.py` and
  `tests/unit/test_cmd_user_create.py`.
