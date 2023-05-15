## Running the container from github registry
docker run --name em -p 8080:80 -v "$(pwd)/config.yaml:/config/config.yaml" ghcr.io/pail23/energy-assistant-backend:latest