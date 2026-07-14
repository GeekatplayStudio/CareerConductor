#!/usr/bin/env bash
# ============================================================================
#  CareerConductor double-clickable installer for macOS
#  Double-click this file in Finder to run setup.
# ============================================================================
cd "$(dirname "$0")"
chmod +x install.sh
./install.sh
echo ""
echo "Press [Enter] to close this window..."
read -r
