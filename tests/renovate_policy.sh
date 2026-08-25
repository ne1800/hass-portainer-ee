#!/usr/bin/env bash
set -euo pipefail

source tests/lib/assert.sh

assert_file renovate.json
jq empty renovate.json

assert_eq "false" "$(jq -r '.automerge' renovate.json)" \
  "Global Renovate automerge"
assert_eq '["dockerfile","github-actions","mise","pep621","pre-commit"]' \
  "$(jq -c '.enabledManagers | sort' renovate.json)" \
  "Enabled Renovate managers"
assert_eq "true" "$(jq -r '.["pre-commit"].enabled' renovate.json)" \
  "Renovate pre-commit manager opt-in"
assert_eq "true" "$(jq -r '.lockFileMaintenance.enabled' renovate.json)" \
  "Lock file maintenance"
assert_eq '["before 6am on Monday"]' \
  "$(jq -c '.schedule' renovate.json)" \
  "Renovate schedule"
assert_eq "Europe/Berlin" "$(jq -r '.timezone' renovate.json)" \
  "Renovate timezone"
assert_eq "true" "$(jq -r '.dependencyDashboard' renovate.json)" \
  "Dependency Dashboard"
assert_eq "1" \
  "$(
    jq -r \
      '[.packageRules[] | select((.matchUpdateTypes // []) | index("major")) | select(.dependencyDashboardApproval == true)] | length' \
      renovate.json
  )" \
  "Dashboard approval for major updates"

assert_eq "1" \
  "$(
    jq -r \
      '[.packageRules[] | select((.matchManagers // []) | index("pep621")) | select((.matchUpdateTypes // []) | index("minor")) | select((.matchUpdateTypes // []) | index("patch")) | select(.groupName == "Python tooling")] | length' \
      renovate.json
  )" \
  "Grouped Python tooling updates"

assert_eq "1" \
  "$(
    jq -r \
      '[.packageRules[] | select((.matchManagers // []) | index("pre-commit")) | select((.matchUpdateTypes // []) | index("minor")) | select((.matchUpdateTypes // []) | index("patch")) | select(.groupName == "Prek hooks")] | length' \
      renovate.json
  )" \
  "Grouped Prek hook updates"

portainer_rule_count="$(
  jq -r \
    '[.packageRules[] | select((.matchDatasources // []) | index("docker")) | select((.matchPackageNames // []) | index("portainer/portainer-ee"))] | length' \
    renovate.json
)"
assert_eq "2" "$portainer_rule_count" "Portainer rule count"

version_rule_index="$(
  jq -r \
    '.packageRules | to_entries | map(select((.value.matchPackageNames // []) | index("portainer/portainer-ee")) | select((.value.matchUpdateTypes // []) | index("major"))) | .[0].key' \
    renovate.json
)"
digest_rule_index="$(
  jq -r \
    '.packageRules | to_entries | map(select((.value.matchPackageNames // []) | index("portainer/portainer-ee")) | select((.value.matchUpdateTypes // []) | index("digest"))) | .[0].key' \
    renovate.json
)"
[[ "$version_rule_index" =~ ^[0-9]+$ ]] ||
  fail "Portainer version block is missing"
[[ "$digest_rule_index" =~ ^[0-9]+$ ]] ||
  fail "Portainer digest rule is missing"
((digest_rule_index > version_rule_index)) ||
  fail "Portainer digest rule must follow the version block"

merged_portainer_field() {
  local update_type="$1"
  local field="$2"
  jq -r \
    --arg update_type "$update_type" \
    --arg field "$field" '
      reduce (
        .packageRules[] |
        select((.matchDatasources // []) | index("docker")) |
        select((.matchPackageNames // []) | index("portainer/portainer-ee")) |
        select((.matchUpdateTypes // []) | index($update_type))
      ) as $rule (
        {
          "enabled": true,
          "automerge": false,
          "dependencyDashboardApproval": false
        };
        .enabled = (
          if $rule | has("enabled") then $rule.enabled else .enabled end
        ) |
        .automerge = (
          if $rule | has("automerge") then $rule.automerge else .automerge end
        ) |
        .dependencyDashboardApproval = (
          if $rule | has("dependencyDashboardApproval") then
            $rule.dependencyDashboardApproval
          else
            .dependencyDashboardApproval
          end
        )
      ) |
      .[$field]
    ' renovate.json
}

for update_type in major minor patch pin pinDigest; do
  assert_eq "false" \
    "$(merged_portainer_field "$update_type" enabled)" \
    "Portainer $update_type remains disabled"
done

assert_eq "true" "$(merged_portainer_field digest enabled)" \
  "Portainer digest updates"
assert_eq "true" \
  "$(merged_portainer_field digest dependencyDashboardApproval)" \
  "Dashboard approval for Portainer digest"
assert_eq "false" "$(merged_portainer_field digest automerge)" \
  "No automerge for Portainer digest"
