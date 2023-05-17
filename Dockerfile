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
COPY ./client /usr/share/nginx/html
COPY ./nginx/default.conf /etc/nginx/conf.d/default.conf
COPY ./energy_assistant.yaml.dist /config/energy_assistant.yaml
COPY ./requirements.txt .
RUN pip install -r requirements.txt
RUN pip install gunicorn
COPY ./app .
EXPOSE 80
CMD gunicorn -b 0.0.0.0:5000 app:app --daemon && nginx -g 'daemon off;' 
