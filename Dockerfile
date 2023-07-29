ARG TARGETPLATFORM="linux/amd64"
ARG BUILD_VERSION=latest
ARG PYTHON_VERSION="3.11"

FROM python:3.11
WORKDIR /app

COPY ./energy_assistant.yaml.dist /config/energy_assistant.yaml
COPY ./requirements.txt .
COPY ./alembic.ini .

RUN pip install -r requirements.txt

RUN mkdir /data

COPY ./app ./app
COPY ./migrations ./migrations
COPY ./client ./client

# Required to persist build arg
ARG BUILD_VERSION
ARG TARGETPLATFORM

# Set some labels for the Home Assistant add-on
LABEL \
    io.hass.version=${BUILD_VERSION} \
    io.hass.name="Energy Assistant" \
    io.hass.description="Energy Assistant" \
    io.hass.platform="${TARGETPLATFORM}" \
    io.hass.type="addon"

VOLUME [ "/data" ]

EXPOSE 5000
ENV APP_CONFIG_FILE=local
CMD alembic upgrade head && uvicorn --host 0.0.0.0 --port 5000 app.main:app
#CMD gunicorn --bind 0.0.0.0:5000 --worker-class aiohttp.GunicornWebWorker app:init_app --daemon && nginx -g 'daemon off;'
