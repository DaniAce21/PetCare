# Rediseño PetCare — 2026-11-05

## Resultado implementado

Se continuó el proyecto existente en `/home/chororemy/Proyectos/PetCare`. No se creó otro proyecto, no se reemplazó PostgreSQL por SQLite, no se borraron datos ni se modificó la migración inicial. La carpeta no contiene metadatos Git accesibles; no se creó un repositorio nuevo ni se hizo commit.

- Relación opcional y única Tutor–User; registro público transaccional exclusivamente Tutor, sesiones y logout POST, cuenta personal y recuperación Django con token de una hora. Vinculación explícita y validada para cuentas anteriores.
- Portal independiente con cuatro acciones, mascotas con edad aproximada y próxima vacuna, historial clínico de lectura, reservas en cinco pasos, citas próximas/anteriores, cancelación futura y vacunas/controles/recordatorios propios. Diseño con CSS responsive, foco visible, enlaces de salto, formularios etiquetados y estado de envío progresivo. Funciona sin JavaScript para el flujo esencial.
- Conservación de la interfaz clínica; dashboard con indicadores reales, citas del día, consultas recientes y acceso directo desde una cita al paciente y su atención. Se conservan agenda, CRUD, fichas, vacunas, profesionales, disponibilidad y recordatorios existentes.
- Querysets y permisos por objeto para tutores; validación de dueño, paciente, estado, plazo y duración en serializers, con revalidación dentro del bloqueo. Escrituras clínicas verifican al profesional tanto en la API como en serializers/Admin.
- Django Admin con identidad propia, plantillas, fieldsets, restricciones de rol además de staff/permisos y autoría en escrituras y eliminaciones masivas. Usuarios y grupos se administran exclusivamente con rol Administrador.
- Límites temporales de autenticación compartidos en PostgreSQL y transaccionales, por IP y cuenta; eventos sin credenciales; protección del login Admin y de registro/recuperación. Configuración de proxy, límites Nginx, logs sin tokens de recuperación, separación entre HTTPS y HSTS, SSH y Fail2ban de ejemplo.
- Documentación académica, ER, defensa oral, continuidad de usuarios y seguridad operativa actualizadas.

## Migraciones incrementales

| Archivo | Cambio | Estado real |
|---|---|---|
| `0001_initial.py` | Esquema y exclusiones existentes | Conservada sin editar; no se pudo consultar su estado aplicado |
| `0002_tutor_usuario.py` | OneToOne nullable con User, PROTECT | Generada, pendiente de aplicar en Debian |
| `0003_loginwindow.py` | Contadores compartidos de autenticación | Generada, pendiente de aplicar en Debian |

No se han inferido vínculos de datos personales. Antes de migrar, respaldar la base actual. Para vincular una cuenta antigua, verificar identidad y usar `manage.py vincular_tutor USUARIO ID_TUTOR`. El comando conserva mascotas e historial; no sobrescribe vínculos y rechaza cuentas con privilegios clínicos/técnicos. Si recepcion debe conservar su rol de personal, asignar únicamente Recepcionista desde administración; si debe ser Tutor, usar una cuenta normal y el vínculo explícito. No se ha cambiado esa cuenta sin poder inspeccionarla en PostgreSQL.

## Verificación real

Salidas completas en [verificacion-redisenio.txt](verificacion-redisenio.txt).

| Verificación | Resultado |
|---|---|
| `manage.py check` | Correcto, sin incidencias |
| `makemigrations --check --dry-run` | Sin cambios; advertencia porque no puede revisar el historial aplicado en PostgreSQL |
| `manage.py migrate --noinput` | Falló al conectar PostgreSQL; no se aplicaron las nuevas migraciones |
| `manage.py test --noinput` | Se descubren 86 pruebas; bloqueado al crear/conectar la base PostgreSQL temporal |
| `manage.py test clinica.tests.test_unit --noinput` | **26 pruebas aprobadas**, sin base de datos |
| `manage.py collectstatic --noinput` | Correcto; 159 archivos estáticos disponibles |
| `node --check static/app.js` y `static/portal.js` | Correcto, sintaxis válida |
| `nginx -t` con rutas de logs/pid temporales | Sintaxis reconocida; comprobación completa falla porque no puede abrir sockets |
| Conexión PostgreSQL/servidor/navegador | No verificables: incluso `socket.socket()` devuelve `PermissionError: Operation not permitted` |
| Despliegue EC2/TLS/SMTP real | No ejecutado; sin IP pública real ni validación de servicios externos |

Las 26 pruebas incluyen permisos, propiedad simulada, CSRF público, rutas, compilación de plantillas y estructura no destructiva de migraciones. Las restantes **60 pruebas necesitan PostgreSQL**; incluyen registro, sesiones, CRUD, aislamiento de tutores, Admin, reset, límites y expiración, proxies falsos, agenda, carreras de reservas y límite de login simultáneo. Están implementadas, no se declaran aprobadas.

La sintaxis JavaScript válida no demuestra ausencia de fallos de ejecución. La revisión real responsive, teclado, navegador y carga de datos sigue pendiente junto con PostgreSQL. No se presentan capturas ni estadísticas fabricadas.

## Archivos principales modificados o añadidos

- Backend: `clinica/models.py`, `permissions.py`, `serializers.py`, `api.py`, `views.py`, `forms.py`, `middleware.py`, `signals.py`, `admin.py`.
- Configuración: `petcare/settings.py`, `petcare/urls.py`, `.env.example`.
- Migraciones: `clinica/migrations/0002_tutor_usuario.py`, `0003_loginwindow.py`.
- Comandos: `clinica/management/commands/vincular_tutor.py`, `limpiar_intentos.py`.
- Interfaz: `templates/portal/*.html`, `templates/registration/login.html`, `reset_*.html`, `password_reset_email.html`, `password_reset_subject.txt`, `templates/admin/base_site.html`, `index.html`, `templates/clinica/app.html`, `templates/400.html`.
- Estáticos: `static/portal.css`, `portal.js`, `app.js`; archivos recopilados en `staticfiles/`.
- Pruebas: `clinica/tests/test_portal.py`, `test_unit.py`, `test_concurrency.py`; `scripts/verificar.sh`.
- Despliegue: `deploy/nginx.conf`, `gunicorn.conf.py`, `sshd-petcare.conf`, `fail2ban-petcare.conf`. Se conserva el servicio systemd existente con usuario sin root y reinicio automático.
- Documentación: `README.md`, `prompts_ia.md`, `docs/modelo-er.md`, `arquitectura.md`, `casos-de-uso.md`, `defensa-oral.md`, `postgresql.md`, `despliegue-ec2.md`, `seguridad-operativa.md`, `pruebas.md`, este informe y las salidas de verificación.

## Completar en Debian

Conservar `.env` y respaldar PostgreSQL antes de aplicar migraciones. No ejecutar cargar_demo en una base con datos. No usar flush ni borrar migraciones. Activar PostgreSQL solo si está detenido:

```bash
cd /home/chororemy/Proyectos/PetCare
sudo systemctl status postgresql --no-pager
# Solo si está detenido:
sudo systemctl start postgresql
pg_isready -h 127.0.0.1 -p 5432
pg_dump -h 127.0.0.1 -U petcare -W -Fc petcare -f "$HOME/petcare-antes-redisenio.backup"
chmod 600 "$HOME/petcare-antes-redisenio.backup"
.venv/bin/python manage.py check
.venv/bin/python manage.py makemigrations --check --dry-run
.venv/bin/python manage.py migrate
# El usuario de desarrollo necesita CREATEDB para la base temporal, nunca usar DB_TEST_NAME=DB_NAME.
.venv/bin/python manage.py test --verbosity 2
.venv/bin/python manage.py collectstatic --noinput
.venv/bin/python manage.py runserver 127.0.0.1:8000
```

Adaptar usuario/nombre/puerto al `.env` real sin publicar secretos. Si falta CREATEDB, usar `sudo -u postgres psql -c 'ALTER ROLE petcare CREATEDB;'` únicamente en desarrollo y retirarlo luego con NOCREATEDB. No conceder superusuario PostgreSQL al proceso web. Para instalar servicios y seguridad de EC2, seguir [despliegue](despliegue-ec2.md) y [seguridad operativa](seguridad-operativa.md); esos pasos requieren sudo y acceso autorizado a la instancia.

Abrir `/registro/` para el Tutor y `/login/` para personal existente. Las cuentas con roles válidos usan `/` y reciben su interfaz correspondiente. Verificar con dos cuentas Tutor que no puedan consultar objetos ajenos; luego probar profesional, agenda, ficha, vacunas y Admin con las pruebas y el recorrido de defensa.
