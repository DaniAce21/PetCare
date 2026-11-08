# Verificación local del calendario — 2026-11-08

- `manage.py check`: sin observaciones.
- `manage.py test --keepdb --noinput`: 95 pruebas aprobadas, 111.634 segundos.
- Pruebas ejecutadas con PostgreSQL 17 aislado en `/tmp/petcare-review-pg`, puerto 55439, base `test_petcare_review`. Se conserva la base; no se usó la base clínica. El rol configurado en el `.env` local no tiene CREATEDB; no se alteraron sus privilegios. El sandbox requiere autorización para abrir conexiones locales.
- `node --test tests/calendar-time.cjs`: aprobado; prueba límites de hora de Santiago, vistas históricas y ausencia de controles de modificación/cancelación/eliminación en detalle histórico.
- `node --check static/app.js`: aprobado.
- `makemigrations --check --dry-run`: sin cambios; ejecutar también con conexión aislada para verificar consistencia.
- Revisión del contenido preparado: patrones de claves privadas/tokens y comparación con SECRET_KEY y DB_PASSWORD locales sin imprimir valores; no se detectaron secretos reales. `.env.example` tiene valores de ejemplo o vacíos.
- Se preservan las validaciones de disponibilidad, exclusiones PostgreSQL de profesional/mascota y bloqueos transaccionales. Se impide reabrir como pendiente/confirmada una cita histórica completada o cancelada.
- El calendario histórico conserva consulta y acceso clínico autorizado, pero oculta controles de cambio de cita y eliminación. Las correcciones deliberadas de estados históricos por personal autorizado siguen disponibles en el backend.
- No se hizo una comprobación visual interactiva en navegador ni se accedió a AWS.

Despliegue posterior: [procedimiento de actualización y reversión](actualizacion-aws.md).
