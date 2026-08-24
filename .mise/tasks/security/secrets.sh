#!/usr/bin/env bash
set -euo pipefail
#MISE description="Scan the current repository tree for secrets"

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

(($# == 0)) || {
  printf 'security:secrets does not accept arguments; use the Gitleaks Action for history scans.\n' >&2
  exit 2
}

exec gitleaks dir \
  --no-banner \
  --no-color \
  --redact=100 \
  --log-level error \
  --config "$repo_root/.gitleaks.toml" \
  "$repo_root"
