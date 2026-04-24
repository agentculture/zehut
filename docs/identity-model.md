# zehut identity model

A zehut identity ("user" in v1) is:

- a stable **ULID `id`** — immutable, safe to reference in audit trails
  and future rename operations.
- a **`name`** — the primary handle users type. For system-backed users
  this MUST equal the OS username.
- optional **`nick`** and **`about`** metadata.
- an auto-generated **`email`** derived from `configuration.email_pattern`
  and `configuration.domain` at create-time, collision-suffixed if needed.
  Immutable post-create in v1.
- a **backing**: `system` or `logical`.

## Backings

### System-backed

- A real local OS account (`useradd` at create, `userdel` at delete).
- Home directory created by default (`useradd -m`); skipped deletion
  with `zehut user delete --keep-home`.
- Primary group matches the username (`useradd -U`).
- Default shell `/bin/bash`.
- Provisioning requires root — the CLI surfaces a `sudo zehut …`
  remediation when called unprivileged.

### Logical

- Metadata only. No OS account. No sudo required for create/delete.
- "Current identity" cannot be resolved ambient-style (no OS user to
  match against); falls back to `$ZEHUT_IDENTITY` env var.
- Useful when you need a zehut identity for accounting or email
  allocation but don't want an OS account to manage.

## Ambient resolution

`zehut user whoami` (aliased `current`), and the optional `<name>`
argument of `zehut user show` / `set`, resolve the current identity in
this order:

1. **OS user match**: `pwd.getpwuid(os.geteuid()).pw_name` is looked up
   against system-backed registry entries. If found, that is the
   identity. Zero-config for agents launched under a zehut-provisioned
   user (Claude Agent SDK, cron, systemd services, `sudo -u …`).
2. **`$ZEHUT_IDENTITY`**: set by `eval $(zehut user switch <logical>)`
   inside a shell, or exported manually.
3. **None**: commands that require a current identity exit with
   `EXIT_USER_ERROR` and a remediation hint.

## The registry as a stable contract

`/var/lib/zehut/users.json` is consumed by a separate (forthcoming)
secrets CLI. Its `schema_version = 1` shape is stable; any breaking
change bumps the version and ships a `zehut migrate` verb.

Downstream consumers should:

- Read the file under `fs.shared_lock(/var/lib/zehut/.lock)`.
- Never write. All mutations MUST go through `zehut user …` /
  `zehut configuration …` so the system-layer provisioning stays in
  sync.
