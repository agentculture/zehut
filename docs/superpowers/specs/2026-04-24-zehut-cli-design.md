# zehut CLI — v1 design

**Date:** 2026-04-24
**Status:** Draft (pending user review)
**Applies to:** `zehut` package on PyPI / TestPyPI

## 1. Overview

`zehut` is the **identity layer** of a broader agents-first secrets-management
system. Secrets themselves are delivered by a separate CLI / package, which
consumes the identity registry this package exposes. This scope split is
deliberate: identity is a stable, small, security-critical foundation that
benefits from being shipped, versioned, and reviewed independently of the
secret-handling surface.

A zehut identity (a "user" in v1) is:

- a stable ULID `id`,
- a primary `name`,
- optional profile metadata (`nick`, `about`),
- an auto-generated email (deterministic from `name` and/or `nick` + configured domain; default pattern is `{name}`, configurable),
- a backing: **system** (real local OS user created via `useradd`) or
  **logical** (metadata-only, no OS account).

Mental model in one sentence: **on a zehut machine, the OS user *is* the
identity; logical users are a superset for cases where no OS account is
wanted.**

The CLI mirrors the conventions of
[`afi-cli`](https://github.com/agentculture/afi-cli) (noun-verb argparse,
structured errors with exit codes and remediation, mandatory per-PR version
bump, Trusted-Publisher CI, agent-first globals).

## 2. Scope

### In scope for v1

- Identity lifecycle: create, list, show, switch, whoami, set, delete.
- System-backed isolation via `useradd` / `userdel`.
- Logical identities with env-var switching.
- Deterministic email generation from a configured domain.
- Machine-wide configuration (`/etc/zehut/config.toml`).
- Machine-wide user registry (`/var/lib/zehut/users.json`).
- Agent-first globals: `init`, `doctor`, `learn`, `overview`, `explain`.
- Ambient identity resolution (the OS user *is* the current zehut user).

### Explicitly out of scope for v1

- **Secrets.** Delivered by a separate CLI/package; not in `zehut`.
- **Email provider integration.** Emails are metadata; MX/deliverability is
  the operator's problem.
- **MCP / HTTP surfaces.** `afi-cli` will scaffold those later; v1 is
  CLI-only.
- **Adopting foreign OS users.** `create alice --system` refuses when
  `/etc/passwd` already has `alice` but the registry does not.
- **`user rename`.** The ULID `id` exists so rename is cheap later, but the
  verb isn't in v1.
- **Schema migrations.** `schema_version` is recorded but there is no
  `zehut migrate`; first breaking change will ship it.
- **Remote/cloud backends** (KMS, HSM, vault) — deferred; named as future
  risk surfaces in `docs/threat-model.md`.
- **Audit log.** No mutation journal in v1.
- **Caller auth beyond sudo.** v1 trusts `geteuid()` + sudoers policy.
- **Multi-machine.** Single host; federation is v3+.

### v2 candidates (this package, not secrets)

1. `zehut migrate` + `schema_version` stepper.
2. `zehut user rename` (leveraging stable ULID).
3. `zehut doctor --adopt` for registering pre-existing OS users.
4. Audit log (append-only JSONL under `/var/lib/zehut/audit/`).
5. Email provider plug layer + `zehut email verify <name>` round-trip probe.

Secrets do not appear here because they belong to a different package.

## 3. CLI surface

Noun-verb shape, following `afi` conventions. Top-level globals live
alongside two nouns: `user` and `configuration`.

### 3.1 Globals

| Command | Purpose | Needs root? |
|---|---|---|
| `zehut init` | Bootstrap `/etc/zehut/config.toml` + `/var/lib/zehut/users.json`. Prompts for `domain` and `default_backend`. Idempotent. | yes |
| `zehut doctor` | Run health checks (see §6). | no |
| `zehut learn` | Emit an agent-authored skill describing how to drive zehut (afi-style). | no |
| `zehut overview [--json]` | Full snapshot: config + users + emails + backing types. | no |
| `zehut explain <topic>` | Human-readable explanation of a command or concept (e.g. `zehut explain user switch`). | no |

### 3.2 `zehut configuration`

| Verb | Purpose | Needs root? |
|---|---|---|
| `configuration show [--json]` | Render current `/etc/zehut/config.toml`. | no |
| `configuration set <key> <value>` | Mutate a single key (`domain`, `default_backend`, `email.pattern`, `email.collision`). | yes |
| `configuration set-domain <domain>` | Convenience alias for the most common op. | yes |

### 3.3 `zehut user`

| Verb | Purpose | Needs root? |
|---|---|---|
| `user create <name> [--system\|--logical] [--nick=…] [--about=…]` | Provision user. `--system`: `useradd` + homedir + registry write. `--logical`: registry write only. Default is `configuration.defaults.backend`. | yes iff `--system` |
| `user list [--json]` | Enumerate users: `name`, `backend`, `email`. | no |
| `user show [<name>] [--json]` | Full record. Omit `<name>` → ambient identity. | no |
| `user switch <name>` | System-backed: exec `sudo -u <sysuser> -i` (replaces the shell). Logical: print `export ZEHUT_IDENTITY=<name>` for `eval $(zehut user switch alice)`. | no (system call prompts via sudo) |
| `user whoami [--json]` | Print ambient identity (see §3.4). Non-zero exit if none. Aliased as `user current`. | no |
| `user set [<name>] <key>=<value>` | Mutate `nick`, `about`. Backing and email immutable post-create in v1. Omit `<name>` → ambient identity. | yes |
| `user delete <name> [--keep-home]` | Registry removal + `userdel` for system-backed. `--keep-home` preserves the home directory. | yes iff system-backed |

No `email` noun in v1: emails are auto-generated at `create` from the
configured domain + pattern and stored immutably on the user record.

### 3.4 Ambient identity resolution

Any verb that references a "current" user resolves in this order:

1. **Ambient OS user.** Look up `pwd.getpwuid(os.geteuid()).pw_name` in the
   registry. If the running process's OS user matches a zehut-managed
   system-backed user, that is the identity. Zero configuration for agents
   launched under a zehut-provisioned user (Claude Agent SDK, cron, systemd,
   `sudo -u usera …` — all automatic).
2. **`$ZEHUT_IDENTITY` env var.** For logical users, or to explicitly
   override inside an OS user's shell.
3. **Nothing.** Commands that require a current identity exit with
   `EXIT_USER_ERROR` and remediation `run 'zehut user switch <name>' or
   'zehut user create <name>' first`.

## 4. Architecture

### 4.1 Package layout

```text
zehut/
├── .claude/skills/version-bump/     # vendored from afi-cli
├── .github/workflows/
│   ├── tests.yml
│   ├── publish.yml
│   └── security-checks.yml
├── .markdownlint-cli2.yaml
├── CHANGELOG.md
├── CLAUDE.md
├── LICENSE
├── README.md
├── docs/
│   ├── threat-model.md
│   ├── identity-model.md
│   ├── testing.md
│   └── superpowers/specs/2026-04-24-zehut-cli-design.md
├── pyproject.toml
├── scripts/lint-md.sh
├── tests/
│   ├── unit/
│   ├── integration/                 # gated: real useradd; runs in Docker in CI
│   ├── test_cli.py
│   └── test_self_verify.py
├── uv.lock
└── zehut/
    ├── __init__.py                  # __version__ via importlib.metadata
    ├── __main__.py
    ├── backend/
    │   ├── base.py                  # Backend ABC
    │   ├── logical.py
    │   └── system.py                # useradd/userdel wrapper
    ├── cli/
    │   ├── __init__.py              # main, _build_parser, _dispatch
    │   ├── _commands/
    │   │   ├── configuration.py
    │   │   ├── doctor.py
    │   │   ├── explain.py
    │   │   ├── init.py
    │   │   ├── learn.py
    │   │   ├── overview.py
    │   │   └── user.py
    │   ├── _errors.py               # ZehutError + EXIT_* constants
    │   └── _output.py               # emit_result / emit_diagnostic / emit_error
    ├── config.py
    ├── fs.py                        # paths, fcntl locking, atomic write
    ├── privilege.py                 # geteuid check + sudo advice
    └── users.py                     # registry CRUD + email generation
```

### 4.2 Module responsibilities

| Module | Responsibility | Depends on |
|---|---|---|
| `zehut.cli` | argparse plumbing, dispatch, error routing. Pure UI — no state mutation. | `_errors`, `_output`, noun handlers |
| `zehut.config` | Load/save/validate `config.toml`, apply defaults, enforce schema_version. | `fs` |
| `zehut.users` | Registry CRUD, email generation, ULID issuance, collision resolution. | `fs`, `config`, `backend` |
| `zehut.backend` | Backend ABC + `system`/`logical` strategies. Only place that shells out to `useradd`/`userdel`. | `privilege` |
| `zehut.fs` | Path constants (respecting `ZEHUT_CONFIG_DIR`/`ZEHUT_STATE_DIR` env overrides), `fcntl` locking, atomic write-temp-then-rename. | stdlib only |
| `zehut.privilege` | `geteuid()` check, sudo-advice message construction, detects `uv tool` PATH pitfall for `sudo zehut`. | stdlib only |

All handlers raise `ZehutError`; `_dispatch` catches and exits with the code.
No Python tracebacks leak to users.

### 4.3 The registry as a contract

`/var/lib/zehut/users.json` is the **stable API surface** the separate
secrets CLI consumes. Breaking changes to its schema bump `schema_version`
and require a coordinated release. Internal modules always read/write the
registry through `zehut.users`, never directly — so the on-disk format can
change without touching the rest of the package.

## 5. State schema

### 5.1 Files

```text
/etc/zehut/config.toml         0644  root:root
/var/lib/zehut/users.json      0644  root:root
/var/lib/zehut/.lock           0644  root:root  (fcntl advisory lock)
```

Paths are overridable for tests via `ZEHUT_CONFIG_DIR` and
`ZEHUT_STATE_DIR` (documented in `docs/testing.md`; not advertised to end
users).

### 5.2 `config.toml`

```toml
schema_version = 1

[defaults]
backend = "system"          # "system" | "logical" — chosen at init

[email]
domain = "agents.example.com"
pattern = "{name}"          # tokens: {name}, {nick}, {id-short}. Fallback: "{nick|name}"
collision = "suffix"        # "-2", "-3", … up to 99 then EXIT_CONFLICT
```

### 5.3 `users.json`

```json
{
  "schema_version": 1,
  "users": [
    {
      "id": "01HYA9...",
      "name": "alice",
      "nick": "Ali",
      "about": "QA agent",
      "email": "ali@agents.example.com",
      "backend": "system",
      "system_user": "alice",
      "system_uid": 1001,
      "created_at": "2026-04-24T12:00:00Z",
      "updated_at": "2026-04-24T12:00:00Z"
    }
  ]
}
```

- `id` is a ULID — immutable, stable across future renames.
- `name` is the primary handle; for system-backed it MUST equal
  `system_user`.
- `system_uid` is recorded at create time for drift detection in `doctor`.

### 5.4 I/O discipline

- Writers take `fcntl.LOCK_EX` on `.lock`; readers take `LOCK_SH`.
- Every write: `write_text(tmp)` → `os.fsync` → `os.replace(tmp, target)`.
- Reads validate `schema_version == 1`; mismatches raise `EXIT_STATE` with
  `run 'zehut migrate' when available (not yet in v1)`.

### 5.5 Transactional ordering

| Op | Order | Rationale |
|---|---|---|
| `create --system` | `useradd` → registry write | If registry write crashes, the orphan OS user is detectable by `doctor`. No registry entry ever points at a missing uid. |
| `delete --system` | registry remove → `userdel` | If `userdel` crashes, registry is clean; orphan OS user is detectable by `doctor`. |
| `set` | registry only, atomic | No OS state change in v1. |

## 6. Error model

Handlers raise `ZehutError(code, message, remediation)`.
`zehut.cli._dispatch` catches, routes through `_output.emit_error` (text or
JSON depending on `--json`), and returns the exit code. Unknown exceptions
are wrapped into an `EXIT_INTERNAL` `ZehutError`.

### 6.1 Exit codes

| Code | Name | Meaning |
|---|---|---|
| 0 | `EXIT_SUCCESS` | — |
| 64 | `EXIT_USER_ERROR` | Bad args, unknown name, verb pre-conditions unmet. |
| 65 | `EXIT_STATE` | Uninitialized or corrupt state (missing files, schema mismatch). |
| 66 | `EXIT_PRIVILEGE` | Operation requires root and current euid is not 0. |
| 67 | `EXIT_BACKEND` | OS-level op failed (`useradd`/`userdel` non-zero). |
| 68 | `EXIT_CONFLICT` | Name / email / uid collision. |
| 70 | `EXIT_INTERNAL` | Wrapped unexpected exception. Ships a bug-report hint. |

### 6.2 Notable error surfaces

- **Needs sudo.** `user create --system` without root: `EXIT_PRIVILEGE`
  with `re-run with: sudo $(which zehut) user create alice --system`.
  `privilege.py` adds the `$(which zehut)` hint because `uv tool install`
  places the binary in `~/.local/bin`, which is not on root's `secure_path`.
- **Not initialized.** `EXIT_STATE`, remediation `run: sudo zehut init`.
- **Foreign OS user.** `create alice --system` when `alice` exists in
  `/etc/passwd` but not in the registry: `EXIT_CONFLICT`, remediation
  `pick a different name; v2 will add 'doctor --adopt'`.
- **Email collision beyond suffix limit.** `EXIT_CONFLICT`, remediation
  `pass --nick=<distinct>`.
- **Registry ↔ OS drift.** `doctor` reports (does not fix) registry
  entries whose `system_uid` no longer matches `/etc/passwd`, and OS users
  whose name matches a *logical* zehut user.

### 6.3 `doctor` checks

Each returns `PASS` / `FAIL` / `WARN` with remediation.

1. `/etc/zehut/config.toml` exists, parses, has required keys, `schema_version == 1`.
2. `/var/lib/zehut/users.json` exists, parses, `schema_version == 1`.
3. File modes / ownership match expectations (0644 root:root).
4. `useradd`, `userdel`, `id` are on `PATH` (only required if any
   system-backed users exist).
5. For each system-backed entry: `pwd.getpwnam(system_user)` resolves and
   the uid matches `system_uid`.
6. No OS-user name collides with any *logical* zehut user name.
7. Ambient resolution: if the current OS user is zehut-managed, registry
   agrees with `os.geteuid()`.
8. `email.domain` is well-formed (format check only; no DNS/MX in v1).

## 7. Packaging, versioning, CI

### 7.1 Packaging

- `pyproject.toml`: hatchling, `requires-python = ">=3.12"`.
- **Zero runtime dependencies** — stdlib only (argparse, tomllib, json,
  fcntl, pwd, subprocess, pathlib, uuid/ulid via a small vendored helper or
  stdlib `uuid.uuid7()` on 3.14+ / minimal ULID impl on 3.12–3.13).
- `project.scripts`: `zehut = "zehut.cli:main"`.
- Install: `uv tool install zehut`. Privileged verbs: `sudo $(which zehut) …`.
- Published on PyPI (existing package reservation) and TestPyPI.
- First published version: `0.1.0` (pre-alpha classifier).

### 7.2 Dev dependency group

Identical to `afi-cli`: pytest, pytest-xdist, pytest-cov, bandit, pylint,
flake8, flake8-bandit, flake8-bugbear, coverage, pre-commit, isort, black.

### 7.3 Versioning (mirror of afi strategy)

- **Every PR bumps.** Enforced by the `version-check` job in `tests.yml`,
  which compares `HEAD`'s `project.version` against `main`'s.
- `.claude/skills/version-bump/` is vendored from afi-cli. Usage:
  `python3 .claude/skills/version-bump/scripts/bump.py {patch|minor|major}`
  with a JSON changelog object on stdin.
- Defaults: **patch** for docs/config/CI, **minor** for new commands or
  verbs, **major** for breaking changes (schema_version bump, removed
  verbs, exit-code reshuffle).
- `CHANGELOG.md` entries 1:1 with merged PRs.
- `zehut/__init__.py`: `__version__ = importlib.metadata.version("zehut")` —
  single source of truth in `pyproject.toml`.

### 7.4 CI workflows

| Workflow | Trigger | Jobs |
|---|---|---|
| `tests.yml` | PR, push to main | lint (flake8/pylint/bandit/black/isort), pytest matrix, `version-check`, markdown lint |
| `publish.yml` | PR → TestPyPI; push to `main` → PyPI | Trusted Publishing (OIDC), `uv build`, upload |
| `security-checks.yml` | weekly + manual | bandit, pip-audit, trivy fs scan |

### 7.5 Markdown linting

`.markdownlint-cli2.yaml` at repo root (MD013/MD060 disabled — parity
with afi-cli). `scripts/lint-md.sh` wraps `markdownlint-cli2 --fix`.
Pre-commit runs it in check-only mode.

## 8. Testing strategy

- **Unit tests.** No network, no real sudo, no real `useradd`. Cover every
  module. Use `ZEHUT_CONFIG_DIR` / `ZEHUT_STATE_DIR` tmp overrides.
- **Integration tests** under `tests/integration/`. Shell out to real
  `useradd`/`userdel`. Gated:
  `@pytest.mark.skipif(os.geteuid() != 0 and not os.getenv("ZEHUT_DOCKER"))`.
  CI runs them inside a disposable Docker container; local `main` stays
  green without polluting the runner.
- **`test_self_verify.py`.** Dogfood: tmpdir-rooted lifecycle
  (`init → create logical → list → whoami → delete`), then assert
  `zehut doctor --json` returns all-PASS. Parallels afi-cli's self-verify.
- **Coverage floor:** 70% (`pyproject.toml` `[tool.coverage.report]
  fail_under = 70`).

## 9. Threat model (stub — full text in `docs/threat-model.md`)

- **Trust boundary.** The host OS + sudoers policy.
- **Adversary model (v1).** Single-admin trusted host. Non-root local
  users must not be able to escalate via zehut, tamper with the registry,
  or impersonate another zehut user.
- **Risk surfaces to enumerate:**
  1. Privileged subprocess invocation of `useradd` / `userdel` (argument
     sanitization, `PATH` pinning to `/usr/sbin:/usr/bin`).
  2. TOCTOU between `geteuid()` check and subprocess invocation.
  3. Registry file tampering (writable only by root; readers take shared
     lock; mode/owner validated by `doctor`).
  4. Email domain takeover (out of zehut's control; called out).
  5. Unprotected state during `init` (create files with restrictive perms
     first, then populate).

## 10. Open questions left for implementation

These are small enough that the implementation plan can resolve them; they
don't require further spec-level brainstorming:

- Exact ULID implementation (stdlib `uuid.uuid7` vs a ~30-line vendored
  ULID generator). Decide when writing `zehut.users`.
- Precise `useradd` flag set (default shell, group handling, skel).
  Document chosen flags in `zehut.backend.system` with citations to
  `useradd(8)`.
- Whether `doctor` should have a `--fix` flag in v1 for safe repairs
  (permissions only) or leave all repairs to v2. Recommend: read-only in
  v1, clearer boundary.

## 11. Acceptance for v1

- All commands in §3 implemented and covered by unit tests.
- `zehut doctor --json` returns all-PASS on a clean `init` + create/delete
  cycle (logical *and* system, the latter in Docker CI).
- `tests.yml` passes with `version-check`, lint, and pytest.
- `publish.yml` successfully uploads `0.1.0` to TestPyPI on PR.
- `docs/threat-model.md` and `docs/identity-model.md` exist and are
  linked from `README.md`.
