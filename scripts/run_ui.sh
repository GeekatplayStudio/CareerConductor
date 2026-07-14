#!/usr/bin/env bash
# Launch the Streamlit control panel at http://localhost:8501
set -euo pipefail
cd "$(dirname "$0")/.."
exec ./.venv/bin/streamlit run careerconductor/ui/app.py "$@"
