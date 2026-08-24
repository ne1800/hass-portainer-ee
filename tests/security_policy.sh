#!/usr/bin/env bash
set -euo pipefail

source tests/lib/assert.sh

assert_file .trivyignore.yaml
assert_file security/accepted-risks.yaml
assert_file .mise/tasks/security/scan.sh
assert_contains .mise/tasks/security/scan.sh "--show-suppressed"
assert_contains .mise/tasks/security/scan.sh "ExperimentalModifiedFindings"
assert_contains .mise/tasks/security/scan.sh \
  "temporary_vulnerability_baseline.source_image"
assert_contains .mise/tasks/security/scan.sh \
  "Recheck and update the baseline before approving the update PR"

expected_findings="$(
  printf '%s\n' \
    'CVE-2025-15558|pkg:golang/github.com/docker/cli@v28.5.1%2Bincompatible' \
    'CVE-2026-17106|pkg:golang/github.com/moby/go-archive@v0.1.0' \
    'CVE-2026-33747|pkg:golang/github.com/moby/buildkit@v0.25.1' \
    'CVE-2026-33748|pkg:golang/github.com/moby/buildkit@v0.25.1' \
    'CVE-2026-33818|pkg:golang/stdlib@v1.26.4' \
    'CVE-2026-39821|pkg:golang/stdlib@v1.26.4' \
    'CVE-2026-39822|pkg:golang/stdlib@v1.26.4' \
    'CVE-2026-41567|pkg:golang/github.com/docker/docker@v28.5.2%2Bincompatible' \
    'CVE-2026-42306|pkg:golang/github.com/docker/docker@v28.5.2%2Bincompatible' \
    'CVE-2026-46600|pkg:golang/stdlib@v1.26.4' \
    'CVE-2026-50163|pkg:golang/oras.land/oras-go/v2@v2.6.1' \
    'CVE-2026-56853|pkg:golang/stdlib@v1.26.4' \
    'CVE-2026-56858|pkg:golang/stdlib@v1.26.4' \
    'CVE-2026-56859|pkg:golang/stdlib@v1.26.4' \
    'CVE-2026-56860|pkg:golang/stdlib@v1.26.4' \
    'CVE-2026-56862|pkg:golang/stdlib@v1.26.4' \
    'CVE-2026-56864|pkg:golang/golang.org/x/mod@v0.37.0' \
    'CVE-2026-56865|pkg:golang/golang.org/x/mod@v0.37.0' \
    'CVE-2026-71556|pkg:golang/github.com/go-git/go-git/v5@v5.19.1' |
    sort
)"

ignored_findings="$(
  yq -r '.vulnerabilities[] | [.id, .purls[0]] | join("|")' \
    .trivyignore.yaml | sort
)"
risk_findings="$(
  yq -r \
    '.accepted_risks[] | select(.kind == "vulnerability") | [.id, .purl] | join("|")' \
    security/accepted-risks.yaml | sort
)"

assert_eq "19" \
  "$(yq -r '.vulnerabilities | length' .trivyignore.yaml)" \
  "Temporary Trivy CVE exception count"
assert_eq "$expected_findings" "$ignored_findings" \
  "Exact Trivy CVE baseline"
assert_eq "$expected_findings" "$risk_findings" \
  "Synchronized risk documentation"
assert_eq "0" \
  "$(yq -r '[.vulnerabilities[] | select((.paths | length) != 1 or .paths[0] != "portainer")] | length' \
    .trivyignore.yaml)" \
  "Path restriction for all CVE exceptions"
assert_eq "0" \
  "$(yq -r '[.vulnerabilities[] | select(.expired_at != "2026-09-30")] | length' \
    .trivyignore.yaml)" \
  "Expiration of all CVE exceptions"
assert_eq "0" \
  "$(yq -r '[.vulnerabilities[] | select(.statement == null or .statement == "")] | length' \
    .trivyignore.yaml)" \
  "Rationale for all CVE exceptions"
assert_eq "0" \
  "$(yq -r '[.accepted_risks[] | select(.kind == "vulnerability") | select(.severity != "HIGH" or .expires_on != "2026-09-30" or .rationale == null or .rationale == "")] | length' \
    security/accepted-risks.yaml)" \
  "Documentation of temporary HIGH risks"

assert_eq "19" \
  "$(yq -r '.temporary_vulnerability_baseline.finding_count' \
    security/accepted-risks.yaml)" \
  "Documented finding count"
assert_eq "local/hass-portainer-ee:$(yq -r '.app.version' release.yaml)" \
  "$(yq -r '.temporary_vulnerability_baseline.source_image' \
    security/accepted-risks.yaml)" \
  "Image binding of the documented security baseline"
assert_eq "2026-09-30" \
  "$(yq -r '.temporary_vulnerability_baseline.expires_on' \
    security/accepted-risks.yaml)" \
  "Documented expiration date"
for condition in \
  private_network_only \
  administrator_only \
  trusted_git_sources_only \
  trusted_images_only; do
  assert_eq "true" \
    "$(yq -r ".temporary_vulnerability_baseline.operating_conditions.${condition}" \
      security/accepted-risks.yaml)" \
    "Operating condition $condition"
done

assert_eq "1" \
  "$(yq -r '.misconfigurations | length' .trivyignore.yaml)" \
  "Trivy misconfiguration exception count"
assert_eq "AVD-DS-0002" \
  "$(yq -r '.misconfigurations[0].id' .trivyignore.yaml)" \
  "Trivy exception"
assert_eq '["portaineree/Dockerfile"]' \
  "$(yq -o=json -I=0 '.misconfigurations[0].paths' .trivyignore.yaml)" \
  "Path restriction"
assert_eq "1" \
  "$(yq -r '[.accepted_risks[] | select(.id == "AVD-DS-0002")] | length' \
    security/accepted-risks.yaml)" \
  "Documented root exception"
assert_eq "$(yq -r '.app.version' release.yaml)" \
  "$(yq -r '.accepted_risks[] | select(.id == "AVD-DS-0002") | .affected_version' \
    security/accepted-risks.yaml)" \
  "App binding of the root exception"
open_advisory_count="$(
  yq -r '[.accepted_risks[] | select(.id == "GHSA-jxhm-qq8x-v4c6")] | length' \
    security/accepted-risks.yaml
)"
resolved_advisory_count="$(
  yq -r '[.resolved_advisories[]? | select(.id == "GHSA-jxhm-qq8x-v4c6")] | length' \
    security/accepted-risks.yaml
)"
if [[ "$open_advisory_count" == "1" ]]; then
  assert_eq "0" "$resolved_advisory_count" \
    "Unresolved Portainer advisory"
else
  assert_eq "0" "$open_advisory_count" \
    "Removed Portainer advisory"
  assert_eq "1" "$resolved_advisory_count" \
    "Documented resolution of the Portainer advisory"
  assert_eq "2.45.0" \
    "$(yq -r '.resolved_advisories[] | select(.id == "GHSA-jxhm-qq8x-v4c6") | .fixed_in' \
      security/accepted-risks.yaml)" \
    "Fixed version of the Portainer advisory"
fi
