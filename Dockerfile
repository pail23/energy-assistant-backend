ARG PYTHON_VERSION="3.11@sha256:3cd9b520be95c671135ea1318f32be6912876024ee16d0f472669d3878801651"


FROM python:${PYTHON_VERSION}
WORKDIR /

# Required to persist build arg
ARG TARGETPLATFORM
ARG EASS_VERSION

COPY ./energy_assistant.yaml.dist /config/energy_assistant.yaml
#COPY ./requirements.txt .
#COPY ./pyproject.toml .
#COPY ./alembic.ini .
#COPY ./app ./app
#COPY ./*.whl .
#COPY ./migrations ./migrations
#COPY ./client ./client

RUN pip install energy-assistant==${EASS_VERSION} && mkdir /data


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
ENV APP_CONFIG_FILE=local
CMD eass
