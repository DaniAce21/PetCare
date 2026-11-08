# Matriz de requisitos y evidencias

Se contrasta el enunciado recibido, no una rúbrica PDF no disponible. No implica asignación de calificación.

| Criterio solicitado | Implementación / ubicación | Evidencia disponible / pendiente |
|---|---|---|
| Django funciona | `petcare/`, `manage.py`, templates | Check sin errores; WSGI importa; faltan servidor con BD y navegador |
| PostgreSQL conectado | settings exclusivamente PostgreSQL, Psycopg | Configuración y binarios presentes; conexión bloqueada por restricción de sockets |
| Migraciones aplicadas | `clinica/migrations/0001_initial.py` con btree_gist | Generada, sin cambios pendientes; migrate no pudo conectarse |
| Admin completo | `clinica/admin.py` | Modelos, inlines, filtros y búsquedas; check pasa; pruebas con BD pendientes |
| Tutores y mascotas | Modelos/serializers/ViewSets + formularios Fetch | CRUD, RUT, relaciones y validaciones implementados; integración pendiente |
| Agenda | `Cita`, `Disponibilidad`, calendario día/semana/mes | Transacciones, bloqueos y exclusiones; SQL de rangos compila; tests reales pendientes |
| Fichas clínicas | `FichaClinica`, API, historial y template imprimible | Autoría/permisos implementados; prueba con sesión y BD pendiente |
| Vacunas/recordatorios | Modelos, señales, servicios, comando, timer | Idempotencia y cierre/atendido implementados; integración/SMTP externo pendientes |
| API REST | ModelSerializer/ViewSets/router, filtros/búsquedas/paginación | Acceso anónimo bloqueado probado; CRUD autenticado pendiente de BD |
| Usuarios y roles | Auth/sesiones/CSRF Django y permisos propios | Login público/CSRF y matriz de roles sin BD probados; login real/acciones pendientes |
| Diseño e interfaz | Templates, CSS adaptado, JS real a API | Sintaxis/templates verificados; revisión visual/responsive pendiente |
| Pruebas | `clinica/tests/`, CI PostgreSQL | 67 definidas, 23 aprobadas sin BD; 44 de integración/concurrencia pendientes |
| Despliegue | `deploy/`, scripts y guía EC2 | Archivos preparados; Nginx reconoce sintaxis pero no puede abrir socket aquí; sin AWS |
| Entrega académica | README, arquitectura, ER, casos, pruebas, defensa, prompts | Documentos incluidos, IP y capturas reales pendientes |

Antes de presentar como proyecto operativo: ejecutar `scripts/verificar.sh` en Debian/Ubuntu con PostgreSQL, resolver cualquier fallo, realizar prueba manual con los tres roles y adjuntar las evidencias externas. No existe una certificación de nivel EXCELENTE en esta entrega.
