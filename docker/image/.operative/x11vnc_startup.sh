#!/bin/bash
echo "starting vnc"

# Use TigerVNC's x0vncserver instead of x11vnc.
# x11vnc (LibVNCServer 0.9.13) has a MSG_PEEK deadlock bug: on new
# connections it peeks at the first byte to detect WebSocket vs RFB,
# but in RFB the server speaks first, so both sides wait forever.
# x0vncserver uses TigerVNC's VNC implementation which speaks the
# RFB protocol correctly (server sends version banner immediately).

VNC_CMD=""
VNC_ARGS=""

if command -v x0vncserver &>/dev/null; then
    echo "Using TigerVNC x0vncserver"
    VNC_CMD="x0vncserver"
    VNC_ARGS="-display $DISPLAY -rfbport 5900 -SecurityTypes None"
elif command -v x11vnc &>/dev/null; then
    echo "WARNING: Falling back to x11vnc (MSG_PEEK deadlock likely)"
    VNC_CMD="x11vnc"
    VNC_ARGS="-display $DISPLAY -forever -shared -wait 50 -rfbport 5900 -nopw -nolookup -noxdamage -nap"
else
    echo "ERROR: No VNC server found" >&2
    exit 1
fi

($VNC_CMD $VNC_ARGS 2>/tmp/x11vnc_stderr.log) &

vnc_pid=$!

# Wait for VNC server to start
timeout=10
while [ $timeout -gt 0 ]; do
    if netstat -tuln | grep -q ":5900 "; then
        break
    fi
    sleep 1
    ((timeout--))
done

if [ $timeout -eq 0 ]; then
    echo "VNC server failed to start, stderr output:" >&2
    cat /tmp/x11vnc_stderr.log >&2
    exit 1
fi

: > /tmp/x11vnc_stderr.log

# Monitor VNC server process in the background
(
    while true; do
        if ! kill -0 $vnc_pid 2>/dev/null; then
            echo "VNC server process crashed, restarting..." >&2
            if [ -f /tmp/x11vnc_stderr.log ]; then
                echo "VNC server stderr output:" >&2
                cat /tmp/x11vnc_stderr.log >&2
                rm /tmp/x11vnc_stderr.log
            fi
            exec "$0"
        fi
        sleep 5
    done
) &
