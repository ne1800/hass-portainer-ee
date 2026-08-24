#!/usr/bin/env bash
set -euo pipefail
#MISE description="Install the repository Prek pre-commit hook"

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

if hooks_path="$(git config --get core.hooksPath 2>/dev/null)"; then
  printf 'Hook installation refused: core.hooksPath is already set to %s.\n' \
    "$hooks_path" >&2
  exit 1
fi

exec prek install --hook-type pre-commit
