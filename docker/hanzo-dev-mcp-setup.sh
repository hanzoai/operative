#!/bin/bash

# This script installs the hanzo-dev-mcp server

# Clone the repository
if [ ! -d "/opt/mcp-servers/hanzo-dev-mcp" ]; then
  echo "Cloning hanzo-dev-mcp repository..."
  mkdir -p /opt/mcp-servers/hanzo-dev-mcp
  git clone https://github.com/hanzoai/dev-mcp.git /opt/mcp-servers/hanzo-dev-mcp || {
    echo "Failed to clone repository. Using npm package instead..."
    cd /opt/mcp-servers
    npm init -y
    npm install --save hanzo-dev-mcp
    mkdir -p /opt/mcp-servers/node_modules/hanzo-dev-mcp/bin
    echo '#!/bin/bash

NODE_PATH=/opt/mcp-servers/node_modules node /opt/mcp-servers/node_modules/hanzo-dev-mcp/dist/server.js "$@"' > /opt/mcp-servers/hanzo-dev-mcp-bin
    chmod +x /opt/mcp-servers/hanzo-dev-mcp-bin
  }
fi

# Create systemd service file
cat > /etc/systemd/system/hanzo-dev-mcp.service << EOL
[Unit]
Description=Hanzo Dev MCP Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/mcp-servers
ExecStart=/opt/mcp-servers/hanzo-dev-mcp-bin --allowed-paths /home/operative
Restart=on-failure
RestartSec=10
StandardOutput=syslog
StandardError=syslog
SyslogIdentifier=hanzo-dev-mcp

[Install]
WantedBy=multi-user.target
EOL

# Enable and start the service
systemctl enable hanzo-dev-mcp.service
systemctl start hanzo-dev-mcp.service

echo "hanzo-dev-mcp server installed and configured to start at boot"
