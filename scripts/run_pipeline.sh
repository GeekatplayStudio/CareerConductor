#!/usr/bin/env bash
# Headless pipeline run (same stages as the UI's Run button). Cron-friendly:
#   0 8 * * * /path/to/JobAgent/scripts/run_pipeline.sh >> /tmp/careerconductor.log 2>&1
set -euo pipefail
cd "$(dirname "$0")/.."
exec ./.venv/bin/python -m careerconductor.main
