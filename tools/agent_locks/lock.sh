#!/usr/bin/env bash
# Runs file_lock.py with whichever Python this computer has (py launcher on Windows,
# python3 on the Raspberry Pi). If none is found the edit goes ahead unguarded.
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if command -v py >/dev/null 2>&1; then
  exec py -3 "$DIR/file_lock.py" "$@"
elif command -v python3 >/dev/null 2>&1; then
  exec python3 "$DIR/file_lock.py" "$@"
elif command -v python >/dev/null 2>&1; then
  exec python "$DIR/file_lock.py" "$@"
fi
exit 0
