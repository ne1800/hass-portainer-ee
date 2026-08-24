#!/usr/bin/env bash
set -euo pipefail

source tests/lib/assert.sh

assert_file .github/workflows/ci.yml
assert_file .github/workflows/release.yml
assert_file .github/workflows/portainer-update.yml

for workflow in .github/workflows/*.yml; do
  while IFS= read -r uses_value; do
    [[ "$uses_value" =~ ^[^[:space:]@]+@[0-9a-f]{40}$ ]] ||
      fail "$workflow contains an action that is not pinned to a full commit: $uses_value"
  done < <(
    yq -r '.. | select(tag == "!!map") | .uses? // ""' "$workflow" |
      sed '/^$/d'
  )

  if grep -Eiq \
    '(^|[^[:alnum:]_-]):(latest|lts|sts)([^[:alnum:]_.-]|$)' \
    "$workflow"; then
    fail "$workflow contains a mutable image tag"
  fi
done

assert_not_contains .github/workflows/ci.yml "packages: write"
assert_not_contains .github/workflows/ci.yml "pull_request_target"
assert_not_contains .github/workflows/ci.yml "mise run privacy:check"
assert_contains .github/workflows/ci.yml "fetch-depth: 0"
assert_contains .github/workflows/ci.yml \
  "gitleaks/gitleaks-action@e0c47f4f8be36e29cdc102c57e68cb5cbf0e8d1e"
assert_contains .github/workflows/ci.yml \
  "j178/prek-action@4e14d07f9231acabce116ccfca13b13dd9755ece"
assert_contains .github/workflows/ci.yml \
  'GITLEAKS_ENABLE_COMMENTS: "false"'
assert_contains .github/workflows/ci.yml \
  'GITLEAKS_ENABLE_UPLOAD_ARTIFACT: "false"'
assert_contains .github/workflows/ci.yml \
  "GITLEAKS_VERSION: \${{ steps.tool_versions.outputs.gitleaks }}"
assert_contains .github/workflows/ci.yml \
  "prek-version: \${{ steps.tool_versions.outputs.prek }}"
assert_contains .github/workflows/ci.yml "extra-args: --all-files"
assert_not_contains .github/workflows/ci.yml "range_base="
assert_not_contains .github/workflows/ci.yml "commit_range="
assert_not_contains .github/workflows/ci.yml "PR_BASE_SHA"
assert_not_contains .github/workflows/ci.yml "BEFORE_SHA"
assert_not_contains .github/workflows/ci.yml \
  "mise run security:secrets -- --range"
assert_not_contains .github/workflows/ci.yml "name: Run lint"
assert_not_contains .github/workflows/ci.yml "name: Run tests"
assert_contains .github/workflows/ci.yml "mise run release:check"
assert_contains .github/workflows/ci.yml "mise run build"
assert_contains .github/workflows/ci.yml "mise run security:scan"
assert_eq '["pull_request","push","workflow_dispatch"]' \
  "$(yq -o=json '.on | keys' .github/workflows/ci.yml | jq -c 'sort')" \
  "CI triggers"

assert_eq '["release"]' \
  "$(yq -o=json '.on | keys' .github/workflows/release.yml | jq -c 'sort')" \
  "Release triggers"
assert_eq '["published"]' \
  "$(yq -o=json '.on.release.types' .github/workflows/release.yml | jq -c '.')" \
  "Release event"
assert_contains .github/workflows/release.yml \
  "mise run release:check -- --release-tag \"\$GITHUB_REF_NAME\""
assert_contains .github/workflows/release.yml \
  "git merge-base --is-ancestor \"\$tag_commit\" origin/main"

for image_ref in \
  "ghcr.io/ne1800/hass-portainer-ee:\${version}" \
  "ghcr.io/ne1800/amd64-hass-portainer-ee:\${version}" \
  "ghcr.io/ne1800/aarch64-hass-portainer-ee:\${version}"; do
  assert_contains .github/workflows/release.yml "$image_ref"
done

assert_contains .github/workflows/release.yml \
  "Non-404 error while checking registry reference"
assert_contains .github/workflows/release.yml \
  'architectures: '\''["amd64", "aarch64"]'\'''
assert_contains .github/workflows/release.yml \
  "image-tags: \${{ needs.init.outputs.version }}"
assert_not_contains .github/workflows/release.yml "image-tags: latest"

assert_eq "write" \
  "$(yq -r '.jobs.build.permissions.packages' .github/workflows/release.yml)" \
  "Release build package permission"
assert_eq "write" \
  "$(yq -r '.jobs.build.permissions.id-token' .github/workflows/release.yml)" \
  "Release build OIDC permission"
assert_eq "write" \
  "$(yq -r '.jobs.manifest.permissions.packages' .github/workflows/release.yml)" \
  "Manifest job package permission"

assert_eq '["schedule","workflow_dispatch"]' \
  "$(yq -o=json '.on | keys' .github/workflows/portainer-update.yml | jq -c 'sort')" \
  "Portainer update check triggers"
assert_eq "17 4 * * *" \
  "$(yq -r '.on.schedule[0].cron' .github/workflows/portainer-update.yml)" \
  "Portainer update check schedule"
assert_eq "write" \
  "$(yq -r '.jobs.update.permissions.contents' .github/workflows/portainer-update.yml)" \
  "Portainer update check contents permission"
assert_eq "write" \
  "$(yq -r '.jobs.update.permissions.pull-requests' .github/workflows/portainer-update.yml)" \
  "Portainer update check pull request permission"
assert_eq "write" \
  "$(yq -r '.jobs.update.permissions.actions' .github/workflows/portainer-update.yml)" \
  "Portainer update check workflow dispatch permission"
assert_eq "null" \
  "$(yq -r '.jobs.update.permissions.packages' .github/workflows/portainer-update.yml)" \
  "Forbidden Portainer update check package permission"
assert_contains .github/workflows/portainer-update.yml "mise run update:check"
assert_contains .github/workflows/portainer-update.yml "mise run update:apply"
assert_contains .github/workflows/portainer-update.yml \
  "branch=\"automation/portainer-\${TARGET_VERSION}\""
assert_contains .github/workflows/portainer-update.yml \
  "git config user.name 'github-actions[bot]'"
assert_contains .github/workflows/portainer-update.yml \
  "'41898282+github-actions[bot]@users.noreply.github.com'"
assert_contains .github/workflows/portainer-update.yml \
  "mise exec -- gh workflow run ci.yml"
assert_not_contains .github/workflows/portainer-update.yml "packages: write"
assert_not_contains .github/workflows/portainer-update.yml "pull_request_target"
assert_not_contains .github/workflows/portainer-update.yml "gh pr merge"
assert_not_contains .github/workflows/portainer-update.yml "gh release"

for workflow in \
  .github/workflows/ci.yml \
  .github/workflows/portainer-update.yml \
  .github/workflows/release.yml; do
  assert_not_contains "$workflow" "uv run"
  assert_not_contains "$workflow" "python "
done
