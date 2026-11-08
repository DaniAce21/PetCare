#!/usr/bin/env bash
set -euo pipefail
# Solo si Ubuntu no tiene Python 3.13. No reemplaza /usr/bin/python3.
# Uso: bash scripts/instalar_python313.sh 3.13.X (elegir un parche oficial vigente).
PYTHON_PATCH="${1:?Indica una versión oficial 3.13.X desde https://www.python.org/downloads/}"
if [[ ! "$PYTHON_PATCH" =~ ^3\.13\.[0-9]+$ ]]; then
  printf '%s\n' 'La versión debe ser 3.13.X.' >&2
  exit 1
fi
sudo apt-get update
sudo apt-get install -y build-essential curl xz-utils libssl-dev zlib1g-dev libbz2-dev libreadline-dev libffi-dev liblzma-dev libncurses-dev uuid-dev
PYTHON_BUILD_DIR="$(mktemp -d)"
trap 'rm -rf "$PYTHON_BUILD_DIR"' EXIT
cd "$PYTHON_BUILD_DIR"
curl --fail --location --proto '=https' --tlsv1.2 "https://www.python.org/ftp/python/${PYTHON_PATCH}/Python-${PYTHON_PATCH}.tar.xz" -o python.tar.xz
tar -xf python.tar.xz
cd "Python-${PYTHON_PATCH}"
./configure --prefix=/opt/python313 --with-ensurepip=install
make -j2
sudo make altinstall
printf '%s\n' 'Python listo: /opt/python313/bin/python3.13. Usa PYTHON_BIN=/opt/python313/bin/python3.13 al instalar dependencias.'
