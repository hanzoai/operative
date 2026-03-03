# Operative

Computer use agent powered by Claude. Provides a Docker container environment where Claude interacts with a virtual desktop via screenshot, mouse, and keyboard tools, with a Streamlit UI for human interaction.

**Image**: `ghcr.io/hanzoai/operative:latest`
**Repo**: [github.com/hanzoai/operative](https://github.com/hanzoai/operative)

> **Note**: Computer use is a beta feature. It poses unique risks distinct from standard API features. To minimize risks:
>
> 1. Use a dedicated virtual machine or container with minimal privileges.
> 2. Avoid giving the model access to sensitive data such as account login information.
> 3. Limit internet access to an allowlist of domains.
> 4. Require human confirmation for decisions with real-world consequences.
>
> Instructions found in web content or images may override user instructions. Isolate the agent from sensitive data and actions.

## What It Does

- Runs a full Linux desktop (X11/Xvfb + VNC) inside Docker
- Claude controls the desktop via screenshot/mouse/keyboard tool calls
- Supports Anthropic API (direct), AWS Bedrock, and Google Vertex
- Streamlit UI for sending instructions and watching the agent work
- Built-in bash and file editing tools alongside computer control

## Quick Start

### Anthropic API

```bash
export ANTHROPIC_API_KEY=%your_api_key%
docker run \
    -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
    -v $HOME/.anthropic:/home/operative/.anthropic \
    -p 5900:5900 \
    -p 8501:8501 \
    -p 6080:6080 \
    -p 8080:8080 \
    -it ghcr.io/hanzoai/operative:latest
```

### Bedrock

```bash
export AWS_PROFILE=<your_aws_profile>
docker run \
    -e API_PROVIDER=bedrock \
    -e AWS_PROFILE=$AWS_PROFILE \
    -e AWS_REGION=us-west-2 \
    -v $HOME/.aws:/home/operative/.aws \
    -v $HOME/.anthropic:/home/operative/.anthropic \
    -p 5900:5900 -p 8501:8501 -p 6080:6080 -p 8080:8080 \
    -it ghcr.io/hanzoai/operative:latest
```

### Vertex

```bash
gcloud auth application-default login
export VERTEX_REGION=%your_vertex_region%
export VERTEX_PROJECT_ID=%your_vertex_project_id%
docker run \
    -e API_PROVIDER=vertex \
    -e CLOUD_ML_REGION=$VERTEX_REGION \
    -e ANTHROPIC_VERTEX_PROJECT_ID=$VERTEX_PROJECT_ID \
    -v $HOME/.config/gcloud/application_default_credentials.json:/home/operative/.config/gcloud/application_default_credentials.json \
    -p 5900:5900 -p 8501:8501 -p 6080:6080 -p 8080:8080 \
    -it ghcr.io/hanzoai/operative:latest
```

## Accessing the Interface

Once the container is running, open [http://localhost:8080](http://localhost:8080) for the combined agent chat + desktop view.

The container stores settings (API key, custom system prompt) in `~/.anthropic/`. Mount this directory to persist settings between runs.

| Port | Service |
|------|---------|
| 8080 | Combined interface |
| 8501 | Streamlit UI only |
| 6080 | noVNC desktop only |
| 5900 | VNC (for VNC clients) |

## Screen Size

Set resolution with `WIDTH` and `HEIGHT` environment variables:

```bash
docker run \
    -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
    -e WIDTH=1920 -e HEIGHT=1080 \
    -v $HOME/.anthropic:/home/operative/.anthropic \
    -p 5900:5900 -p 8501:8501 -p 6080:6080 -p 8080:8080 \
    -it ghcr.io/hanzoai/operative:latest
```

XGA resolution (1024x768) is recommended. For higher resolutions, scale screenshots down to XGA and map coordinates back proportionally. For smaller displays, add black padding to reach 1024x768.

## Development

```bash
./setup.sh  # configure venv, install dev dependencies, pre-commit hooks
docker build . -t operative:local
export ANTHROPIC_API_KEY=%your_api_key%
docker run \
    -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
    -v $(pwd)/operative:/home/operative/ \
    -v $HOME/.anthropic:/home/operative/.anthropic \
    -p 5900:5900 -p 8501:8501 -p 6080:6080 -p 8080:8080 \
    -it operative:local
```

The docker run command mounts the repo inside the container with auto-reloading enabled.

## Credits

Based on [Anthropic's computer use demo](https://github.com/anthropics/anthropic-quickstarts/tree/main/computer-use-demo). See upstream repository for original implementation.

## License

MIT
