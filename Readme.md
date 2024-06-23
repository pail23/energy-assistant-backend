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
docker run --name em -p 8080:5000 -v "$(pwd)/energy_assistant.yaml:/config/energy_assistant.yaml" ghcr.io/pail23/energy-assistant-server:latest
```

## Configure Energy Assistant

Please find information on how to configure Energy Assistant [here](https://pail23.github.io/energy-assistant-backend/config_file.html).

## User documentation

Please consult the user documentation for [Energy Assistant](https://pail23.github.io/energy-assistant-backend/).

[repository-badge]: https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg
[repository-url]: https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fpail23%2Fenergy-assistant-addon

## Local Development

The easiest way to get started with development is to use Visual Studio Code with devcontainers. This approach will create a preconfigured development environment with all the tools you need. This approach is enabled for the Energy Assistant frontend and the Energy Assistant backend repository. [Learn more about devcontainers](https://code.visualstudio.com/docs/devcontainers/containers).

Getting started:

1. Go to [Energy Assistant backend](https://github.com/pail23/energy-assistant-backend) repository and click "fork".
2. Clone the forked repository locally (git clone ...)
3. Open the devcontainer in VSCode
4. Copy `energy_assistan.yaml.dist` to `energy_assistan.yaml` and configure your setup (e.g. connection to Home Assistant)
5. Press F5 to start Energy Assistant
6. Go to [Energy Assistant frontend](https://github.com/pail23/energy-assistant-frontend) repository and click "fork".
7. Clone the forked repository locally (git clone ...)
8. Open the devcontainer in VSCode
9. Enter `yarn install` and then `yarn dev` in the Terminal of VSCode

Useful commands:

`./scripts/lint.sh` run the linter to check the code quality.

`./scripts/create-dev-db.sh` create a new database in the root folder of the project.
