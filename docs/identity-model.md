# zehut identity model

A zehut identity is:

- a stable **ULID `id`** — immutable, safe to reference in audit trails
  and future rename operations.
- a **`name`** — the primary handle users type. For system-backed users
  this MUST equal the OS username.
- optional **`nick`** and **`about`** metadata.
- an auto-generated **`email`** derived from `configuration.email_pattern`
  and `configuration.domain` at create-time, collision-suffixed if needed.
  Immutable post-create.
- a **backing**: `system` or `subuser`.
- a **`parent_id`** — ULID reference to the owning system user. `null`
  for system users (they are always top-level); required non-null for
  sub-users.

## Backings

### System-backed

- A real local OS account (`useradd` at create, `userdel` at delete).
- Home directory created by default (`useradd -m`); skipped deletion
  with `zehut user delete --keep-home`.
- Primary group matches the username (`useradd -U`).
- Default shell `/bin/bash`.
- Provisioning requires root — the CLI surfaces a `sudo zehut …`
  remediation when called unprivileged.
- Always top-level: `parent_id == null`.

### Sub-user

A sub-user is a metadata-only identity scoped under exactly one
system-backed parent. Intended for one OS user ("an agent") to own
multiple dependent identities ("bots"), each with its own ULID and
deterministic email — without spinning up an OS account per bot.

- Metadata only. No OS account. No sudo required for create/delete.
- Must be created with `--parent <system-user-name>`. The parent must
  exist, must have backing `system`, and must itself be top-level
  (hierarchy is **flat**: sub-users cannot own sub-users).
- Cascade delete: removing a system-backed user also removes every
  sub-user whose `parent_id` matches. The cascaded names are reported
  in the `zehut user delete` output (`cascaded_subusers`).
- "Current identity" cannot be resolved ambient-style (no OS user to
  match against); falls back to `$ZEHUT_IDENTITY` env var.
- Privilege inheritance (the intent): a sub-user represents a role the
  parent has delegated to a long-lived application. Any app-level
  privilege the parent holds is conceptually available to its
  sub-users. `zehut` itself does not yet implement app-level
  privileges — this is the design hook for the forthcoming secrets CLI.

## Ambient resolution

`zehut user whoami` (aliased `current`), and the optional `<name>`
argument of `zehut user show` / `set`, resolve the current identity in
this order:

1. **OS user match**: `pwd.getpwuid(os.geteuid()).pw_name` is looked up
   against system-backed registry entries. If found, that is the
   identity. Zero-config for agents launched under a zehut-provisioned
   user (Claude Agent SDK, cron, systemd services, `sudo -u …`).
2. **`$ZEHUT_IDENTITY`**: set by `eval $(zehut user switch <subuser>)`
   inside a shell, or exported manually. This is how a process assumes
   a sub-user identity — there is no OS-level `sudo -u` equivalent
   because sub-users have no OS account.
3. **None**: commands that require a current identity exit with
   `EXIT_USER_ERROR` and a remediation hint.

## The registry as a stable contract

`/var/lib/zehut/users.json` is consumed by a separate (forthcoming)
secrets CLI. `schema_version = 2` is the current shape.

- **v1 → v2** was the breakaway change: the `logical` backend was
  replaced by `subuser`, and every record gained a `parent_id` field
  (`null` for system users; a ULID reference to a system user for
  sub-users). There is no automatic migration in the current release;
  any existing v1 file must be re-initialised.
- Any further breaking change bumps the version again and ships a
  `zehut migrate` verb.

Downstream consumers should:

- Read the file under `fs.shared_lock(/var/lib/zehut/.lock)`.
- Treat `parent_id` as authoritative for ownership — a secrets CLI that
  issues credentials to a sub-user MUST look up the parent and scope
  the issuance against the parent's permissions, not the sub-user's.
- Never write. All mutations MUST go through `zehut user …` /
  `zehut configuration …` so the system-layer provisioning stays in
  sync and cascade semantics are honoured.
