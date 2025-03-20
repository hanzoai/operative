#!/bin/bash
set -e

cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")"

./start_all.sh
./novnc_startup.sh

python http_server.py > /tmp/server_logs.txt 2>&1 &

STREAMLIT_SERVER_PORT=8501 python -m streamlit run $HOME/.operative/operative/operative.py > /tmp/streamlit_stdout.log &

echo "✨ Operative initialized."
echo "➡️  Open http://localhost:8080 in your browser to begin."

# Keep the container running
tail -f /dev/null
