#!/bin/bash

set -e

export DISPLAY=:${DISPLAY_NUM:-1}
export GEOMETRY="${WIDTH:-1280}x${HEIGHT:-800}x24"

# Start Xvfb
Xvfb $DISPLAY -screen 0 $GEOMETRY &
sleep 1

# Start VNC server
x11vnc -display $DISPLAY -forever -shared &

# Start noVNC
/opt/noVNC/utils/novnc_proxy --vnc localhost:5900 --listen 6080 &

# Keep container running
tail -f /dev/null
