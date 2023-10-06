# Energy Assistant

Energy Assistant is a free, opensource Energy Management System which works together with [Home Assistant](https://www.home-assistant.io/) and [Evcc](https://evcc.io/).

Energy Assistant is using [Emhass](https://emhass.readthedocs.io/en/latest/) in order to optimize the energy consumption of your house.

**Documentation and support**

For issues, please go to [the issue tracker](https://github.com/pail23/energy-assistant-backend/issues).

For feature requests, please see [feature requests](https://github.com/pail23/energy-assistant-backend/discussions/categories/feature-requests-and-ideas).

## Running the Energy Assistant

### Preferred method: Home Assistant Add-on

By far the most convenient way to run the Energy Assistant is to install the Energy Assistant Add-on:

1. Add the Energy Assistant repository to your Home Assistant instance.
2. Install the Energy Assistant add-on.

[![Add repository on my Home Assistant][repository-badge]][repository-url]

### Alternative method: Docker image

An alternative way to run the Energy Assistant is by running the docker image:

Copy the `energy_assistant.yaml.dist` file to `energy_assistant.yaml` and modify it to match your setup and then start the docker container in the same folder.

```
docker run --name em -p 8080:5000 -v "$(pwd)/energy_assistant.yaml:/config/energy_assistant.yaml" ghcr.io/pail23/energy-assistant-backend:latest
```

## Configure Energy Assistant

Please find information on how to configure Energy Assistant [here](https://pail23.github.io/energy-assistant-backend/config_file.html).

## User documentation

Please consult the user documentation for [Energy Assistant](https://pail23.github.io/energy-assistant-backend/).

[repository-badge]: https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg
[repository-url]: https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fpail23%2Fenergy-assistant-addon
