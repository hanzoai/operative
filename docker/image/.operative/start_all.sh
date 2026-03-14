#!/bin/bash

set -e

export DISPLAY=:${DISPLAY_NUM:-1}

./xvfb_startup.sh
./tint2_startup.sh
./mutter_startup.sh

# Setup desktop icons via pcmanfm (replaces broken tint2 launcher)
echo "Setting up desktop icons..."
mkdir -p $HOME/Desktop
mkdir -p $HOME/.config/libfm

# Configure libfm to auto-execute .desktop files without prompting
cat > $HOME/.config/libfm/libfm.conf << 'LIBFM'
[config]
quick_exec=1

[ui]
always_show_tabs=0
LIBFM

# Create desktop shortcut files
cat > $HOME/Desktop/Terminal.desktop << 'DESK'
[Desktop Entry]
Name=Terminal
Exec=xterm -fa "Monospace" -fs 14
Icon=utilities-terminal
Type=Application
DESK

cat > $HOME/Desktop/Firefox.desktop << 'DESK'
[Desktop Entry]
Name=Firefox
Exec=firefox-esr
Icon=firefox-esr
Type=Application
DESK

cat > $HOME/Desktop/Calculator.desktop << 'DESK'
[Desktop Entry]
Name=Calculator
Exec=galculator
Icon=galculator
Type=Application
DESK

cat > $HOME/Desktop/TextEditor.desktop << 'DESK'
[Desktop Entry]
Name=Text Editor
Exec=gedit
Icon=text-editor
Type=Application
DESK

cat > $HOME/Desktop/Spreadsheet.desktop << 'DESK'
[Desktop Entry]
Name=Spreadsheet
Exec=libreoffice --calc
Icon=libreoffice-calc
Type=Application
DESK

cat > $HOME/Desktop/Files.desktop << 'DESK'
[Desktop Entry]
Name=Files
Exec=pcmanfm
Icon=system-file-manager
Type=Application
DESK

chmod +x $HOME/Desktop/*.desktop

# Start pcmanfm desktop mode (manages root window with desktop icons)
pcmanfm --desktop &
sleep 1

./x11vnc_startup.sh

# Start MCP servers
echo "Starting Hanzo MCP"
./hanzo-mcp.sh
