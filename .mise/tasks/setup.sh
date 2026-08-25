#!/usr/bin/env bash
set -euo pipefail
#MISE description="Verify repository tools and tasks"

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

required_tools=(
  actionlint
  cosign
  docker-cli-plugin-docker-buildx
  gitleaks
  hadolint
  jq
  prek
  python
  regctl
  trivy
  uv
  yq
)

for tool in "${required_tools[@]}"; do
  command -v "$tool" >/dev/null ||
    {
      printf 'Required tool is missing: %s\n' "$tool" >&2
      exit 1
    }
done

required_task_files=(
  .mise/tasks/setup.sh
  .mise/tasks/check.sh
  .mise/tasks/hooks/install.sh
  .mise/tasks/lint.sh
  .mise/tasks/test.sh
  .mise/tasks/build.sh
  .mise/tasks/release/check.py
  .mise/tasks/security/scan.sh
  .mise/tasks/security/secrets.sh
  .mise/tasks/update/check.py
  .mise/tasks/update/apply.py
)

for task_file in "${required_task_files[@]}"; do
  test -x "$task_file" ||
    {
      printf 'Task is missing or not executable: %s\n' "$task_file" >&2
      exit 1
    }
done

required_config_files=(
  .gitleaks.toml
  .pre-commit-config.yaml
)

for config_file in "${required_config_files[@]}"; do
  test -f "$config_file" ||
    {
      printf 'Configuration file is missing: %s\n' "$config_file" >&2
      exit 1
    }
done

printf 'Setup verified: %s tools, %s tasks, and %s configuration files.\n' \
  "${#required_tools[@]}" \
  "${#required_task_files[@]}" \
  "${#required_config_files[@]}"
