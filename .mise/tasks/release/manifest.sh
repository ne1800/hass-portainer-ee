#!/usr/bin/env bash
set -euo pipefail
#MISE description="Verify signed native release images and publish the final manifest"

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"
mise run release:check -- --release-tag "${GITHUB_REF_NAME:?Release tag is required}"
version="$(yq -r '.app.version' release.yaml)"
revision="$(git rev-parse HEAD)"
target="ghcr.io/ne1800/hass-portainer-ee:${version}"
identity="https://github.com/ne1800/hass-portainer-ee/.github/workflows/release.yml@refs/tags/v${version}"
description="Portainer Business Edition app for Home Assistant OS with signed amd64 and arm64 images."
source_images=()

for arch in amd64 aarch64; do
  source_tag="ghcr.io/ne1800/${arch}-hass-portainer-ee:${version}"
  digest="$(regctl image digest "$source_tag")"
  [[ "$digest" =~ ^sha256:[0-9a-f]{64}$ ]] || {
    printf 'Invalid native image digest.\n' >&2
    exit 1
  }
  source_image="${source_tag%:*}@${digest}"
  cosign verify \
    --certificate-identity "$identity" \
    --certificate-oidc-issuer https://token.actions.githubusercontent.com \
    "$source_image" >/dev/null
  oci_arch="$arch"
  [[ "$arch" != "aarch64" ]] || oci_arch=arm64
  config="$(regctl image config "$source_image" --platform "linux/${oci_arch}" --format '{{json .}}')"
  jq -e --arg arch "$arch" --arg oci_arch "$oci_arch" \
    --arg version "$version" --arg revision "$revision" '
    .architecture == $oci_arch and .os == "linux" and
    .config.Labels["io.hass.arch"] == $arch and
    .config.Labels["io.hass.version"] == $version and
    .config.Labels["org.opencontainers.image.revision"] == $revision and
    .config.Labels["org.opencontainers.image.source"] == "https://github.com/ne1800/hass-portainer-ee"
  ' <<<"$config" >/dev/null
  mise run security:scan -- "$source_image" "linux/${oci_arch}"
  source_images+=("$source_image")
done

# Recheck immediately before the only write to the public app reference.
registry_error="$(mktemp)"
trap 'unlink "$registry_error"' EXIT
if regctl manifest head "$target" >/dev/null 2>"$registry_error"; then
  printf 'Target reference already exists: %s\n' "$target" >&2
  exit 1
fi
if ! grep -Fq '[http 404]' "$registry_error"; then
  printf 'Could not establish that the manifest tag is unused.\n' >&2
  exit 1
fi

docker-cli-plugin-docker-buildx imagetools create \
  --annotation "index:org.opencontainers.image.description=${description}" \
  --annotation "index:org.opencontainers.image.source=https://github.com/ne1800/hass-portainer-ee" \
  --annotation "index:org.opencontainers.image.revision=${revision}" \
  --tag "$target" \
  "${source_images[@]}"
digest="$(regctl image digest "$target")"
[[ "$digest" =~ ^sha256:[0-9a-f]{64}$ ]]
cosign sign --yes "${target%:*}@${digest}"
