## Running the Energy Assistant

### Preferred method: Home Assistant Add-on

By far the most convenient way to run the Energy Assistant is to install the Energy Assistant Add-on:

1. Add the Energy Assistant repository to your Home Assistant instance.
2. Install the Energy Assistant add-on.

[![Add repository on my Home Assistant][repository-badge]][repository-url]

### Alternative method: Docker image

An alternative way to run the Energy Assistant is by running the docker image:

Copy the energy_assistant.yaml.dist file to energy_assistant.yaml ([link](https://raw.githubusercontent.com/pail23/energy-assistant-backend/main/energy_assistant.yaml.dist)) and modify it to match your setup and then start the docker container in the same folder.

```
docker run --name em -p 8080:5000 -v "$(pwd)/energy_assistant.yaml:/config/energy_assistant.yaml" ghcr.io/pail23/energy-assistant-backend:latest
```

[repository-badge]: https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg
[repository-url]: https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fpail23%2Fenergy-assistant-addon
