# zehut

Agents-first identity layer for Linux hosts.

`zehut` provisions and tracks machine-local identities — either **system-backed**
(real OS users via `useradd`) or **logical** (metadata only) — and gives each
one a deterministic email address from a configured domain. A separate CLI
consumes zehut's `users.json` registry to provide secrets management on top of
this identity foundation.

## Install

```bash
uv tool install zehut
```

## Quick start

```bash
# One-time bootstrap (needs sudo).
sudo $(which zehut) init --domain agents.example.com --default-backend system

# Create a system-backed user.
sudo $(which zehut) user create alice --nick Ali --about "QA agent"

# Create a logical (metadata-only) user.
zehut user create bot --logical

# List, show, switch.
zehut user list
zehut user show alice
zehut user switch alice     # system: exec sudo -u alice -i
eval "$(zehut user switch bot)"  # logical: sets ZEHUT_IDENTITY

# Health check.
zehut doctor
```

## Documentation

- [Identity model](docs/identity-model.md)
- [Threat model](docs/threat-model.md)
- [Testing](docs/testing.md)
- [Design spec](docs/superpowers/specs/2026-04-24-zehut-cli-design.md)

## License

MIT. See [LICENSE](LICENSE).
