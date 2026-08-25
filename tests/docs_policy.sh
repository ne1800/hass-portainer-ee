#!/usr/bin/env bash
set -euo pipefail

source tests/lib/assert.sh

documents=(
  README.md
  portaineree/README.md
  portaineree/DOCS.md
  docs/runbooks/release.md
)
for document in "${documents[@]}"; do
  assert_file "$document"
done

assert_contains README.md "Portainer BE"
assert_contains README.md "STS"
assert_contains README.md "LTS security bridge"
assert_contains README.md "Renovate"
assert_contains README.md "mise run update:check"
assert_contains README.md "mise run check"
assert_contains README.md "mise run lint"
assert_contains README.md "mise run test"
assert_contains README.md "mise run hooks:install"
assert_contains README.md "pre-commit hook repositories"
assert_contains README.md "Git history"
assert_contains README.md "uv.lock"
assert_contains README.md "does not change Git identity or hooks"
assert_not_contains README.md "git config user.email"
assert_not_contains README.md "tools/privacy-check.sh"

for document in portaineree/README.md portaineree/DOCS.md; do
  assert_contains "$document" "protection mode"
  assert_contains "$document" "Ingress"
  assert_contains "$document" '8000'
  assert_contains "$document" '9000'
  assert_contains "$document" '9443'
  assert_contains "$document" '/data'
done
assert_contains portaineree/DOCS.md \
  "does not include container or volume data"
assert_contains portaineree/DOCS.md \
  "fresh instance with an empty \`/data\`"

release_runbook="docs/runbooks/release.md"
for command in \
  "mise install" \
  "mise run setup" \
  "mise run check" \
  "mise run release:check" \
  "mise run build" \
  "mise run security:scan"; do
  assert_contains "$release_runbook" "$command"
done
assert_contains "$release_runbook" "Before every GitHub push"
assert_contains "$release_runbook" "Git history"
assert_contains "$release_runbook" "outside the tracked public repository"
assert_not_contains "$release_runbook" "repository-local Noreply"
assert_not_contains "$release_runbook" "privacy checks"
assert_contains "$release_runbook" "v2.44.0.1"
assert_contains "$release_runbook" "anonym"
assert_contains "$release_runbook" "cosign verify"
assert_not_contains "$release_runbook" "image-tags: latest"

for document in "${documents[@]}"; do
  if LC_ALL=C grep -aEq \
    'https?://[^[:space:]]*[.]home([.:/]|$)' \
    "$document"; then
    fail "$document contains a local hostname"
  fi
  if LC_ALL=C grep -aEq \
    '(^|[^0-9])(10[.]|192[.]168[.]|172[.](1[6-9]|2[0-9]|3[01])[.])' \
    "$document"; then
    fail "$document contains a private IPv4 address"
  fi
  if LC_ALL=C grep -aEq \
    'eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}' \
    "$document"; then
    fail "$document contains a JWT pattern"
  fi

  while IFS= read -r target; do
    case "$target" in
      http://* | https://* | mailto:* | \#*) continue ;;
    esac
    target="${target%%#*}"
    case "$target" in
      docs/runbooks/release.md | ../docs/runbooks/release.md) ;;
      docs/runbooks/* | ../docs/runbooks/*)
        fail "$document references a site-specific runbook"
        ;;
    esac
    [[ -z "$target" || -e "$(dirname "$document")/$target" ]] ||
      fail "$document references a missing target: $target"
  done < <(
    grep -aoE '\]\([^)]+' "$document" |
      sed 's/^](//'
  )
done
