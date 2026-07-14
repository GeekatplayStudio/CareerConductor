#!/usr/bin/env bash
# ============================================================================
#  CareerConductor installer — Mac / Linux
#  Run from the project root:   ./install.sh
#  Safe to re-run any time; it reuses the existing environment.
# ============================================================================
set -euo pipefail
cd "$(dirname "$0")"

step() { printf '\n[%s/4] %s\n' "$1" "$2"; }

step 1 "Checking Python (3.11 or newer required)"
PYTHON="${PYTHON:-python3}"
if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "  Python 3 was not found. Install it from https://www.python.org/downloads/"
  echo "  (or on Mac: brew install python) and run ./install.sh again."
  exit 1
fi
"$PYTHON" - <<'EOF'
import sys
if sys.version_info < (3, 11):
    print(f"  Found Python {sys.version.split()[0]} — 3.11+ is required.")
    raise SystemExit(1)
print(f"  OK: Python {sys.version.split()[0]}")
EOF

step 2 "Creating virtual environment (.venv)"
if [ -d .venv ]; then
  echo "  .venv already exists — reusing it."
else
  "$PYTHON" -m venv .venv
  echo "  Created .venv"
fi

step 3 "Installing CareerConductor and dependencies (may take a minute)"
./.venv/bin/pip install --quiet --upgrade pip
./.venv/bin/pip install --quiet -e .
echo "  Dependencies installed."

step 4 "Preparing configuration"
if [ -f .env ]; then
  echo "  .env already exists — keeping your settings."
else
  cp .env.example .env
  echo "  Created .env from the template."
fi

printf '\nDone. Next steps:\n'
printf '  1. Open .env and add your ANTHROPIC_API_KEY (console.anthropic.com)\n'
printf '     and optionally GEMINI_API_KEY (aistudio.google.com).\n'
printf '  2. Launch the app:   ./start.sh\n'
