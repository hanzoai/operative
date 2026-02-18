# Operative

Claude computer use agent. Provides a Docker container environment where Claude can interact with a desktop via screenshot/mouse/keyboard tools, with a Streamlit UI for human interaction.

- **Repo**: https://github.com/hanzoai/operative
- **Images**: `ghcr.io/hanzoai/operative`, `ghcr.io/hanzoai/desktop`, `ghcr.io/hanzoai/xvfb`

## Stack

- Python 3.13+, Streamlit
- Anthropic API (direct, Bedrock, Vertex)
- Docker (Ubuntu 22.04 base)
- X11/Xvfb + VNC + tint2/mutter
- uv for dependency management

## Architecture

```
User -> Streamlit UI -> Claude API -> Tool calls -> Container environment
                                                      ├── Computer (screenshot/mouse/keyboard)
                                                      ├── Bash (shell commands)
                                                      └── Edit (file editing)
```

### Core Modules

| File | Purpose |
|------|---------|
| `operative/operative.py` | Streamlit UI entrypoint |
| `operative/loop.py` | Agent sampling loop (Claude API interaction) |
| `operative/prompt.py` | System prompt with tool instructions |
| `operative/tools/computer.py` | Screen, keyboard, mouse interaction |
| `operative/tools/bash.py` | Shell command execution |
| `operative/tools/edit.py` | File editing |
| `operative/tools/base.py` | Base tool classes |
| `operative/tools/collection.py` | Tool collection management |
| `operative/tools/groups.py` | Tool versioning and grouping |

### Tool Versions

- `computer_use_20241022`: Claude 3.5 Sonnet (basic mouse/keyboard/screenshot)
- `computer_use_20250124`: Claude 3.7 Sonnet (adds scroll, key hold, mouse down/up, wait, triple-click)

### Docker Images

| Dockerfile | Image | Purpose |
|-----------|-------|---------|
| `docker/Dockerfile` | `operative:latest` | Base with minimal deps |
| `docker/Dockerfile.desktop` | `desktop:latest` | Full desktop environment |
| `docker/Dockerfile.xvfb` | `xvfb:latest` | Headless with Xvfb |

### Ports

| Port | Service |
|------|---------|
| 5900 | VNC |
| 8501 | Streamlit UI |
| 6080 | noVNC web |
| 8080 | HTTP |

## Commands

```bash
# Setup
make setup          # Python env with uv
make install-dev    # Dev dependencies

# Run
make dev            # Docker with local code mounted
make run            # Run locally with uv
make run-docker     # Run Docker container

# Build
make build          # Build operative image (depends on xvfb)
make build-desktop  # Build desktop image
make build-xvfb     # Build xvfb base image

# Test
make test           # Run tests
make test-cov       # Tests with coverage
make lint           # Ruff linting
make format         # Code formatting

# Push
make push           # Push operative to GHCR
make push-desktop   # Push desktop to GHCR
```

## Authentication

- **Anthropic**: `ANTHROPIC_API_KEY` env var
- **Bedrock**: AWS credentials (profile or access keys)
- **Vertex**: GCP credentials

## Token Optimization

- Limits recent screenshots sent to model
- Optional `token-efficient tools` beta flag
- Prompt caching for repetitive elements
- Extended output (128K) with Claude 3.7

## MCP Servers (in container)

- `hanzo-dev-mcp`: Primary MCP server
- `modelcontextprotocol-server-filesystem`: File access
- `modelcontextprotocol-server-git`: Git operations
- `mcp-server-commands`: Shell commands
- `mcp-text-editor`: Text editing

## CI/CD

- `tests.yml`: Tests + linting on push/PR
- `release.yml`: Build and publish Docker images to GHCR

## Rules for AI Assistants

1. ALWAYS update LLM.md with significant discoveries
2. NEVER commit symlinked files (.AGENTS.md, CLAUDE.md, etc.) -- they are in .gitignore
3. NEVER create random summary files -- update THIS file
