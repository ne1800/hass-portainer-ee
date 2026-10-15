#!/usr/bin/env bash
set -euo pipefail
#MISE description="Scan the repository and a required release image with Trivy"

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

if (($# > 1)); then
  printf 'Usage: mise run security:scan -- [IMAGE_REFERENCE]\n' >&2
  exit 1
fi
mise run security:check

trivy config \
  --exit-code 1 \
  --ignorefile .trivyignore.yaml \
  --severity HIGH,CRITICAL \
  --skip-dirs .git \
  --skip-dirs .worktrees \
  --skip-dirs .venv \
  .

app_version="$(yq -r '.app.version' release.yaml)"
image_ref="${1:-local/hass-portainer-ee:${app_version}}"
image_source=remote
if docker image inspect "$image_ref" >/dev/null 2>&1; then
  image_source=docker
elif (($# == 0)); then
  printf 'Required local release image is missing: %s. Run mise run build first.\n' \
    "$image_ref" >&2
  exit 1
fi

scan_report="$(mktemp)"
trap 'unlink "$scan_report"' EXIT
trivy image \
  --image-src "$image_source" \
  --scanners vuln \
  --exit-code 1 \
  --ignorefile .trivyignore.yaml \
  --severity HIGH,CRITICAL \
  --show-suppressed \
  --format json \
  --output "$scan_report" \
  "$image_ref"
mise run security:check -- --report "$scan_report"
