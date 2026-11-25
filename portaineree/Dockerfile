FROM portainer/portainer-ee:2.45.4-alpine@sha256:f92ab4dfcabaaa00594400625e8e66efbb45fff85eb779485c33ec2d9e0b2eeb

ARG BUILD_ARCH
ARG BUILD_VERSION
ARG BUILD_REVISION

LABEL io.hass.arch="${BUILD_ARCH}" \
      io.hass.type="app" \
      io.hass.version="${BUILD_VERSION}" \
      org.opencontainers.image.source="https://github.com/ne1800/hass-portainer-ee" \
      org.opencontainers.image.revision="${BUILD_REVISION}" \
      org.opencontainers.image.version="${BUILD_VERSION}" \
      org.opencontainers.image.title="Portainer BE for Home Assistant OS" \
      org.opencontainers.image.description="Portainer Business Edition app for Home Assistant OS with signed amd64 and arm64 images." \
      org.opencontainers.image.documentation="https://github.com/ne1800/hass-portainer-ee/blob/main/portaineree/DOCS.md" \
      org.opencontainers.image.url="https://github.com/ne1800/hass-portainer-ee" \
      org.opencontainers.image.vendor="ne1800"

RUN apk add --no-cache tzdata

ENTRYPOINT ["/portainer"]
