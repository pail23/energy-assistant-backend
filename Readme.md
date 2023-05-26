## Running the container from github registry

docker run --name em -p 8080:80 -v "$(pwd)/energy_assistant.yaml:/config/energy_assistant.yaml" ghcr.io/pail23/energy-assistant-backend:latest

## show all data for one device

flask --app app/manage.py show-data 'Stadel 15'

gunicorn -b 0.0.0.0:5000 --worker-class aiohttp.GunicornWebWorker app:init_app
