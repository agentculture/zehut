# Testing zehut

## Local unit tests

```bash
uv run pytest -n auto
```

Integration tests are marked `@pytest.mark.integration` and skip by
default (they require real `useradd`/`userdel`).

## Integration tests

Two ways to run them:

1. **As root on a disposable VM:**

   ```bash
   sudo -E uv run pytest -v -m integration
   ```

   Only do this on a throwaway machine — the tests create and destroy
   OS users named `zht<hex>`.

2. **Inside the CI Docker image:**

   ```bash
   docker build -t zehut-int -f .github/workflows/Dockerfile.integration .
   docker run --rm -e ZEHUT_DOCKER=1 zehut-int \
     uv run pytest tests/integration -v -m integration
   ```

## Test-only environment hooks

Unit tests rely on these overrides; they are not user-facing features.

- `ZEHUT_CONFIG_DIR` — overrides `/etc/zehut`. Tests point this at a
  tmpdir so they never touch the real system.
- `ZEHUT_STATE_DIR` — overrides `/var/lib/zehut`. Same rationale.
- `ZEHUT_ASSUME_ROOT=1` — makes `zehut.privilege.is_root()` return
  `True` regardless of actual euid. Used by `tests/test_self_verify.py`
  to exercise the privilege-gated paths without running as root.
- `ZEHUT_DOCKER=1` — signals the integration-test gate that we're
  running inside the disposable CI container; otherwise integration
  tests only run as real root.

## Coverage

`pyproject.toml` enforces a 70% floor via `[tool.coverage.report]
fail_under = 70`. Local inspection:

```bash
uv run pytest --cov=zehut --cov-report=term-missing
```
