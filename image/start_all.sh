#!/bin/bash

set -e

export DISPLAY=:${DISPLAY_NUM}
export XDG_SESSION_TYPE=x11
export XDG_SESSION_DESKTOP=budgie-desktop
export XDG_CURRENT_DESKTOP=Budgie:GNOME

./xvfb_startup.sh

# Start Budgie Desktop
budgie-daemon &
budgie-panel &
budgie-wm &

./x11vnc_startup.sh
