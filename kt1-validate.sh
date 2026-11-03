#!/usr/bin/env sh
# Walidator XML KT-1 - uruchamianie w Linux / macOS / Git Bash. Użycie: ./kt1-validate.sh plik.xml [opcje]
DIR=$(cd "$(dirname "$0")" && pwd)
if command -v python3 >/dev/null 2>&1; then PY=python3; else PY=python; fi
exec "$PY" "$DIR/kt1_validator.py" "$@"
