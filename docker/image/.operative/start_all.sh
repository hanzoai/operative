#!/bin/bash

set -e

export DISPLAY=:${DISPLAY_NUM:-1}

./xvfb_startup.sh
./tint2_startup.sh
./mutter_startup.sh
./x11vnc_startup.sh

# Start MCP servers
echo "Starting MCP servers..."
/opt/mcp-servers/start_mcp_servers.sh &
