# shellcheck shell=bash
set -euo pipefail

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  return 1
}

assert_file() {
  local path="$1"
  [[ -f "$path" ]] || fail "$path is missing"
}

assert_executable() {
  local path="$1"
  [[ -x "$path" ]] || fail "$path is not executable"
}

assert_contains() {
  local path="$1"
  local expected="$2"
  grep -Fq -- "$expected" "$path" ||
    fail "$path does not contain: $expected"
}

assert_not_contains() {
  local path="$1"
  local unexpected="$2"
  if grep -Fq -- "$unexpected" "$path"; then
    fail "$path unexpectedly contains: $unexpected"
  fi
}

assert_eq() {
  local expected="$1"
  local actual="$2"
  local label="${3:-value}"
  [[ "$actual" == "$expected" ]] ||
    fail "$label: expected '$expected', got '$actual'"
}
