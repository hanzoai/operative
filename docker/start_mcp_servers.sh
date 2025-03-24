#!/bin/bash

# Run the hanzo-dev-mcp setup script if needed
if [ ! -f "/etc/systemd/system/hanzo-dev-mcp.service" ]; then
  echo "Setting up hanzo-dev-mcp..."
  /opt/mcp-servers/hanzo-dev-mcp-setup.sh
fi

# Start MCP servers
# If systemd service exists, use it; otherwise start manually
if [ -f "/etc/systemd/system/hanzo-dev-mcp.service" ]; then
  systemctl start hanzo-dev-mcp.service
else
  # Fallback to manual start
  /opt/mcp-servers/hanzo-dev-mcp-bin --allowed-paths /home/operative &
fi

/usr/local/bin/modelcontextprotocol-server-filesystem --allow-paths /home/operative &
/usr/local/bin/modelcontextprotocol-server-postgres &

echo "MCP servers started successfully"

# Wait a moment to ensure servers are started
sleep 2

# Check if hanzo-dev-mcp is running
if pgrep -f "hanzo-dev-mcp" > /dev/null; then
  echo "hanzo-dev-mcp is running"
else
  echo "WARNING: hanzo-dev-mcp failed to start"
fi
