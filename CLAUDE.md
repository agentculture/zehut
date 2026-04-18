# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**zehut** — "Agents first secrets manager." A secrets manager whose primary clients are AI agents rather than humans. Repo: https://github.com/OriNachum/zehut

## Current State

Greenfield. The repo contains only `README.md`, `LICENSE` (MIT), and a Python `.gitignore`. There is no source code, build system, test suite, or CI configured yet. Before adding code, expand this file with:

- Chosen language/toolchain and why (the `.gitignore` is Python-flavored but nothing is committed)
- The agent-facing API shape (how agents authenticate, request secrets, and have access scoped — this is the core design question for an "agents first" secrets manager)
- Storage/backend decisions (local file, cloud KMS, HSM, etc.)
- Threat model — secrets managers live or die by this; write it down before the first secret is stored

## Conventions Inherited from the Workspace

This repo lives under `/home/spark/git/`, whose workspace-level `CLAUDE.md` assumes:

- **uv** for Python dependency management (if Python is chosen)
- Projects own their own version bumps and CHANGELOGs
- Branch → implement → version bump → PR is the standard flow

Nothing in this repo enforces those yet — they are defaults to follow unless a reason emerges to diverge.
