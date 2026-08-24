FROM portainer/portainer-ee:2.44.0-alpine@sha256:dbb2ae19e5e690105b087201c12f78b7f0c7e8a4694094258105fe040cc18b32

ARG BUILD_ARCH
ARG BUILD_VERSION

LABEL io.hass.arch="${BUILD_ARCH}" \
      io.hass.type="app" \
      io.hass.version="${BUILD_VERSION}" \
      org.opencontainers.image.source="https://github.com/ne1800/hass-portainer-ee"

RUN apk add --no-cache tzdata

ENTRYPOINT ["/portainer"]
