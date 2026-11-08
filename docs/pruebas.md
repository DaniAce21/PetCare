> Registro histórico de la entrega anterior. Los resultados del rediseño del 2026-11-05 están en [redisenio.md](redisenio.md) y [verificacion-redisenio.txt](verificacion-redisenio.txt). Actualmente se descubren 86 pruebas; solo 26 sin PostgreSQL pudieron ejecutarse con éxito.

# Pruebas: resultados reales y pendientes

Fecha de ejecución: 4 de noviembre de 2026. Entorno: Python 3.13.5; Django 5.2.17; DRF 3.18.1; Psycopg 3.3.6; binarios PostgreSQL 17.11 presentes. No se utilizó SQLite como sustituto.

## Resultado observado

| Comando / comprobación | Resultado real |
|---|---|
| `python manage.py check` | Pasa: 0 problemas |
| `python manage.py makemigrations --check --dry-run` | Pasa: No changes detected; advertencia de que no pudo consultarse el historial de la BD |
| `python manage.py migrate --noinput` | Falla antes de migrar: conexión PostgreSQL no disponible en el entorno restringido |
| `python manage.py test --verbosity 1` | Descubre la suite, pero falla creando/conectando la BD temporal; no hay aprobación de la suite completa |
| `python manage.py test clinica.tests.test_unit` | **23 pruebas aprobadas**, sin usar base de datos |
| `python manage.py collectstatic --noinput` | Pasa; estáticos de Django/DRF/app reunidos |
| `DEBUG=False HTTPS_ENABLED=True python manage.py check --deploy` | Pasa: 0 problemas |
| `DEBUG=False HTTPS_ENABLED=False python manage.py check --deploy` | 4 advertencias reales: W004, W008, W012, W016. El comando devuelve 0 por defecto; no equivale a ausencia de advertencias |
| `python manage.py runserver 127.0.0.1:8000 --noreload` | Falla antes de escuchar: comprobación de migraciones necesita PostgreSQL |
| `node --check static/app.js` | Pasa |
| Carga de `petcare.wsgi.application` | Pasa: objeto WSGI importado |
| `nginx -t` con configuración propia temporal | Reconoce sintaxis válida, pero falla al abrir socket :80 por `Operation not permitted`; no se declara validación completa de Nginx |
| `python -m compileall` (configuración, app y scripts) | Pasa |
| `bash -n scripts/*.sh` | Pasa |

El archivo [verificacion-real.txt](verificacion-real.txt) contiene salidas y códigos de retorno. Se agregó al final una segunda ejecución tras ampliar las pruebas unitarias a 23. La ejecución inicial de un test de RUT con K falló por un valor esperado incorrecto y se corrigió antes de las ejecuciones exitosas. No se ocultaron advertencias de despliegue.

## Causa de la limitación

La instalación por pip encontró `Name or service not known`; se reutilizaron dependencias disponibles en un entorno local aislado. PostgreSQL se pudo inicializar con `initdb` en una carpeta ignorada, pero `pg_ctl` no pudo abrir un socket Unix ni TCP:

```text
could not bind Unix address ...: Operation not permitted
could not create IPv4 socket for address "127.0.0.1": Operation not permitted
FATAL: could not create any TCP/IP sockets
```

No se solicita ni se da por obtenida una autorización de sistema que este entorno no permite. La aplicación WSGI importa correctamente y las vistas públicas/seguridad sin BD fueron ejecutadas mediante el cliente de pruebas Django. Esto **no certifica** que el servidor haya iniciado ni que las transacciones concurrentes hayan pasado.

## Cobertura definida: 67 pruebas

- `test_unit.py` (23): RUT y teléfono, fecha, login español/CSRF, redirección de acceso, logout POST, bloqueo anónimo en todos los endpoints, rutas/templates, HTTPS, validaciones tempranas de intervalos/fechas, compilación de rangos PostgreSQL, extensión y matriz de permisos.
- `test_api.py` (41): CRUD, tutor-mascotas, duplicados, filtros/paginación, auditoría/dashboard, altas/ediciones/cancelación de citas, intervalos y disponibilidad, exclusión PostgreSQL incluso con bulk_create, fichas/impresión, vacunas/avisos/SMTP, sesiones/perfil/roles y Admin. Incluye carga de demo y rechazo de sobrescritura.
- `test_concurrency.py` (3): dos reservas del mismo veterinario, dos reservas de la misma mascota con profesionales distintos, reserva contra reducción simultánea de disponibilidad. Usa `TransactionTestCase`, barrera y conexiones independientes, sin SQLite ni mocks de bloqueo.

Las 44 pruebas que necesitan PostgreSQL se encuentran implementadas pero **pendientes de ejecución efectiva**. Los tests SMTP usan un mock del servidor de correo y no prueban entrega real por Internet.

## Reproducir la suite completa

En Debian/Ubuntu con PostgreSQL operativo y `.env` configurado:

```bash
sudo -u postgres psql -c 'ALTER ROLE petcare CREATEDB;'
.venv/bin/python manage.py check
.venv/bin/python manage.py makemigrations --check --dry-run
.venv/bin/python manage.py migrate
.venv/bin/python manage.py test --verbosity 2
.venv/bin/python manage.py collectstatic --noinput
DEBUG=False HTTPS_ENABLED=True .venv/bin/python manage.py check --deploy --fail-level WARNING
```

También está preparado `bash scripts/verificar.sh` y el workflow `.github/workflows/tests.yml` con un contenedor PostgreSQL 17. Ninguno se ha ejecutado en GitHub durante esta sesión. El workflow no usa credenciales reales; la confianza PostgreSQL allí solo corresponde a un servicio de CI efímero, no a producción.

## Evidencias que faltan antes de la entrega final

1. Aplicar migraciones reales en PostgreSQL y guardar `showmigrations`.
2. Ejecutar los 67 tests completos y corregir cualquier fallo que aparezca.
3. Levantar el servidor y verificar cada recorrido con navegador, incluidos móvil y permisos.
4. Instalar Gunicorn desde requirements y comprobar Nginx/systemd en EC2.
5. Validar SMTP real si se configura, timer y acceso público externo.
6. Adjuntar IP real, capturas auténticas y resultados de AWS.

La prueba visual no pudo realizarse porque no hay servidor escuchando. No se incluyen imágenes de la aplicación que aparenten verificación inexistente.
