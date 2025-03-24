#!/bin/bash

# This script installs and configures the hanzo-dev-mcp server

# Create NPM package directory
mkdir -p /opt/mcp-servers
cd /opt/mcp-servers

# Create package.json if it doesn't exist
if [ ! -f "package.json" ]; then
  npm init -y
fi

# Install hanzo-dev-mcp
npm install --save hanzo-dev-mcp

# Create executable script
cat > /opt/mcp-servers/hanzo-dev-mcp-bin << 'EOL'
#!/bin/bash

NODE_PATH=/opt/mcp-servers/node_modules node /opt/mcp-servers/node_modules/hanzo-dev-mcp/dist/server.js --allowed-paths /home/operative "$@"
EOL

chmod +x /opt/mcp-servers/hanzo-dev-mcp-bin

# Create systemd service file
cat > /etc/systemd/system/hanzo-dev-mcp.service << 'EOL'
[Unit]
Description=Hanzo Dev MCP Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/mcp-servers
ExecStart=/opt/mcp-servers/hanzo-dev-mcp-bin
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=hanzo-dev-mcp

[Install]
WantedBy=multi-user.target
EOL

# Create startup script
cat > /opt/mcp-servers/start-hanzo-mcp.sh << 'EOL'
#!/bin/bash

# Start hanzo-dev-mcp in the background
/opt/mcp-servers/hanzo-dev-mcp-bin &

# Wait and verify it's running
sleep 2
pgrep -f "hanzo-dev-mcp" > /dev/null && echo "hanzo-dev-mcp started successfully" || echo "Failed to start hanzo-dev-mcp"
EOL

chmod +x /opt/mcp-servers/start-hanzo-mcp.sh

echo "hanzo-dev-mcp server installed and configured"
