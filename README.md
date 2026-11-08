# PetCare · Sistema de Gestión de Citas y Fichas Médicas

Proyecto académico para Evaluación Parcial N.º 3 de Desarrollo Backend, INACAP. Docente indicado en el enunciado: Marcelo Alvarado Aravena.

**Estado del rediseño (2026-11-05):** portal de tutores, relación opcional Tutor–User, permisos por objeto, recuperación de contraseña, límites compartidos de autenticación y personalización del administrador implementados. La base existente se conserva: solo se añaden las migraciones `0002_tutor_usuario` y `0003_loginwindow`. Ver resultados efectivos en [verificación del rediseño](docs/redisenio.md). El entorno no permite abrir sockets, por lo que la aplicación con PostgreSQL, la suite de integración y la revisión visual requieren ejecución en Debian. No se ha desplegado en AWS.

## Problema y objetivo

La gestión en papel provoca pérdidas de fichas, solapamientos de horas y falta de seguimiento preventivo. PetCare centraliza tutores y mascotas, agenda por profesional, atenciones clínicas y vacunación con recordatorios, con un portal privado para tutores y un espacio de gestión para personal autorizado.

## Tecnologías y arquitectura

- Python 3.13; Django 5.2.17; Django REST Framework 3.18.1.
- PostgreSQL 14 o superior y Psycopg 3.3.6. No existe configuración SQLite de respaldo.
- Django Templates, HTML/CSS/JavaScript y Fetch API. Calendario propio con día/semana/mes, sin CDN ni dependencia de FullCalendar.
- Autenticación, sesiones, hash PBKDF2, CSRF y grupos de Django.
- Producción: Ubuntu EC2 + Nginx + Gunicorn + PostgreSQL local + systemd/timer.

La compatibilidad de Python 3.13 está documentada por [Django](https://docs.djangoproject.com/en/5.2/releases/5.2/) y [DRF](https://www.django-rest-framework.org/community/3.16-announcement/). Diagrama y decisiones en [arquitectura](docs/arquitectura.md); relaciones en [modelo ER](docs/modelo-er.md).

## Instalación local en Debian

Requisitos: Debian 13 con Python 3.13, acceso sudo para instalar paquetes, PostgreSQL 14+ y conexión a Internet para instalar dependencias. El script también sirve en Ubuntu si se configura `PYTHON_BIN` con Python 3.13. No ejecuta migraciones ni sobrescribe `.env`.

```bash
cd /home/chororemy/Proyectos/PetCare
bash scripts/instalar_dependencias.sh
sudo systemctl enable --now postgresql
```

Si prefieres instalar manualmente:

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-dev libpq-dev postgresql postgresql-contrib nginx
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/configurar_local.py
```

`configurar_local.py` crea una clave aleatoria y un `.env` de permisos 600; no imprime la clave. La carpeta `.venv` existente en el equipo de construcción contiene dependencias copiadas de un entorno local porque no había DNS disponible; **una instalación nueva debe ejecutar pip según requirements.txt**, incluido Gunicorn, que no estaba disponible en dicho equipo.

### PostgreSQL

Crear un usuario y la base, asignando una contraseña en el prompt interactivo, sin incluirla en el historial de comandos:

```bash
sudo -u postgres createuser --pwprompt petcare
sudo -u postgres createdb --owner=petcare petcare
sudo -u postgres psql -d petcare -c 'CREATE EXTENSION IF NOT EXISTS btree_gist;'
nano .env
```

Configura `DB_NAME=petcare`, `DB_USER=petcare`, `DB_PASSWORD` con la contraseña elegida, `DB_HOST=127.0.0.1`, `DB_PORT=5432`. Conserva `DEBUG=True` y `HTTPS_ENABLED=False` únicamente para desarrollo. PostgreSQL debe escuchar solo en localhost; no abras el puerto 5432. Detalle, permisos de pruebas y backups en [PostgreSQL](docs/postgresql.md).

### Inicializar y levantar

```bash
.venv/bin/python manage.py check
.venv/bin/python manage.py migrate
.venv/bin/python manage.py createsuperuser
.venv/bin/python manage.py cargar_demo
.venv/bin/python manage.py runserver 127.0.0.1:8000
```

Abrir **http://127.0.0.1:8000/**. Administrador: **http://127.0.0.1:8000/admin/**. API navegable autenticada: **http://127.0.0.1:8000/api/**.

Los comandos anteriores están listos para ejecutar en tu Debian fuera del entorno restringido; el arranque con BD **no pudo completarse aquí**. `migrate` es obligatorio antes de acceder al sistema. No ejecutar `legacy/server.py`: es el prototipo anterior y no pertenece a la aplicación final.

### Datos de demostración

`cargar_demo` crea `demo_admin`, `demo_vet` y `demo_recepcion` con contraseñas aleatorias independientes, mostradas una sola vez en la terminal. Guarda esas contraseñas de forma privada. El comando rechaza bases que ya contienen tutores o cuentas demo y no sobrescribe datos. Usa nombres ficticios, correos `example.invalid`, RUT de prueba y textos clínicos sin validez médica.

Opcionalmente se admite la variable `PETCARE_DEMO_PASSWORD`, que pasa por los validadores de Django. No se debe agregar su valor a Git, capturas ni documentación. Las contraseñas pueden restablecerse con:

```bash
.venv/bin/python manage.py changepassword demo_vet
```

El administrador demo tiene el grupo Administrador y acceso al Admin. Puedes usar en su lugar el superusuario que creaste. Para agregar otro veterinario desde la interfaz: crear usuario con rol Veterinario → crear perfil profesional vinculado → crear disponibilidad. El rol queda operativo cuando tiene un perfil activo.

## Funcionalidades

1. **Tutores:** CRUD, nombres/apellidos, RUT con módulo 11 y unicidad normalizada, contacto, dirección, búsqueda y relación con varias mascotas.
2. **Mascotas:** CRUD, tutor, especie/raza/sexo, nacimiento, peso positivo y observaciones. Detalle con historial y vacunas.
3. **Agenda:** calendario diario/semanal/mensual, filtro por profesional/estado, altas/ediciones/cancelación, franjas semanales. Validación transaccional por veterinario y mascota; citas canceladas liberan el horario. Intervalos adyacentes son válidos.
4. **Fichas:** motivo, síntomas, diagnóstico, tratamiento, receta, exámenes, resultados y observaciones. Fecha/profesional/cita opcional. Consulta, edición por autor veterinario o administrador e impresión/PDF del historial con protección de acceso.
5. **Vacunas:** aplicaciones y próxima dosis, filtro próximas/atrasadas, seguimiento cerrado y recordatorio automático idempotente.
6. **Recordatorios:** controles manuales, avisos de vacunas, estado atendido, alertas internas y envío SMTP opcional desde comando programado.
7. **Dashboard:** tutores, mascotas, citas del día, próximas citas, vacunas pendientes y actividad reciente sin textos clínicos en la auditoría.
8. **Usuarios:** login/logout con CSRF y sesiones; grupos; perfil editable; cambio de contraseña con contraseña actual; gestión administrativa de usuarios y desactivación.
9. **Admin:** todos los modelos, filtros, búsquedas, relaciones, campos de solo lectura e inlines.

Las tablas y la agenda se actualizan cada 15 segundos cuando la página está visible y no hay formularios abiertos. Esto es sondeo periódico, no WebSockets. La disponibilidad se valida en el servidor en cada escritura.

## Permisos

| Acción | Administrador | Veterinario activo | Recepcionista |
|---|---|---|---|
| Tutores y mascotas (CRUD) | Sí | Sí | Sí |
| Agenda (consultar/crear/editar/cancelar) | Sí | Sí | Sí |
| Eliminar citas permanentemente | Sí, sin ficha relacionada | No | No |
| Consultar fichas e imprimir | Sí | Sí | No |
| Crear/editar fichas y vacunas | Sí | Solo bajo su perfil; editar las propias | No |
| Eliminar fichas y vacunas | Sí | No | No |
| Consultar vacunas/avisos | Sí | Sí | Sí |
| Crear controles/marcar atendidos | Sí | Sí | Sí |
| Modificar disponibilidad | Sí | Solo la propia | No |
| Gestionar profesionales/usuarios | Sí | No | No |
| Cambiar su perfil y contraseña | Sí | Sí | Sí |

La API devuelve 403 a anónimos con autenticación de sesión de DRF. La aplicación HTML redirige al login. Los permisos se verifican en el backend; ocultar botones solo mejora la interfaz. Las bajas con dependencias devuelven 409 para conservar relaciones e historial. Las cuentas se desactivan; no se eliminan desde la API de usuarios.

## API REST

Todos los recursos tienen lista y detalle (`/api/recurso/<id>/`) con GET/POST/PUT/PATCH/DELETE según permisos:

| Endpoint | Búsqueda / filtros |
|---|---|
| `/api/tutores/` | `search` nombre, apellidos, RUT, correo, teléfono |
| `/api/mascotas/` | `search`, `tutor`, `especie` |
| `/api/veterinarios/` | `search` nombre/especialidad |
| `/api/disponibilidades/` | `veterinario`, `dia` (lunes=0) |
| `/api/citas/` | `search`, `mascota`, `veterinario`, `estado`, `desde`, `hasta` |
| `/api/fichas/` | `search`, `mascota`, `veterinario` |
| `/api/vacunas/` | `search`, `mascota`, `veterinario`, `seguimiento=vencidas\|proximas` |
| `/api/recordatorios/` | `search`, `mascota`, `estado`, `tipo` |
| `/api/usuarios/` | Solo administrador; `search`; desactivar con PATCH |

También: `GET /api/dashboard/`, `GET/PATCH /api/perfil/`, `POST /api/citas/<id>/cancelar/`, `POST /api/recordatorios/<id>/atender/`.

Paginación: 20 resultados por página, `?page=2`, respuesta `{count,next,previous,results}`. Orden: `?ordering=nombre` en mascotas, `?ordering=fecha,hora_inicio` en citas. Escrituras JSON y cabecera `X-CSRFToken`, usando cookie de sesión del login. Errores: 400 validación, 403 permisos/CSRF, 404 inexistente, 409 integridad/relación protegida. Contrato y ejemplos en [casos de uso](docs/casos-de-uso.md).

## Pruebas y migraciones

Para ejecutar tests, el usuario PostgreSQL necesita crear una base temporal. Conceder solo en desarrollo:

```bash
sudo -u postgres psql -c 'ALTER ROLE petcare CREATEDB;'
.venv/bin/python manage.py check
.venv/bin/python manage.py makemigrations --check --dry-run
.venv/bin/python manage.py migrate
.venv/bin/python manage.py test --verbosity 2
.venv/bin/python manage.py collectstatic --noinput
.venv/bin/python manage.py check --deploy
```

O ejecutar `bash scripts/verificar.sh` (requiere Node únicamente para verificar sintaxis JavaScript; instalarlo con `sudo apt-get install nodejs` si falta). Pruebas independientes de conexión: `.venv/bin/python manage.py test clinica.tests.test_unit`.

En cambios de modelos: `makemigrations clinica`, revisar la migración, probar y luego `migrate`. La migración inicial incluye `btree_gist`. No modificar manualmente tablas ni usar el antiguo `schema.sql`. CI con PostgreSQL está definido en `.github/workflows/tests.yml`; no ha sido ejecutado en GitHub desde esta sesión.

## Recordatorios y correo

```bash
.venv/bin/python manage.py generar_recordatorios
.venv/bin/python manage.py generar_recordatorios --enviar
```

Las vacunas generan su aviso al guardarse y el comando reconcilia el seguimiento. Configura SMTP en `.env` con `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`. Se usa STARTTLS y nunca se devuelven credenciales al navegador. Sin SMTP, los recordatorios siguen visibles; el comando informa que no se envió correo. Los envíos aplican a pendientes cuya fecha sea dentro de los próximos 7 días o esté vencida. Se conserva la fecha de envío para evitar reenvíos normales; SMTP no garantiza entrega exactamente una vez ante fallos posteriores al envío.

Para ejecución automática usa el timer de `deploy/` o cron según [EC2](docs/despliegue-ec2.md). El servidor web por sí solo no ejecuta un bucle de correo.

## Despliegue EC2 y evidencias académicas

- Guía reproducible: [despliegue EC2](docs/despliegue-ec2.md).
- IP pública real: **PENDIENTE — completar al crear la instancia**.
- URL pública: **PENDIENTE — sin despliegue realizado**.
- Datos e instalación PostgreSQL: [guía](docs/postgresql.md).
- Defensa, pruebas manuales y capturas: [guía de defensa](docs/defensa-oral.md).
- Uso de IA y prompts reales disponibles: [prompts_ia.md](prompts_ia.md).
- Correspondencia de requisitos y evidencias: [matriz de evaluación](docs/matriz-evaluacion.md).

Incorporar capturas propias en `docs/capturas/` después de levantar la aplicación: login, dashboard, CRUD, calendario, error de solapamiento, ficha/impresión, vacunas, Admin y terminal de tests. No se incluyen capturas fabricadas ni resultados de pruebas que no se hayan ejecutado.

## Estructura de entrega

```text
manage.py                  Entrada Django
petcare/                   Settings, URLs y WSGI
clinica/                   Modelos, API, permisos, Admin, servicios y tests
clinica/migrations/        Esquema PostgreSQL versionado
clinica/management/        Comandos de demo y recordatorios
templates/                 Login, aplicación y reporte imprimible
static/                    CSS preservado/ampliado y JavaScript Fetch
scripts/                   Instalación, configuración y verificación
deploy/                    Gunicorn, Nginx y servicios/timer systemd
docs/                      Arquitectura, ER, casos, despliegue y resultados
legacy/                    Prototipo previo conservado; no se ejecuta
.github/workflows/         Pruebas reproducibles con PostgreSQL
```

## Límites y pendientes verificables

- Falta ejecutar migraciones, suite con BD y prueba visual en un entorno que permita sockets; no se sustituyó PostgreSQL por SQLite ni por mocks para declarar los tests aprobados.
- Falta instalar/verificar Gunicorn en un entorno con red. Nginx/systemd/EC2 están preparados, no instalados ni activados desde esta sesión.
- La documentación sigue el enunciado recibido; no se adjuntó la rúbrica oficial en PDF, por lo que la calificación EXCELENTE depende de la revisión docente y de las evidencias pendientes.
- Disponibilidad semanal recurrente; no hay feriados, bloqueos excepcionales o portal de tutores.
- La interfaz carga listas de referencia completas para los selectores; para clínicas grandes conviene autocompletado remoto. Las tablas y agenda usan endpoints paginados.
- El envío SMTP real y certificados HTTPS requieren configuración externa; recepción solo registra datos administrativos de mascotas y no consulta las fichas.


## Portal Tutor y continuidad de cuentas

Registro público: `/registro/`. Sesiones: `/login/` y `/logout/` (solo POST). Recuperación: `/recuperar/`, token Django con vencimiento de una hora, invalidado al cambiar contraseña. Configurar SMTP real en producción; sin SMTP el backend de desarrollo imprime el correo en la terminal y no lo entrega al destinatario.

El registro ignora cualquier rol o privilegio enviado: crea exclusivamente Tutor, sin `is_staff` ni `is_superuser`. La relación opcional `Tutor.usuario` conserva todos los tutores y mascotas anteriores. **No se vinculan historiales por coincidencia de correo o nombre.** Un responsable debe verificar la identidad y ejecutar:

```bash
.venv/bin/python manage.py vincular_tutor USUARIO ID_TUTOR
```

El comando impide sobrescribir vínculos y rechaza cuentas clínicas/técnicas. Si `recepcion` debe ser tutor, verificar primero su identidad y el ID del tutor correspondiente y usar ese comando; retira exclusivamente el grupo Recepcionista. Si sigue siendo personal de recepción, asignar desde el superusuario el grupo Recepcionista y conservar ese flujo. No se conceden privilegios administrativos para resolver un 403.

| Rol | Interfaz y permisos |
|---|---|
| Tutor | Inicio con cuatro tarjetas, `/mi-cuenta/`, `/mis-mascotas/`, `/reservar/`, `/mis-citas/`, `/cuidados/`, historial propio en lectura |
| Veterinario | Dashboard clínico, agenda, pacientes, fichas, vacunas y controles; escrituras clínicas bajo su propio perfil |
| Recepcionista | Compatibilidad con gestión administrativa de agenda; sin escritura clínica ni lectura de fichas |
| Administrador | Gestión de la clínica y cuentas autorizadas |
| Superusuario | Administración técnica Django |

El Django Admin exige cuenta activa con `is_staff`, rol clínico autorizado y permisos Django. Ser staff no concede autorización clínica. Usuarios y grupos solo se administran con rol Administrador. Las reservas del tutor duran 30 minutos, admiten un horizonte de 180 días y quedan Pendientes. Solo puede cancelar reservas Pendientes/Confirmadas antes del inicio; para reprogramar debe cancelar y reservar nuevamente. El personal mantiene la gestión de duraciones y estados existente. Un horario visible puede ocuparse simultáneamente: la transacción y las exclusiones PostgreSQL deciden al guardar.

La API conserva routers, paginación, búsqueda, filtros y CRUD existentes. Los querysets del Tutor filtran propiedad antes de resolver identificadores; serializers verifican mascota, propietario, estado y plazo, y rechazan escrituras clínicas. El dashboard con datos globales está reservado al personal. Pruebas nuevas: `clinica/tests/test_portal.py`.

Consulta [rediseño y verificación](docs/redisenio.md), [seguridad operativa](docs/seguridad-operativa.md) y [defensa oral](docs/defensa-oral.md).
