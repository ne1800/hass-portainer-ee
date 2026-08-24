#!/usr/bin/env bash
set -euo pipefail
#MISE description="Run all deterministic repository tests"

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

shell_test_count=0
while IFS= read -r test_file; do
  "$test_file"
  shell_test_count=$((shell_test_count + 1))
done < <(find tests -maxdepth 1 -type f -name '*.sh' -perm -u+x | sort)

if ((shell_test_count == 0)); then
  printf 'No executable shell tests found.\n' >&2
  exit 1
fi

uv run --locked pytest

printf '%s shell test(s) and all Python tests passed.\n' "$shell_test_count"
