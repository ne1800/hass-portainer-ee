#!/usr/bin/env bash
set -euo pipefail
#MISE description="Run lint and deterministic tests"

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

mise run lint
exec mise run test
