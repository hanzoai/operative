#!/bin/bash

# Simple script to run hanzo-mcp MCP server
# This can be placed in .operative folder to be launched automatically

# Install if not already installed
if ! command -v hanzo-mcp &> /dev/null; then
  echo "Installing hanzo-mcp..."
  pip install hanzo-mcp
fi

# Run the MCP server
hanzo-mcp --allow-path /home/operative "$@"
