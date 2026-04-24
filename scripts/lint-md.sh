#!/usr/bin/env bash
# Lint (and auto-fix) markdown files tracked in git.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

if [[ $# -gt 0 ]]; then
    files=("$@")
else
    mapfile -t files < <(git ls-files '*.md')
fi

if ! command -v markdownlint-cli2 >/dev/null 2>&1; then
    echo "markdownlint-cli2 not on PATH; install with: npm i -g markdownlint-cli2" >&2
    exit 127
fi

markdownlint-cli2 --fix "${files[@]}"
