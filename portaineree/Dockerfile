FROM portainer/portainer-ee:2.45.2-alpine@sha256:859c869c9b1b38ef460970f178534c053cc9c5b064099504ba672338a3372bfb

ARG BUILD_ARCH
ARG BUILD_VERSION

LABEL io.hass.arch="${BUILD_ARCH}" \
      io.hass.type="app" \
      io.hass.version="${BUILD_VERSION}" \
      org.opencontainers.image.source="https://github.com/ne1800/hass-portainer-ee"

RUN apk add --no-cache tzdata

ENTRYPOINT ["/portainer"]
