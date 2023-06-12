FROM nginx:stable-alpine
WORKDIR /app
RUN apk update && apk add --no-cache python3 && \
    python3 -m ensurepip && \
    rm -r /usr/lib/python*/ensurepip && \
    pip3 install --upgrade pip setuptools && \
    if [ ! -e /usr/bin/pip ]; then ln -s pip3 /usr/bin/pip ; fi && \
    if [[ ! -e /usr/bin/python ]]; then ln -sf /usr/bin/python3 /usr/bin/python; fi && \
    rm -r /root/.cache
RUN apk update && apk add gcc python3-dev musl-dev

COPY ./energy_assistant.yaml.dist /config/energy_assistant.yaml
COPY ./requirements.txt .
COPY ./alembic.ini .

RUN pip install -r requirements.txt

RUN mkdir /data

COPY ./app ./app
COPY ./migrations ./migrations
COPY ./client ./client


EXPOSE 5000
ENV APP_CONFIG_FILE=local
CMD alembic upgrade head && uvicorn --host 0.0.0.0 --port 5000 app.app:app
#CMD gunicorn --bind 0.0.0.0:5000 --worker-class aiohttp.GunicornWebWorker app:init_app --daemon && nginx -g 'daemon off;'
