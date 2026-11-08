# Actualización posterior de PetCare en EC2

Procedimiento preparado localmente el 2026-11-08. No se ha conectado a AWS ni ejecutado estos pasos. Destino existente: `/srv/petcare`, https://petcare-inacap.duckdns.org.

## Preparación y respaldo

1. Autorizar una ventana de mantenimiento y registrar el SHA actual y el SHA aprobado. Identificar el servicio Gunicorn real con `systemctl cat` (la plantilla usa `petcare`), usuario, entorno virtual, rutas estáticas y nombre/propietario reales de PostgreSQL. No asumir que las plantillas coinciden con producción.
2. Verificar espacio libre y disponer de una segunda sesión administrativa. Detener temporalmente escrituras web y tareas de recordatorios durante el respaldo y la actualización. No modificar Nginx, systemd ni certificados para esta actualización.
3. En un directorio privado fuera de `/srv/petcare`, con permisos 700 y `umask 077`, respaldar el código actual, `.env`, entorno de dependencias y archivos estáticos recolectados. El respaldo de `.env` contiene secretos: permisos 600 y nunca Git. Conservar aparte las configuraciones actuales de Nginx y systemd, sin reemplazarlas.
4. Respaldar la base real con `pg_dump --format=custom --file=RUTA_PRIVADA DB_REAL`, usando autenticación interactiva o archivo privado; nunca poner la contraseña en el comando. Comprobar código de salida y `pg_restore --list`. Ensayar restauración en una base aislada antes de una actualización de esquema. No usar la base de producción para ensayos.

## Preparar y aplicar el código

5. Descargar el commit aprobado en un directorio de preparación separado. Comprobar SHA, cambios y requisitos antes de tocar `/srv/petcare`. Si el servidor aún no usa Git, no ejecutar `git init`, `git pull` ni clonar encima de sus archivos existentes.
6. Revisar diferencias contra el respaldo. Aplicar únicamente archivos de aplicación revisados, conservando `/srv/petcare/.env`, `.venv`, datos, archivos subidos y configuración propia del servidor. No copiar `deploy/` sobre `/etc`, ni tocar certificados. Conservar los archivos sustituidos en el respaldo; no usar `rsync --delete`, `git clean` ni `reset --hard`.
7. Si cambió `requirements.txt`, preparar y verificar dependencias antes del cambio, conservando el entorno anterior para reversión. No actualizar versiones ajenas al commit.
8. Como usuario del servicio, desde `/srv/petcare`, ejecutar `.venv/bin/python manage.py check` y `.venv/bin/python manage.py migrate --plan`. Comparar también las migraciones con el código anterior. Ejecutar `migrate --noinput` solo si hay migraciones pendientes revisadas y necesarias. No generar migraciones en producción. Esta corrección del calendario no cambia el esquema.
9. Si cambiaron estáticos (en esta entrega sí cambia `static/app.js`), ejecutar `.venv/bin/python manage.py collectstatic --noinput`, conservando previamente el respaldo de `staticfiles`. No usar `--clear`.
10. Reiniciar únicamente el servicio Gunicorn identificado. Consultar `systemctl is-active`, estado y logs recientes sin publicar secretos. Ejecutar `check --deploy` con el entorno real. Hacer una comprobación HTTPS de `/login/` y acceso autenticado antes de permitir nuevas escrituras.

## Aceptación

11. Comprobar en navegador calendario diario/semanal/mensual, consulta histórica sin controles de modificación, fecha/hora de Santiago, rechazo de reservas pasadas mediante UI y HTTP manipulado, disponibilidad y rechazo de solapamientos. Usar cuentas de prueba y una mascota autorizada, sin alterar historiales reales.
12. Comprobar tutor (solo mascotas propias, reserva/cancelación futura) y veterinario (alcance clínico autorizado), login, CSRF y estáticos. Rehabilitar tráfico y tareas solo si todas las comprobaciones pasan. Registrar SHA, hora, responsable y resultados. No ejecutar `manage.py test` contra PostgreSQL productivo.

## Reversión

13. Ante un fallo, mantener bloqueadas las escrituras y detener Gunicorn/tareas. Restaurar desde el respaldo los archivos de código sustituidos, el entorno de dependencias y los estáticos anteriores. Conservar el `.env` productivo. Reiniciar el servicio y repetir las comprobaciones.
14. Si no hubo migraciones, no restaurar ni modificar PostgreSQL. Si hubo cambios de esquema, determinar previamente si el código anterior es compatible o si la migración tiene reversión revisada. No ejecutar migraciones inversas a ciegas. Una restauración de base requiere aprobación específica, ventana sin escrituras y respaldo del estado fallido; podría perder datos posteriores al respaldo. Preferir recuperar en una base separada y verificarla antes de cambiar la conexión.
15. Conservar los respaldos y el registro de cambios hasta la aceptación. No eliminar registros para resolver conflictos de reservas.
