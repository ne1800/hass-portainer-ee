#!/usr/bin/env bash
set -euo pipefail
#MISE description="Run all repository linters through Prek"

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

exec prek run --all-files --show-diff-on-failure
