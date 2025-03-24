# Operative - Developer Documentation

## Project Overview

Operative is a reference implementation for Claude's computer use capabilities. It enables Claude to interact with a computer environment through a set of tools, providing the following features:

- A Docker container with all necessary dependencies
- An agent loop using Anthropic API, Bedrock, or Vertex to access Claude 3.5/3.7 Sonnet
- Implementation of Anthropic-defined computer use tools
- A Streamlit app for user interaction with the agent

## Architecture

### Core Components

1. **Main Modules**
   - `operative.py`: Entrypoint and Streamlit UI interface
   - `loop.py`: Agent sampling loop for Claude API interaction
   - `prompt.py`: System prompt for Claude with tool instructions
   - `tools/`: Tool implementations for computer interaction

2. **Tool Structure**
   - `tools/base.py`: Base tool classes and common functionality
   - `tools/computer.py`: Screen, keyboard, and mouse interaction
   - `tools/bash.py`: Shell command execution
   - `tools/edit.py`: File editing capabilities
   - `tools/collection.py`: Tool collection management
   - `tools/groups.py`: Tool versioning and grouping

3. **API Support**
   - Anthropic API (direct)
   - AWS Bedrock
   - Google Vertex AI

4. **Container Components**
   - X11 environment with Xvfb
   - Lightweight desktop environment (tint2)
   - VNC server for remote viewing
   - Web interface combining Streamlit and desktop view

### Data Flow

1. User inputs instructions via Streamlit interface
2. Instructions are sent to Claude via the API
3. Claude generates response, potentially including tool calls
4. Tool calls are executed in the container environment
5. Results (including screenshots) are returned to Claude
6. Claude interprets results and continues the interaction

## Implementation Details

### Tool Versions

The project supports two tool versions:
- `computer_use_20241022`: Initial version for Claude 3.5 Sonnet
- `computer_use_20250124`: Enhanced version for Claude 3.7 Sonnet with additional actions

### Computer Tool

The computer tool allows Claude to:
- Take screenshots of the display
- Move the mouse cursor
- Perform mouse clicks (left, right, middle, double)
- Type text or send key combinations
- Drag items with the mouse
- Get cursor position

The newer version adds features like:
- Mouse down/up actions for more complex interactions
- Scrolling capability
- Key holding
- Waiting (pausing) for interface elements
- Triple-click actions

### Screen Resolution Handling

The implementation includes scaling logic to handle different screen resolutions:
- XGA/WXGA resolutions are recommended for optimal performance
- Coordinates can be scaled between the actual screen size and the optimal size
- Image scaling is performed to provide Claude with appropriately sized screenshots

### Thinking Capability

Claude 3.7 Sonnet supports a "thinking" capability that allows for more detailed reasoning:
- Enabled via the `thinking_budget` parameter
- Thinking content is displayed in a separate tab in the UI
- Streaming of thinking content for real-time feedback

### Token Efficiency

Several optimizations are implemented to manage token usage:
- Limiting the number of recent screenshots sent to the model
- Optional token-efficient tools beta flag
- Prompt caching to reduce token consumption for repetitive elements

## Development Environment

### Requirements

- Python 3.13+
- Docker
- uv (Python packaging tool)

### Setup

The project uses `uv` for dependency management and virtual environments:

```bash
# Set up development environment
./setup.sh  # Configure venv, install dependencies, and set up pre-commit hooks

# Alternatively, use the Makefile
make setup  # Set up Python environment with uv
make install-dev  # Install development dependencies
```

### Available Make Commands

```bash
# Development
make dev      # Run with local code mounted
make run      # Run locally using uv

# Docker operations
make build    # Build the Docker image
make push     # Push the Docker image to registry
make run-docker  # Run the Docker container

# Testing
make test     # Run tests
make test-cov # Run tests with coverage
make lint     # Run linting
make format   # Format code
```

## Testing Framework

The project uses pytest with asyncio support for testing asynchronous code:

```bash
# Run all tests
make test

# Run tests with coverage
make test-cov
```

Test files mirror the project structure:
- `tests/loop_test.py`: Tests for the agent loop
- `tests/tools/*.py`: Tests for individual tools

Testing approach:
- Mock objects for simulating API responses
- AsyncMock for asynchronous function testing
- Parametrized fixtures for testing multiple implementations
- Isolated tests for each tool function

## Docker Container

The container is based on Ubuntu 22.04 and includes:

### Desktop Environment
- Xvfb for headless operation
- tint2 as a lightweight desktop environment
- mutter for window management
- x11vnc for VNC access

### Development Tools
- Languages: Python, Node.js, Go, Rust, PHP, .NET, R, Ruby, Scala, Dart, Julia, Zig, Java
- Editors: VS Code, Neovim, Emacs with Spacemacs
- Terminal tools: ripgrep, fd-find, jq, fzf, bat, tmux, glow, curlie
- Databases: SQLite, PostgreSQL, MariaDB, MongoDB, Redis
- ML libraries: PyTorch, NumPy, Pandas, Scikit-learn, JupyterLab

### GUI Applications
- Browsers: Firefox ESR, Chromium
- Office: LibreOffice
- Text editors: Gedit
- File manager: PCManFM
- Utilities: Galculator, Xpaint

### Container Options

The project provides multiple Docker image variations:
- `Dockerfile`: Base image with minimal dependencies
- `Dockerfile.desktop`: Full desktop environment
- `Dockerfile.xvfb`: Headless environment with Xvfb

## API Integration

### Anthropic API

The project uses the AsyncAnthropic client for communication with the Anthropic API, supporting:
- Streamed responses for real-time feedback
- Beta features for computer use
- Prompt caching for optimization
- Support for extended output tokens (128K) with Claude 3.7

### Authentication

Different authentication methods are supported depending on the API provider:
- Anthropic: API key
- Bedrock: AWS credentials (profile or access keys)
- Vertex: Google Cloud credentials

## MCP Servers

MCP (Model Context Protocol) servers extend Claude's capabilities. The container includes:
- hanzo-dev-mcp: Primary MCP server
- modelcontextprotocol-server-filesystem: File access
- modelcontextprotocol-server-git: Git operations
- mcp-server-commands: Shell command execution
- mcp-text-editor: Text editing

## CI/CD

The project uses GitHub Actions for CI/CD:

### Workflows
- `tests.yml`: Runs tests and linting on push to main and pull requests
- `release.yml`: Builds and publishes Docker images

### Testing Process
1. Checkout code
2. Set up Python 3.13
3. Install dependencies with uv
4. Run tests with pytest
5. Run linting with ruff

## Security Considerations

Computer use capabilities introduce unique security risks:
- The container provides isolation from the host system
- Warning messages remind users about potential risks
- Interaction with web content requires caution due to potential prompt injection
- The implementation recommends limiting internet access and sensitive data exposure

## Debugging and Monitoring

The UI provides several debugging features:
- HTTP Logs tab to monitor API requests and responses
- Thinking Logs tab to track Claude's reasoning
- Tool outputs displayed inline in the conversation
- Error messages from tool execution shown in the UI

## Common Issues and Solutions

### Screen Resolution Problems
- Set `WIDTH` and `HEIGHT` environment variables to match your needs
- Enable scaling for better model performance with high resolutions
- Use standard resolutions (XGA/WXGA) for optimal model interaction

### Authentication Issues
- For Anthropic: Check API key validity and quotas
- For Bedrock: Verify AWS credentials and region
- For Vertex: Check GCP credentials and project access

### Tool Execution Failures
- Check container logs for Xvfb or X11 errors
- Verify command permissions within the container
- Check for missing dependencies for specific actions
