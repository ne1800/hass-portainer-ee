#!/usr/bin/env bash
set -euo pipefail

source tests/lib/assert.sh

assert_file mise.toml
assert_not_contains mise.toml '[tasks.'
assert_contains mise.toml 'gitleaks = "8.30.1"'
assert_contains mise.toml 'gh = "2.98"'
assert_contains mise.toml 'prek = "0.4.14"'
assert_contains mise.toml 'python = "3.13"'
assert_contains mise.toml 'uv = "0.12.5"'

assert_file .gitleaks.toml
assert_contains .gitleaks.toml 'useDefault = true'
assert_contains .gitleaks.toml 'id = "portainer-jwt"'
assert_file .pre-commit-config.yaml
assert_contains .pre-commit-config.yaml 'minimum_prek_version: "0.4.14"'
assert_contains .pre-commit-config.yaml \
  'Commit-SHA pinning is intentionally not used for these hook repositories.'
assert_contains .pre-commit-config.yaml \
  'repo: https://github.com/pre-commit/pre-commit-hooks'
assert_contains .pre-commit-config.yaml 'args: [--enforce-all]'
assert_contains .pre-commit-config.yaml \
  'repo: https://github.com/astral-sh/ruff-pre-commit'
assert_contains .pre-commit-config.yaml \
  'repo: https://github.com/adrienverge/yamllint'
assert_contains .pre-commit-config.yaml \
  'repo: https://github.com/scop/pre-commit-shfmt'
assert_contains .pre-commit-config.yaml \
  'repo: https://github.com/shellcheck-py/shellcheck-py'
assert_contains .pre-commit-config.yaml \
  'repo: https://github.com/rhysd/actionlint'
assert_contains .pre-commit-config.yaml \
  'repo: https://github.com/zizmorcore/zizmor-pre-commit'
assert_contains .pre-commit-config.yaml \
  'repo: https://github.com/hadolint/hadolint'
assert_contains .pre-commit-config.yaml 'entry: mise run security:secrets'
assert_not_contains .pre-commit-config.yaml 'entry: mise run lint'
assert_not_contains .pre-commit-config.yaml 'entry: mise run test'

assert_file pyproject.toml
assert_file uv.lock
assert_contains pyproject.toml 'requires-python = ">=3.13,<3.14"'
assert_contains pyproject.toml 'ruamel-yaml'
assert_contains pyproject.toml 'pytest'
assert_not_contains pyproject.toml '"ruff>='

for hook_managed_tool in shellcheck shfmt yamllint zizmor; do
  assert_not_contains mise.toml "${hook_managed_tool} ="
done

for task in setup check lint test; do
  assert_executable ".mise/tasks/${task}.sh"
done
assert_contains .mise/tasks/lint.sh \
  'exec prek run --all-files --show-diff-on-failure'
assert_contains .mise/tasks/check.sh 'mise run lint'
assert_contains .mise/tasks/check.sh 'mise run test'

assert_executable .mise/tasks/hooks/install.sh
assert_contains .mise/tasks/hooks/install.sh 'core.hooksPath'
assert_contains .mise/tasks/hooks/install.sh '--hook-type pre-commit'
assert_not_contains .mise/tasks/hooks/install.sh '--hook-type pre-push'

assert_executable .mise/tasks/release/check.py
assert_contains .mise/tasks/release/check.py \
  '#!/usr/bin/env -S uv run --locked python'
assert_contains .mise/tasks/release/check.py \
  '#MISE description="Verify release metadata and image pins"'
assert_executable .mise/tasks/update/check.py
assert_contains .mise/tasks/update/check.py \
  '#!/usr/bin/env -S uv run --locked python'
assert_contains .mise/tasks/update/check.py \
  '#MISE description="Check official Portainer releases for allowed updates"'
assert_executable .mise/tasks/update/apply.py
assert_contains .mise/tasks/update/apply.py \
  '#!/usr/bin/env -S uv run --locked python'
assert_contains .mise/tasks/update/apply.py \
  '#MISE description="Apply validated Portainer update output reproducibly"'
assert_executable .mise/tasks/security/secrets.sh
assert_contains .mise/tasks/security/secrets.sh 'gitleaks dir'
[[ ! -e tools/secret-check.sh ]] ||
  fail "The custom public history scanner still exists"
assert_contains mise.toml '"aqua:docker/buildx" = "0.36"'
assert_contains .mise/tasks/build.sh 'docker-cli-plugin-docker-buildx build'
assert_contains .mise/tasks/build.sh '--load'

assert_not_contains .mise/tasks/setup.sh 'git config --local user.name'
assert_not_contains .mise/tasks/setup.sh 'git config --local user.email'
assert_not_contains .mise/tasks/setup.sh 'git config --local core.hooksPath'

repo_root="$(pwd)"
hook_task="$repo_root/.mise/tasks/hooks/install.sh"
fixture_parent="$(mktemp -d)"
trap 'rm -rf "$fixture_parent"' EXIT

custom_hooks_repo="$fixture_parent/custom-hooks"
git init --quiet --initial-branch=main "$custom_hooks_repo"
git -C "$custom_hooks_repo" config core.hooksPath custom-hooks
if (
  cd "$custom_hooks_repo"
  env \
    GIT_CONFIG_GLOBAL=/dev/null \
    GIT_CONFIG_SYSTEM=/dev/null \
    "$hook_task"
) >/dev/null 2>&1; then
  fail "Hook installation overwrote a custom hooks path"
fi

plain_repo="$fixture_parent/plain"
git init --quiet --initial-branch=main "$plain_repo"
cp "$repo_root/.pre-commit-config.yaml" "$plain_repo/.pre-commit-config.yaml"
(
  cd "$plain_repo"
  env \
    GIT_CONFIG_GLOBAL=/dev/null \
    GIT_CONFIG_SYSTEM=/dev/null \
    "$hook_task"
) >/dev/null
assert_executable "$plain_repo/.git/hooks/pre-commit"
