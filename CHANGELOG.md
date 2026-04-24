# Changelog

All notable changes to `zehut` will be documented in this file. The format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and
this project adheres to [Semantic Versioning](https://semver.org/).

## [0.2.0] - 2026-04-24


### Added

- `--subuser` backend and `--parent` flag on `zehut user create` — replaces `--logical`.
- Cascade delete: removing a system-backed user automatically removes every sub-user whose `parent_id` matches, reported as `cascaded_subusers` in the delete output.
- `subuser_parents_valid` check in `zehut doctor` — catches hand-edited drift in `users.json` where sub-users point at missing or non-system parents.
- `zehut explain subuser` topic.


### Changed

- **BREAKING:** `users.json` `schema_version` 1 → 2. Every record now carries `parent_id` (ULID or null); the `logical` backend is replaced by `subuser`. No automatic migration; re-initialise with `zehut init --force` on an empty registry.
- **BREAKING:** `configuration.default_backend` accepts `system | subuser` (was `system | logical`). `zehut init --default-backend` choices updated.
- **BREAKING:** `zehut user create --logical` is gone. Use `zehut user create <name> --subuser --parent <system-user>`. Sub-users require a system-backed parent (hierarchy is flat: sub-users cannot own sub-users).
- `zehut user list` gained a `PARENT` column.
- `zehut doctor` `logical_names_free` check renamed to `subuser_names_free`.

## [Unreleased]

## [0.1.0] — 2026-04-24

### Added

- Initial v1 release: `zehut init`, `zehut user create/list/show/set/delete/switch/whoami/current`,
  `zehut configuration show/set/set-domain`, `zehut doctor`, `zehut learn`,
  `zehut overview`, `zehut explain`.
- System-backed and logical identity backings.
- Deterministic email generation from a configurable pattern +
  collision suffixing.
- Ambient identity resolution (OS user → registry match →
  `$ZEHUT_IDENTITY` fallback).
- Root-owned machine state under `/etc/zehut/` and `/var/lib/zehut/`,
  with `fcntl` locking and atomic rename.
- Zero runtime dependencies (stdlib only).
- CI: lint, unit tests, Docker-gated integration tests, Trusted
  Publishing to TestPyPI (on PR) and PyPI (on push to `main`).

[Unreleased]: https://github.com/OriNachum/zehut/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/OriNachum/zehut/releases/tag/v0.1.0
