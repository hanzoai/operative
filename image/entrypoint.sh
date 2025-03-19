#!/bin/bash
set -e

# Set default Git config if not already set via environment variables
if [ -z "$(git config --global user.email)" ]; then
    git config --global user.email "dev@hanzo.ai"
fi
if [ -z "$(git config --global user.name)" ]; then
    git config --global user.name "Dev"
fi

./start_all.sh
./novnc_startup.sh

python http_server.py > /tmp/server_logs.txt 2>&1 &

STREAMLIT_SERVER_PORT=8501 python -m streamlit run operative/streamlit.py > /tmp/streamlit_stdout.log &

echo "✨ Operative is ready!"
echo "➡️  Open http://localhost:8080 in your browser to begin"

# Keep the container running
tail -f /dev/null
