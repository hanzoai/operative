#!/bin/bash
set -e

echo "🖥️ Starting Xvfb virtual display..."
mkdir -p /tmp/.X11-unix && chmod 1777 /tmp/.X11-unix
Xvfb :1 -screen 0 1920x1080x24 &
export DISPLAY=:1
sleep 2

# Set default Git config if not already set
if [ -z "$(git config --global user.email)" ]; then
    git config --global user.email "dev@hanzo.ai"
fi
if [ -z "$(git config --global user.name)" ]; then
    git config --global user.name "Dev"
fi

# Patch i3 config if needed (remove xss-lock, nm-applet if headless)
sed -i '/xss-lock/d' /home/operative/.config/i3/config || true
sed -i '/nm-applet/d' /home/operative/.config/i3/config || true

# Set macOS-like GTK/QT theme and Inter Variable font
export GTK_THEME="WhiteSur-Dark"
export GTK2_RC_FILES="/usr/share/themes/WhiteSur-Dark/gtk-2.0/gtkrc"
export QT_STYLE_OVERRIDE="WhiteSur-Dark"
export GDK_SCALE=1
export FONT="InterVariable 11"
export PANGO_FONT="InterVariable 11"

# Optional compositor for shadows (if picom is installed)
# picom --config /home/operative/.config/picom.conf &

echo "🪟 Starting i3 Window Manager..."
i3 &

# VNC setup
if [ ! -f /home/operative/.vnc/passwd ]; then
    mkdir -p /home/operative/.vnc
    x11vnc -storepasswd "${VNC_PASSWORD:-changeme}" /home/operative/.vnc/passwd
fi

echo "🚀 Starting x11vnc server on DISPLAY :1"
x11vnc -display :1 -forever -rfbauth /home/operative/.vnc/passwd -rfbport 5901 -noxdamage &

echo "🌐 Starting noVNC server..."
./novnc_startup.sh &

# Optional backend services
echo "⚙️ Starting backend services..."
python http_server.py > /tmp/server_logs.txt 2>&1 &
STREAMLIT_SERVER_PORT=8501 python -m streamlit run operative/streamlit.py > /tmp/streamlit_stdout.log &

echo "✨ Operative environment ready!"
echo "➡️  VNC on port 5901 or browser at http://localhost:6080/vnc.html"

# Keep the container running
tail -f /dev/null
