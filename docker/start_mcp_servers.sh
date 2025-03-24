#!/bin/bash

# Start MCP servers
# /usr/local/bin/hanzo-dev-mcp &
/usr/local/bin/modelcontextprotocol-server-filesystem &
/usr/local/bin/modelcontextprotocol-server-postgres &

echo "MCP servers started successfully"
