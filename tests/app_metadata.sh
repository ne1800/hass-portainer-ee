#!/usr/bin/env bash
set -euo pipefail

source tests/lib/assert.sh

assert_file repository.yaml
assert_file release.yaml
assert_file update-policy.yaml
assert_file portaineree/config.yaml
assert_file portaineree/Dockerfile
assert_file portaineree/CHANGELOG.md
assert_file portaineree/README.md
assert_file portaineree/icon.png
assert_file portaineree/logo.png

assert_eq "Portainer BE STS" "$(yq -r '.name' repository.yaml)" \
  "Repository name"
assert_eq "ne1800" "$(yq -r '.maintainer' repository.yaml)" \
  "Maintainer"
assert_eq "https://github.com/ne1800/hass-portainer-ee" \
  "$(yq -r '.url' repository.yaml)" "Repository URL"

assert_eq "portaineree" "$(yq -r '.slug' portaineree/config.yaml)" \
  "App slug"
assert_eq "2.44.0.1" "$(yq -r '.version' portaineree/config.yaml)" \
  "App version"
assert_eq '["amd64","aarch64"]' \
  "$(yq -o=json -I=0 '.arch' portaineree/config.yaml)" \
  "Architectures"
assert_eq "ghcr.io/ne1800/hass-portainer-ee" \
  "$(yq -r '.image' portaineree/config.yaml)" "Runtime image"
assert_eq "true" "$(yq -r '.docker_api' portaineree/config.yaml)" \
  "Docker API"
assert_eq "manual" "$(yq -r '.boot' portaineree/config.yaml)" \
  "Boot mode"
assert_eq "false" "$(yq -r '.init' portaineree/config.yaml)" \
  "Init mode"
assert_eq "Portainer Business Edition on the verified STS channel" \
  "$(yq -r '.description' portaineree/config.yaml)" \
  "App description"
assert_eq "Portainer Edge tunnel" \
  "$(yq -r '.ports_description."8000/tcp"' portaineree/config.yaml)" \
  "Edge tunnel port description"
assert_eq "Portainer web UI over HTTP" \
  "$(yq -r '.ports_description."9000/tcp"' portaineree/config.yaml)" \
  "HTTP port description"
assert_eq "Portainer web UI over HTTPS" \
  "$(yq -r '.ports_description."9443/tcp"' portaineree/config.yaml)" \
  "HTTPS port description"

assert_eq "2.44.0.1" "$(yq -r '.app.version' release.yaml)" \
  "Release app version"
assert_eq "2.44.0" "$(yq -r '.portainer.version' release.yaml)" \
  "Portainer version"
assert_eq "STS" "$(yq -r '.portainer.channel' release.yaml)" \
  "Portainer channel"
assert_eq "2.45.0" \
  "$(yq -r '.security_bridges[0].target_version' update-policy.yaml)" \
  "Security bridge"

[[ ! -e config.json ]] || fail "config.json must not be in the repository root"
[[ ! -e Dockerfile ]] || fail "Dockerfile must not be in the repository root"
assert_not_contains portaineree/config.yaml "armv7"
assert_not_contains repository.yaml "@"
