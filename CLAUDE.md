# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**zehut** — "Agents first secrets manager." A secrets manager whose primary clients are AI agents rather than humans. Repo: https://github.com/OriNachum/zehut

## Stack

- **Language/runtime:** Python, packaged as a **uv tool** (install via `uv tool install zehut`, run as a CLI).
- **Interface:** CLI-first. The agent-facing API (however it ends up — library, local socket, HTTP) should be reachable through the CLI too.
- **Delivery channel:** email provider. Zehut sends/receives via email — expect an email-based flow to be part of how secrets are issued, rotated, or verified. Pin down which provider and the exact flow before implementing.

## Current State

Greenfield. The repo contains only `README.md`, `LICENSE` (MIT), and a Python `.gitignore`. No `pyproject.toml`, source, tests, or CI yet. Still-open design questions before code lands:

- The agent-facing API shape (how agents authenticate, request secrets, and have access scoped — the core design question for an "agents first" secrets manager)
- Storage/backend decisions (local file, cloud KMS, HSM, etc.)
- Threat model — secrets managers live or die by this; write it down before the first secret is stored
- Email provider choice and what email is actually used for in the flow

## Workflow

- **Branch + PR** for all changes by default. Direct pushes to `main` only with explicit per-change authorization.
- Follow the workspace defaults from `/home/spark/git/CLAUDE.md`: `uv` for deps, per-project version bump before PR.
