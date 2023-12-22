ARG TARGETPLATFORM="linux/amd64"
ARG BUILD_VERSION=latest
ARG PYTHON_VERSION="3.11"

FROM python:${PYTHON_VERSION}
WORKDIR /app

COPY ./energy_assistant.yaml.dist /config/energy_assistant.yaml
#COPY ./requirements.txt .
#COPY ./pyproject.toml .
#COPY ./alembic.ini .
#COPY ./app ./app
#COPY ./*.whl .
#COPY ./migrations ./migrations
#COPY ./client ./client

RUN pip install energy-assistant && mkdir /data

# Required to persist build arg
ARG BUILD_VERSION
ARG TARGETPLATFORM

# Set some labels for the Home Assistant add-on
LABEL \
    org.opencontainers.image.title="Energy Assistant" \
    org.opencontainers.image.description="Energy Assistant" \
    org.opencontainers.image.source="https://github.com/pail23/energy-assistant-backend" \
    org.opencontainers.image.authors="The Energy Assistant Team" \
    org.opencontainers.image.documentation="https://github.com/pail23/energy-assistant-backend/discussions" \
    org.opencontainers.image.licenses="MIT" \
    io.hass.version=${BUILD_VERSION} \
    io.hass.name="Energy Assistant" \
    io.hass.description="Energy Assistant" \
    io.hass.platform="${TARGETPLATFORM}" \
    io.hass.type="addon"

VOLUME [ "/data" ]

EXPOSE 5000
ENV APP_CONFIG_FILE=local
CMD eass
