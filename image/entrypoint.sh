#!/bin/bash
set -e

# Set Git config from environment variables or defaults
git config --global user.email "${GIT_USER_EMAIL:-dev@hanzo.ai}"
git config --global user.name "${GIT_USER_NAME:-Dev}"

./start_all.sh
./novnc_startup.sh

python http_server.py > /tmp/server_logs.txt 2>&1 &

STREAMLIT_SERVER_PORT=8501 python -m streamlit run operative/streamlit.py > /tmp/streamlit_stdout.log &

echo "✨ Operative is ready!"
echo "➡️  Open http://localhost:8080 in your browser to begin"

# Keep the container running
tail -f /dev/null
