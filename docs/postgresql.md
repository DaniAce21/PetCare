# PostgreSQL, migraciones y respaldos

PetCare necesita PostgreSQL 14+; el entorno de construcción contiene binarios 17.11. Nunca usa SQLite para pruebas ni desarrollo final.

## Crear base y rol

```bash
sudo systemctl enable --now postgresql
sudo -u postgres createuser --pwprompt petcare
sudo -u postgres createdb --owner=petcare petcare
sudo -u postgres psql -d petcare -c 'CREATE EXTENSION IF NOT EXISTS btree_gist;'
```

La contraseña se ingresa interactivamente; copiarla a `.env` (permisos 600) sin incluirla en Git. Los ejemplos no proporcionan contraseñas compartidas.

```text
DB_NAME=petcare
DB_USER=petcare
DB_PASSWORD=<la elegida en el prompt>
DB_HOST=127.0.0.1
DB_PORT=5432
```

No copiar los signos `< >`. `pg_hba.conf` debe exigir `scram-sha-256` para `127.0.0.1/32` y `::1/128`. Conservar reglas `peer` para administración local de postgres. `listen_addresses = 'localhost'`. Ubicación habitual: `/etc/postgresql/<VERSION>/main/`. Reiniciar PostgreSQL después de cambios. La guía usa el rol propietario en un único equipo académico; separar usuario de migraciones y usuario de runtime sería una mejora para producción de mayor escala.

Verificar:

```bash
pg_isready -h 127.0.0.1 -p 5432
psql -h 127.0.0.1 -U petcare -d petcare -W -c 'SELECT version();'
.venv/bin/python manage.py migrate
.venv/bin/python manage.py showmigrations
```

`btree_gist` permite igualdad de IDs en las restricciones de exclusión del calendario. La migración incluye `BtreeGistExtension()`; se puede preinstalar como postgres si el rol no tiene permisos de extensión. No usar `--fake` para saltar un fallo real.

## Base de pruebas

Django crea `test_petcare` y la elimina al terminar. **Nunca configurar `DB_TEST_NAME=petcare`.** Conceder `CREATEDB` solo en desarrollo:

```bash
sudo -u postgres psql -c 'ALTER ROLE petcare CREATEDB;'
.venv/bin/python manage.py test --verbosity 2
```

El rol propietario de la BD temporal puede instalar la extensión confiable `btree_gist`. Si una política del servidor lo impide, el administrador debe precrear la base/ extensión y usar `--keepdb`, conservando la separación respecto a la BD de aplicación. En EC2 productivo no se necesitan permisos `CREATEDB` para servir la web:

```bash
sudo -u postgres psql -c 'ALTER ROLE petcare NOCREATEDB;'
```

## Migraciones futuras

```bash
.venv/bin/python manage.py makemigrations clinica
.venv/bin/python manage.py makemigrations --check --dry-run
.venv/bin/python manage.py migrate --plan
.venv/bin/python manage.py migrate
```

Versionar los archivos de migración; revisar las operaciones destructivas antes de ejecutarlas. No ejecutar `legacy/schema.sql`. Las bases y registros existentes deben conservarse. La conexión no pudo comprobarse desde el entorno restringido; no se ejecuta reinicialización.

## Respaldo

```bash
pg_dump -h 127.0.0.1 -U petcare -W -Fc petcare -f petcare.backup
```

La copia contiene datos personales y clínicos: guardarla fuera del repositorio, con acceso restringido y cifrado al moverla. Para ensayar recuperación usar otra base vacía:

```bash
sudo -u postgres createdb --owner=petcare petcare_restore
pg_restore -h 127.0.0.1 -U petcare -W -d petcare_restore petcare.backup
```

Documentar fecha/resultado del ensayo. No sobrescribir la BD clínica con un restore de demostración.


## Separar migraciones de runtime

En una instalación ya existente no recrear la base ni el propietario. Como administrador PostgreSQL, crear un rol separado y asignar contraseña interactivamente con `\password petcare_runtime`:

```sql
CREATE ROLE petcare_runtime LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE;
GRANT CONNECT ON DATABASE petcare TO petcare_runtime;
-- Dentro de la base petcare:
GRANT USAGE ON SCHEMA public TO petcare_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO petcare_runtime;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO petcare_runtime;
ALTER DEFAULT PRIVILEGES FOR ROLE petcare IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO petcare_runtime;
ALTER DEFAULT PRIVILEGES FOR ROLE petcare IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO petcare_runtime;
```

Adaptar los nombres al propietario real. Revisar que PUBLIC no conceda CREATE en el esquema antes de usar runtime. Ejecutar migraciones con el propietario existente y usar DB_USER=petcare_runtime en el servicio. No guardar credenciales del propietario en la configuración de runtime. El rol de pruebas debe ser separado y poder crear únicamente bases temporales en el entorno de desarrollo.

Antes de migrar esta entrega, generar un `pg_dump -Fc` privado y verificar el archivo con `pg_restore --list`. Las migraciones 0002 y 0003 añaden una columna nullable y una tabla; no eliminan datos clínicos. La vinculación de cuentas se realiza explícitamente con `vincular_tutor`.
