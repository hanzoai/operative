#!/bin/bash
set -e

cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")"

# Then start the UI components
./start_all.sh
./novnc_startup.sh

# Use project venv
source ~/.operative/.venv/bin/activate

# static server
python http_server.py > /tmp/server_logs.txt 2>&1 &

# streamlit app
STREAMLIT_SERVER_PORT=8501 ~/.operative/.venv/bin/python -m streamlit run operative/operative.py > /tmp/streamlit_stdout.log &

echo "✨ Operative initialized."
echo "➡️  Open http://localhost:8080 in your browser to begin."

# Keep the container running
tail -f /dev/null
