#!/usr/bin/env python3
"""Crea .env sin sobrescribirlo ni imprimir secretos."""
from pathlib import Path
import os
import secrets
root = Path(__file__).resolve().parent.parent
path = root/'.env'
if path.exists():
    print('.env ya existe. Se conserva sin modificaciones.')
else:
    data = (root/'.env.example').read_text().replace('SECRET_KEY=\n','SECRET_KEY='+secrets.token_urlsafe(64)+'\n')
    fd = os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as file:
        file.write(data)
    print('.env creado. Configura PostgreSQL antes de ejecutar migraciones.')
