# Despliegue en AWS Academy EC2 · Ubuntu

**Estado: pendiente.** No se ha creado, configurado ni publicado una instancia durante esta sesión. No se dispone de una IP pública real ni de credenciales AWS. Los siguientes pasos deben ejecutarse en la instancia por el responsable del laboratorio.

## 1. Instancia y red

Crear EC2 Ubuntu compatible con el laboratorio (por ejemplo Ubuntu 24.04 LTS), usando el par de claves del estudiante. No guardar `.pem`, credenciales de AWS ni `.env` en Git. Elegir recursos suficientes para PostgreSQL, dos workers de Gunicorn y el sistema; si se compila Python puede requerir más RAM que el uso ordinario. Al detener AWS Academy puede cambiar la IP pública: actualizar `ALLOWED_HOSTS`, orígenes CSRF y Nginx.

Security Group de entrada:

| Puerto TCP | Origen | Uso |
|---|---|---|
| 22 | IP del estudiante `/32` | SSH |
| 80 | Público, si se requiere revisión externa | HTTP |
| 443 | Público, solo al habilitar TLS | HTTPS |
| 5432 | **Sin regla pública** | PostgreSQL solo localhost |
| 8000/8001 | **Sin regla pública** | Desarrollo/Gunicorn internos |

Acceso (reemplazar marcadores):

```bash
chmod 600 /ruta/privada/clave.pem
ssh -i /ruta/privada/clave.pem ubuntu@IP_PUBLICA_REAL
```

No editar reglas de AWS desde un script que asuma credenciales o IDs del laboratorio. La configuración debe realizarse en la consola autorizada.

## 2. Código y Python

Copiar el proyecto a `/srv/petcare`, excluyendo `.env`, `.venv`, `.local`, `__pycache__`, backups y `staticfiles`. Se puede usar un repositorio propio o `rsync` desde el equipo local. No hay una URL Git predefinida en esta entrega.

```bash
sudo mkdir -p /srv/petcare
sudo chown ubuntu:ubuntu /srv/petcare
# Copiar aquí el código del proyecto y entrar a /srv/petcare
cd /srv/petcare
python3 --version
```

Se solicita Python 3.13. Debian 13 lo incluye; Ubuntu puede traer otra versión. Si ya existe `python3.13`, usarla. En caso contrario el script opcional compila una versión oficial **sin reemplazar el Python del sistema**:

```bash
# Elegir un parche 3.13 vigente en https://www.python.org/downloads/
# Sustituir X por el número real antes de ejecutar.
bash scripts/instalar_python313.sh 3.13.X
PYTHON_BIN=/opt/python313/bin/python3.13 bash scripts/instalar_dependencias.sh
```

Si Python 3.13 ya está disponible:

```bash
PYTHON_BIN=python3.13 bash scripts/instalar_dependencias.sh
```

El script no se ejecutó aquí con sudo. Requiere Internet y puede tardar al compilar; `make -j2` limita memoria. Verifica la procedencia del archivo de versión en python.org y usa un parche mantenido, no el Python 3.13.5 del equipo de construcción como referencia de actualización.

## 3. PostgreSQL y variables

```bash
sudo systemctl enable --now postgresql
sudo -u postgres createuser --pwprompt petcare
sudo -u postgres createdb --owner=petcare petcare
sudo -u postgres psql -d petcare -c 'CREATE EXTENSION IF NOT EXISTS btree_gist;'
nano .env
```

Configurar:

```text
DEBUG=False
ALLOWED_HOSTS=IP_PUBLICA_REAL,DOMINIO_SI_EXISTE,127.0.0.1,localhost
DB_NAME=petcare
DB_USER=petcare
DB_PASSWORD=<contraseña elegida>
DB_HOST=127.0.0.1
DB_PORT=5432
HTTPS_ENABLED=False
CSRF_TRUSTED_ORIGINS=http://IP_PUBLICA_REAL
```

Eliminar `DOMINIO_SI_EXISTE` si no se usa. Conservar la SECRET_KEY generada por `configurar_local.py`; no regenerarla en cada reinicio. `HTTPS_ENABLED=False` solo corresponde a la primera comprobación por HTTP. Mantener PostgreSQL limitado a localhost y autenticación SCRAM según [guía](postgresql.md).

## 4. Migraciones, administrador y estáticos

```bash
.venv/bin/python manage.py check
.venv/bin/python manage.py migrate
.venv/bin/python manage.py createsuperuser
.venv/bin/python manage.py collectstatic --noinput
# Opcional: solo en base académica vacía
.venv/bin/python manage.py cargar_demo
```

Ejecutar la suite en una BD de pruebas local separada **antes** de servir datos de la clínica. Conceder temporalmente CREATEDB al rol de desarrollo, según la guía, y retirarlo después. `staticfiles` se genera con collectstatic; no subirlo como sustituto de ejecutar el comando.

## 5. Usuario de servicio y permisos

```bash
sudo useradd --system --home /srv/petcare --shell /usr/sbin/nologin petcare
sudo chown -R petcare:www-data /srv/petcare
sudo chmod 750 /srv/petcare
sudo chmod 600 /srv/petcare/.env
```

El directorio `staticfiles` debe ser legible por el grupo www-data de Nginx. El generador crea normalmente archivos 644 y directorios 755; comprobarlos si se cambió la umask. La cuenta petcare es del sistema, distinta del rol PostgreSQL aunque compartan nombre.

## 6. Gunicorn y systemd

```bash
sudo cp deploy/petcare.service /etc/systemd/system/petcare.service
sudo systemctl daemon-reload
sudo systemctl enable --now petcare
sudo systemctl status petcare --no-pager
sudo journalctl -u petcare -n 50 --no-pager
```

`deploy/gunicorn.conf.py` enlaza a `127.0.0.1:8001`, tiene dos workers y dos threads por worker por defecto. Ajustar `WEB_CONCURRENCY` si la instancia tiene recursos limitados. El servicio usa `/srv/petcare/.venv`, no el Python global. `ProtectSystem=strict`/`ProtectHome=true` suponen código en `/srv`, sin cargas de archivos ni escritura de logs dentro del repositorio.

## 7. Nginx

Reemplazar `IP_PUBLICA_O_DOMINIO` en `deploy/nginx.conf` por la IP/dominio real antes de copiar:

```bash
sudo cp deploy/nginx.conf /etc/nginx/sites-available/petcare
sudo ln -s /etc/nginx/sites-available/petcare /etc/nginx/sites-enabled/petcare
# Si se trata de una instancia dedicada nueva, quitar el enlace del sitio por defecto:
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl enable --now nginx
sudo systemctl reload nginx
```

No eliminar el sitio default si contiene trabajo ajeno. No crear dos enlaces del mismo sitio. El archivo incluye una zona para limitar solicitudes al login; si otros sitios usan zonas, evitar nombres duplicados. Nginx sirve estáticos y fija `X-Forwarded-Proto` antes de reenviar a Gunicorn. Comprobar `http://IP_PUBLICA_REAL/login/` desde otro equipo.

## 8. HTTPS

Si hay dominio disponible, instalar Certbot según la distribución y emitir certificado para el dominio que apunta a la instancia. Después:

```text
HTTPS_ENABLED=True
CSRF_TRUSTED_ORIGINS=https://DOMINIO_REAL
ALLOWED_HOSTS=DOMINIO_REAL,127.0.0.1,localhost
```

Nginx debe servir TLS y redirigir HTTP a HTTPS. Reiniciar PetCare y verificar:

```bash
sudo systemctl restart petcare
sudo -u petcare /srv/petcare/.venv/bin/python /srv/petcare/manage.py check --deploy --fail-level WARNING
```

La configuración HTTPS activa cookies seguras y redirección SSL. HSTS permanece desactivado con `HSTS_SECONDS=0`; habilitarlo separadamente después de comprobar HTTPS. No activarla antes de disponer de TLS real. En HTTP, `check --deploy` muestra W004/W008/W012/W016: corresponden a HSTS, redirección SSL y cookies seguras; no se han silenciado. Pasar un control de configuración no certifica por sí solo la seguridad de la instancia.

## 9. Automatización

Opción preferida:

```bash
sudo cp deploy/petcare-recordatorios.service /etc/systemd/system/
sudo cp deploy/petcare-recordatorios.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now petcare-recordatorios.timer
sudo systemctl start petcare-recordatorios.service
sudo systemctl list-timers petcare-recordatorios.timer
sudo journalctl -u petcare-recordatorios.service -n 30 --no-pager
```

Alternativa cron como usuario petcare (elegir **una** de las dos opciones):

```cron
0 * * * * cd /srv/petcare && /srv/petcare/.venv/bin/python manage.py generar_recordatorios --enviar
```

`.env` se carga desde la raíz mediante python-dotenv. Sin SMTP configurado se generan los avisos pero no se envía correo. Probar primero con destinatarios propios y nunca con direcciones de los datos ficticios.

## 10. Aceptación externa y registro

Completar manualmente:

- IP pública real: **PENDIENTE**.
- Dominio y URL: **PENDIENTE**.
- Fecha/hora y responsable de despliegue: **PENDIENTE**.
- Salida real de migraciones y suite PostgreSQL: **PENDIENTE**.
- `nginx -t`, estado de Gunicorn y timer: **PENDIENTE**.
- Login de los tres roles, CRUD y reserva concurrente: **PENDIENTE**.
- Capturas desde navegador externo: **PENDIENTE**.
- Configuración SMTP/recepción de correo, si se evalúa: **PENDIENTE**.

Al actualizar el código: respaldar BD, instalar requisitos, aplicar migraciones revisadas, collectstatic, reiniciar servicio y volver a probar. No se requiere abrir PostgreSQL al exterior en ninguna etapa.


Rediseño 2026-11-05: seguir también [seguridad operativa](seguridad-operativa.md). Configurar el proxy confiable local, revisar el nuevo servidor default Nginx y no habilitar HSTS por anticipado. La IP pública real sigue pendiente.
