#!/usr/bin/env bash
# ============================================================================
#  CareerConductor launcher — Mac / Linux
#  Run from the project root:   ./start.sh
#  Opens the control panel at http://localhost:8501
# ============================================================================
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -x ./.venv/bin/streamlit ]; then
  echo "The app is not installed yet — run ./install.sh first."
  exit 1
fi
if [ ! -f .env ]; then
  echo "Note: no .env found. Copy .env.example to .env and add your API keys"
  echo "or the pipeline pages will show missing-key warnings."
fi

echo "Starting CareerConductor at http://localhost:8501  (Ctrl+C to stop)"
exec ./.venv/bin/streamlit run careerconductor/ui/app.py "$@"
