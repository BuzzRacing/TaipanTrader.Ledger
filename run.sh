#!/usr/bin/env bash
# Runs SeaTrader in this terminal on Linux, a Raspberry Pi or a Mac.
# Ctrl+C saves and stops.   ./run.sh [--port 8765] [--new]
cd "$(dirname "${BASH_SOURCE[0]}")" || exit 1
exec python3 -u server.py "$@"
