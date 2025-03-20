echo "starting tint2 on display :$DISPLAY_NUM ..."
# Check if tint2 exists and is executable
which tint2 || echo "tint2 not found in PATH"

# Try to find tint2rc config file
if [ -f "$HOME/.config/tint2/tint2rc" ]; then
  echo "Found tint2rc at default location"
else
  echo "tint2rc not found at default location"
  # Create default config if missing
  mkdir -p $HOME/.config/tint2
  echo "# Default tint2 config" > $HOME/.config/tint2/tint2rc
fi

# Start tint2 with full path and capture all output
/usr/bin/tint2 -c $HOME/.config/tint2/tint2rc > /tmp/tint2_stdout.log 2>/tmp/tint2_stderr.log &
TINT2_PID=$!

# Wait for tint2 window properties to appear
timeout=30
while [ $timeout -gt 0 ]; do
    if xdotool search --class "tint2" >/dev/null 2>&1; then
        echo "tint2 window found"
        break
    fi
    # Check if process is still running
    if ! kill -0 $TINT2_PID 2>/dev/null; then
        echo "tint2 process died"
        break
    fi
    sleep 1
    ((timeout--))
done

if [ $timeout -eq 0 ]; then
    echo "tint2 stderr output:" >&2
    cat /tmp/tint2_stderr.log >&2
    echo "tint2 stdout output:" >&2
    cat /tmp/tint2_stdout.log >&2
    exit 1
fi
