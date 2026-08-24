#!/usr/bin/env bash
set -euo pipefail
#MISE description="Scan the repository and local release image with Trivy"

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

trivy config \
  --exit-code 1 \
  --ignorefile .trivyignore.yaml \
  --severity HIGH,CRITICAL \
  --skip-dirs .git \
  --skip-dirs .worktrees \
  .

app_version="$(yq -r '.app.version' release.yaml)"
local_image="local/hass-portainer-ee:${app_version}"

if docker image inspect "$local_image" >/dev/null 2>&1; then
  documented_source_image="$(
    yq -er '.temporary_vulnerability_baseline.source_image' \
      security/accepted-risks.yaml
  )"
  if [[ "$documented_source_image" != "$local_image" ]]; then
    printf 'The security baseline belongs to %s, not the new image %s.\n' \
      "$documented_source_image" "$local_image" >&2
    printf 'Recheck and update the baseline before approving the update PR.\n' >&2
    exit 1
  fi

  scan_report="$(mktemp)"
  cleanup_scan_report() {
    unlink "$scan_report" >/dev/null 2>&1 || true
  }
  trap cleanup_scan_report EXIT

  trivy image \
    --exit-code 1 \
    --ignorefile .trivyignore.yaml \
    --severity HIGH,CRITICAL \
    --show-suppressed \
    --format json \
    --output "$scan_report" \
    "$local_image"

  expected_baseline="$(
    yq -r \
      '.vulnerabilities[] | [.id, .purls[0]] | join("|")' \
      .trivyignore.yaml | sort
  )"
  observed_baseline="$(
    jq -r \
      '.Results[].ExperimentalModifiedFindings[]? | select(.Type == "vulnerability" and .Status == "ignored" and .Source == ".trivyignore.yaml") | [.Finding.VulnerabilityID, .Finding.PkgIdentifier.PURL] | join("|")' \
      "$scan_report" | sort
  )"

  if [[ "$observed_baseline" != "$expected_baseline" ]]; then
    printf 'The security baseline does not match the image.\n' >&2
    printf 'Expected:\n%s\n' "$expected_baseline" >&2
    printf 'Observed:\n%s\n' "$observed_baseline" >&2
    exit 1
  fi

  baseline_count="$(yq -r '.vulnerabilities | length' .trivyignore.yaml)"
  printf '%s temporary HIGH findings matched exactly; new findings block approval.\n' \
    "$baseline_count"
else
  printf 'No local image found; skipped image scan: %s\n' \
    "$local_image"
fi
