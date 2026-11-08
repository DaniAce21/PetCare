#!/usr/bin/env bash
set -euo pipefail
# Ejecutar dentro del proyecto, como usuario normal con sudo en Debian/Ubuntu.
cd "$(dirname "$0")/.."
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-dev build-essential libpq-dev postgresql postgresql-contrib nginx
PYTHON_BIN="${PYTHON_BIN:-python3}"
"$PYTHON_BIN" -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/configurar_local.py
printf '%s\n' 'Dependencias instaladas. Configura PostgreSQL y .env según README.md.'
