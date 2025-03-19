#!/bin/bash
set -e

# Ensure Git config is set for operative user
sudo -u operative git config --global user.email "${GIT_USER_EMAIL:-dev@hanzo.ai}"
sudo -u operative git config --global user.name "${GIT_USER_NAME:-Dev}"

# Start dbus service
eval "$(dbus-launch --sh-syntax)"

echo "🖥️ Starting GDM3 Display Manager..."
systemctl start gdm3

# Allow GDM to spin up fully
sleep 5

# Find the GDM3 Xauthority file (may differ based on system/ubuntu version)
AUTHFILE=$(find /var/lib/gdm3 /var/run/gdm3 /run/user -name '*.Xauth' 2>/dev/null | head -n 1)
if [ -z "$AUTHFILE" ]; then
    echo "❌ Failed to locate GDM3 Xauthority file"
    exit 1
fi

echo "✅ Found Xauthority: $AUTHFILE"

# Optional: Generate VNC password if not present
if [ ! -f /home/operative/.vnc/passwd ]; then
    mkdir -p /home/operative/.vnc
    x11vnc -storepasswd "${VNC_PASSWORD:-changeme}" /home/operative/.vnc/passwd
fi

echo "🚀 Starting x11vnc on DISPLAY :0 with auth"
x11vnc -display :0 -auth "$AUTHFILE" -forever -rfbauth /home/operative/.vnc/passwd -rfbport 5900 &

# Optional: Start novnc for browser access
./novnc_startup.sh

# Optional ML/Streamlit/Python apps
python http_server.py > /tmp/server_logs.txt 2>&1 &
STREAMLIT_SERVER_PORT=8501 python -m streamlit run operative/streamlit.py > /tmp/streamlit_stdout.log &

echo "✨ Operative is ready!"
echo "➡️  Open VNC on port 5900 or browser http://localhost:6080/vnc.html"

# Keep container alive
tail -f /dev/null
