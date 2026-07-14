#!/usr/bin/env bash
# One-shot setup: virtualenv + package install.
# Safe to re-run; it reuses an existing .venv.
set -euo pipefail
cd "$(dirname "$0")/.."

PYTHON="${PYTHON:-python3}"

if [ ! -d .venv ]; then
  echo ">> Creating virtualenv (.venv)"
  "$PYTHON" -m venv .venv
fi

echo ">> Installing CareerConductor and dependencies"
./.venv/bin/pip install --quiet --upgrade pip
./.venv/bin/pip install --quiet -e .

if [ ! -f .env ]; then
  cp .env.example .env
  echo ">> Created .env from template — add your API keys:"
  echo "   ANTHROPIC_API_KEY (console.anthropic.com)"
  echo "   GEMINI_API_KEY    (aistudio.google.com, optional)"
fi

echo ">> Done. Start the UI with: ./scripts/run_ui.sh"
