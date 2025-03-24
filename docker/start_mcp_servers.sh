#!/bin/bash

# Setup hanzo-dev-mcp if not already done
if [ ! -f "/opt/mcp-servers/hanzo-dev-mcp-bin" ]; then
  echo "Setting up hanzo-dev-mcp..."
  /opt/mcp-servers/hanzo-dev-mcp-setup.sh
fi

# Start hanzo-dev-mcp directly (don't use systemd in containers)
/opt/mcp-servers/hanzo-dev-mcp-bin &

# Give the server time to start
sleep 2

# Verify it's running
if pgrep -f "hanzo-dev-mcp" > /dev/null; then
  echo "✅ hanzo-dev-mcp is running"
else
  echo "❌ WARNING: hanzo-dev-mcp failed to start"
fi
