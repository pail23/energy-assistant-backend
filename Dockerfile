ARG PYTHON_VERSION="3.12"


FROM python:${PYTHON_VERSION}
COPY --from=ghcr.io/astral-sh/uv /uv /uvx /bin/
ENV PATH=/root/.local/bin:$PATH
ENV APP_CONFIG_FILE=local

WORKDIR /

# Required to persist build arg
ARG TARGETPLATFORM
ARG EASS_VERSION

COPY ./energy_assistant.yaml.dist /config/energy_assistant.yaml


RUN uv tool install --index-strategy unsafe-best-match energy-assistant==${EASS_VERSION} && mkdir /data


# Set some labels for the Home Assistant add-on
LABEL \
    org.opencontainers.image.title="Energy Assistant" \
    org.opencontainers.image.description="Energy Assistant" \
    org.opencontainers.image.source="https://github.com/pail23/energy-assistant-backend" \
    org.opencontainers.image.authors="The Energy Assistant Team" \
    org.opencontainers.image.documentation="https://github.com/pail23/energy-assistant-backend/discussions" \
    org.opencontainers.image.licenses="MIT" \
    io.hass.version=${EASS_VERSION} \
    io.hass.name="Energy Assistant" \
    io.hass.description="Energy Assistant" \
    io.hass.platform="${TARGETPLATFORM}" \
    io.hass.type="addon"

VOLUME [ "/data" ]

EXPOSE 5000
CMD eass
