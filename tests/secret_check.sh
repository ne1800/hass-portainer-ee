#!/usr/bin/env bash
set -euo pipefail

source tests/lib/assert.sh

config="$(pwd)/.gitleaks.toml"
assert_file "$config"
assert_executable .mise/tasks/security/secrets.sh
[[ ! -e tools/secret-check.sh ]] ||
  fail "The custom public history scanner still exists"
if .mise/tasks/security/secrets.sh --range HEAD^..HEAD >/dev/null 2>&1; then
  fail "The current-tree task still accepts a history range"
fi

fixture_parent="$(mktemp -d)"
trap 'rm -rf "$fixture_parent"' EXIT

gitleaks_dir() {
  gitleaks dir \
    --no-banner \
    --no-color \
    --redact=100 \
    --log-level error \
    --config "$config" \
    "$1"
}

clean_tree="$fixture_parent/clean-tree"
mkdir -p "$clean_tree"
printf 'Clean fixture\n' >"$clean_tree/payload.txt"
if ! gitleaks_dir "$clean_tree" >/dev/null 2>&1; then
  fail "Clean tree was rejected"
fi

dummy_jwt='eyJhbGciOiJIUzI1NiJ9.''eyJzdWIiOiJmaXh0dXJlLXVzZXIifQ.''dGVzdC1zaWduYXR1cmUtbm90LWEtc2VjcmV0'
jwt_tree="$fixture_parent/jwt-tree"
mkdir -p "$jwt_tree"
printf '%s\n' "$dummy_jwt" >"$jwt_tree/payload.txt"
if jwt_output="$(gitleaks_dir "$jwt_tree" 2>&1)"; then
  fail "JWT pattern was not rejected"
fi
[[ "$jwt_output" != *"$dummy_jwt"* ]] ||
  fail "JWT value was printed in the error message"

dummy_pat='xoxb-123456789012-''123456789012-abcdefghijklmnopqrstuvwx'
pat_tree="$fixture_parent/pat-tree"
mkdir -p "$pat_tree"
printf '%s\n' "$dummy_pat" >"$pat_tree/payload.txt"
if pat_output="$(gitleaks_dir "$pat_tree" 2>&1)"; then
  fail "Common secret was not rejected"
fi
[[ "$pat_output" != *"$dummy_pat"* ]] ||
  fail "Secret value was printed in the error message"

fixture_repo="$fixture_parent/history-repo"
git init --quiet --initial-branch=main "$fixture_repo"
git -C "$fixture_repo" config user.name "External Contributor"
git -C "$fixture_repo" config user.email "contributor@example.invalid"
printf 'Base\n' >"$fixture_repo/base.txt"
git -C "$fixture_repo" add base.txt
git -C "$fixture_repo" commit --quiet -m "test: base"
fixture_base="$(git -C "$fixture_repo" rev-parse HEAD)"

printf '%s\n' "$dummy_jwt" >"$fixture_repo/payload.txt"
git -C "$fixture_repo" add payload.txt
git -C "$fixture_repo" commit --quiet -m "test: add secret"
git -C "$fixture_repo" rm --quiet payload.txt
git -C "$fixture_repo" commit --quiet -m "test: remove secret"
fixture_head="$(git -C "$fixture_repo" rev-parse HEAD)"

if history_output="$(
  gitleaks git \
    --no-banner \
    --no-color \
    --redact=100 \
    --log-level error \
    --config "$config" \
    --log-opts="${fixture_base}..${fixture_head}" \
    "$fixture_repo" 2>&1
)"; then
  fail "Secret removed in a later commit was not rejected"
fi
[[ "$history_output" != *"$dummy_jwt"* ]] ||
  fail "Historical JWT value was printed in the error message"
