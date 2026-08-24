#!/usr/bin/env bash
set -euo pipefail
#MISE description="Build the Portainer app for the local architecture"

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

docker_arch="$(docker info --format '{{.Architecture}}')"
case "$docker_arch" in
  amd64 | x86_64)
    build_arch="amd64"
    ;;
  arm64 | aarch64)
    build_arch="aarch64"
    ;;
  *)
    printf 'Unsupported local Docker architecture: %s\n' \
      "$docker_arch" >&2
    exit 1
    ;;
esac

app_version="$(yq -r '.app.version' release.yaml)"
local_image="local/hass-portainer-ee:${app_version}"

docker-cli-plugin-docker-buildx build \
  --load \
  --pull \
  --build-arg "BUILD_ARCH=${build_arch}" \
  --build-arg "BUILD_VERSION=${app_version}" \
  --tag "$local_image" \
  portaineree

docker image inspect "$local_image" >/dev/null
printf 'Built local image: %s (%s).\n' "$local_image" "$build_arch"
