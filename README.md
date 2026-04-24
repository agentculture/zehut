# zehut

Agents-first identity layer for Linux hosts.

`zehut` provisions and tracks machine-local identities — **system-backed**
(real OS users via `useradd`) plus **sub-users** (metadata-only identities
owned by a system-backed parent) — and gives each one a deterministic
email address from a configured domain. A separate CLI consumes zehut's
`users.json` registry to provide secrets management on top of this
identity foundation.

## Install

```bash
uv tool install zehut
```

## Quick start

```bash
# One-time bootstrap (needs sudo).
sudo $(which zehut) init --domain agents.example.com --default-backend system

# Create a system-backed user — the parent identity (an "agent").
sudo $(which zehut) user create agent --nick Ali --about "QA agent"

# Create sub-users owned by the agent — e.g. per-bot identities.
# Sub-users must have a system-backed parent; deleting the parent
# cascade-deletes every sub-user under it.
sudo $(which zehut) user create bot1 --subuser --parent agent --about "scraper"

# List, show, switch.
zehut user list
zehut user show agent
zehut user switch agent            # system: exec sudo -u agent -i
eval "$(zehut user switch bot1)"   # sub-user: sets ZEHUT_IDENTITY

# Health check.
zehut doctor
```

## Documentation

- [Identity model](docs/identity-model.md)
- [Threat model](docs/threat-model.md)
- [Testing](docs/testing.md)
- [Design spec (v1)](docs/superpowers/specs/2026-04-24-zehut-cli-design.md)
- [Sub-user addendum (v1 → v2)](docs/superpowers/specs/2026-04-24-zehut-subusers.md)

## License

MIT. See [LICENSE](LICENSE).
