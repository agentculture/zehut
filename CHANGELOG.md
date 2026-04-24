# Changelog

All notable changes to `zehut` will be documented in this file. The format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and
this project adheres to [Semantic Versioning](https://semver.org/).

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
