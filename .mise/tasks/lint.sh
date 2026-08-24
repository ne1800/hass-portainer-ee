#!/usr/bin/env bash
set -euo pipefail
#MISE description="Lint Python, shell, YAML, JSON, Actions, and Dockerfiles"

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

uv run --locked ruff check .
uv run --locked ruff format --check .

shell_files=()
for directory in .mise tests tools .githooks publication/hooks; do
  if [[ -d "$directory" ]]; then
    while IFS= read -r -d '' path; do
      shell_files+=("$path")
    done < <(find "$directory" -type f \
      \( -name '*.sh' -o -name 'pre-push' \) -print0)
  fi
done

if ((${#shell_files[@]} > 0)); then
  shellcheck -x "${shell_files[@]}"
  shfmt -d -i 2 -ci "${shell_files[@]}"
fi

yaml_files=()
while IFS= read -r -d '' path; do
  yaml_files+=("$path")
done < <(
  find . -type f \( -name '*.yaml' -o -name '*.yml' \) \
    -not -path './.git/*' \
    -not -path './.worktrees/*' \
    -print0
)

if ((${#yaml_files[@]} > 0)); then
  yamllint \
    -d '{extends: default, rules: {document-start: disable, line-length: disable, truthy: disable}}' \
    "${yaml_files[@]}"
fi

json_files=()
while IFS= read -r -d '' path; do
  json_files+=("$path")
done < <(
  find . -type f -name '*.json' \
    -not -path './.git/*' \
    -not -path './.worktrees/*' \
    -print0
)

for path in "${json_files[@]}"; do
  jq empty "$path"
done

if [[ -d .github/workflows ]]; then
  actionlint .github/workflows/*.yml
  zizmor --pedantic .
fi

dockerfiles=()
while IFS= read -r -d '' path; do
  dockerfiles+=("$path")
done < <(
  find . -type f -name Dockerfile \
    -not -path './.git/*' \
    -not -path './.worktrees/*' \
    -print0
)

if ((${#dockerfiles[@]} > 0)); then
  # Alpine package revisions are coupled to the digest-pinned base repository.
  hadolint --ignore DL3018 "${dockerfiles[@]}"
fi
