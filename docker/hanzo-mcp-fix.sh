#!/bin/bash

# Fix the permissions issue with hanzo-mcp install
# Run with user permissions, not as root

# Install hanzo-mcp if not already installed
if ! command -v hanzo-mcp &> /dev/null; then
  echo "Installing hanzo-mcp..."
  mkdir -p ~/.local/bin
  pip install --user hanzo-mcp
fi

# Add to PATH if not already there
if ! echo $PATH | grep -q "$HOME/.local/bin"; then
  echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
fi

# Run the MCP server with proper permissions
hanzo-mcp --allow-path $(pwd) "$@"
