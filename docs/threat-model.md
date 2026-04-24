# zehut threat model (v1)

## Trust boundary

The host OS and its sudoers policy. zehut is a privileged CLI: any caller
who can become root can do everything zehut can do anyway. zehut's job is
to be a well-behaved privileged caller — not to enforce authorisation
above the OS layer.

## Adversary model (v1)

Single-admin trusted host. Non-root local users MUST NOT be able to:

1. Escalate privileges via a zehut invocation.
2. Tamper with `/var/lib/zehut/users.json` or `/etc/zehut/config.toml`.
3. Impersonate another zehut user through ambient resolution.

Multi-tenant hosts, network services, and cloud identity backends are
out of scope for v1.

## Risk surfaces

### 1. Privileged subprocess invocation (`useradd` / `userdel`)

- `PATH` is pinned to `/usr/sbin:/usr/bin` on every `subprocess.run` call
  in `zehut/backend/system.py`.
- `LC_ALL=C` is set so error parsing is stable across locales.
- Names are validated against `^[a-z_][a-z0-9_-]{0,31}$` before they
  reach the subprocess — rejects shell metacharacters at the zehut
  layer.
- Flags are hard-coded; user input never lands in a flag position.

### 2. TOCTOU between `geteuid()` and subprocess

- `privilege.require_root()` is called as late as possible (inside the
  handler, before any state mutation). A successful check is immediately
  followed by the privileged subprocess; there is no user-controlled
  I/O in between that could trigger a suid change.
- Python processes cannot drop/gain privileges between calls without
  `setuid`; zehut never calls `setuid`.

### 3. Registry file tampering

- `users.json` and `config.toml` live in root-owned directories with
  mode 0o644. Non-root users can read (needed for `whoami` / `list`)
  but cannot write.
- `doctor` validates modes and ownership; any drift is reported as
  `WARN`.
- Writers hold `fcntl.LOCK_EX` on `.lock` and use
  write-temp→fsync→rename. A concurrent reader holding `LOCK_SH`
  observes the old file until rename completes.

### 4. Email domain takeover

- Out of zehut's control. The configured domain's DNS/MX posture is the
  operator's responsibility. `doctor` only validates syntactic
  well-formedness.
- Documented here so operators understand the boundary.

### 5. Unprotected state during `init`

- `init` creates `config.toml` and `users.json` via
  `fs.atomic_write_text(..., mode=0o644)`, which uses `mkstemp` with
  default 0o600 perms before the explicit `chmod 0o644`. There is no
  window in which either file is world-readable without being also
  world-unwritable.

## Known non-goals (v2+)

- Caller authentication beyond sudo.
- Audit log of mutations.
- Remote/cloud backends.
- Multi-machine federation.

These are tracked in the design spec's "v2 candidates" and will each get
a threat-model update when added.
