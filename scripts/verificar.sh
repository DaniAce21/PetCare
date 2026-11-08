#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
.venv/bin/python manage.py check
.venv/bin/python manage.py makemigrations --check --dry-run
.venv/bin/python manage.py migrate --noinput
.venv/bin/python manage.py test --verbosity 2
.venv/bin/python manage.py collectstatic --noinput
.venv/bin/python manage.py check --deploy
node --check static/app.js
node --check static/portal.js
