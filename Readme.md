## Running the container from github registry
docker run --name em -p 8080:80 -v "$(pwd)/config.yaml:/config/config.yaml" ghcr.io/pail23/energy-assistant-backend:latest

## show all data for one device
flask --app app/manage.py show-data 'Stadel 15'