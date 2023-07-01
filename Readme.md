## Running the container from github registry

docker run --name em -p 8080:5000 -v "$(pwd)/energy_assistant.yaml:/config/energy_assistant.yaml" ghcr.io/pail23/energy-assistant-backend:latest
