# Guía de defensa oral y demostración

## Relato sugerido

1. Explicar el problema de papel: duplicidad de horas, fichas perdidas, seguimiento tardío.
2. Mostrar arquitectura Django Templates/Fetch → DRF/ORM → PostgreSQL. Señalar sesiones y CSRF, sin credenciales de base de datos en JS.
3. Mostrar ER: tutor 1:N mascotas, veterinario 1:N franjas/citas, ficha opcional 1:1 cita, vacuna 1:1 recordatorio.
4. Demostrar un recorrido real: tutor → mascota → reserva → atención → vacuna → recordatorio.
5. Abrir dos sesiones e intentar el mismo horario; explicar bloqueo de filas estables y exclusión GiST de rangos `[)`.
6. Cambiar de administrador a recepción e intentar consultar fichas; mostrar 403 de backend y no solo un botón oculto.
7. Enseñar el Admin, `showmigrations`, tests y configuración de despliegue.
8. Distinguir explícitamente lo implementado de lo verificado: esta sesión no pudo conectar PostgreSQL/levantar servidor y no desplegó EC2. Completar esas pruebas antes de afirmar cumplimiento operativo.

## Preguntas técnicas

**¿Por qué PostgreSQL?** Es obligatorio en el enunciado, aporta ORM transaccional, bloqueos de fila y exclusiones de intervalos para impedir solapamientos incluso si una escritura omite validaciones de la API.

**¿Por qué no basta con consultar citas antes de insertar?** Dos peticiones pueden consultar una agenda vacía al mismo tiempo. Se bloquean veterinario y mascota dentro de la transacción, y PostgreSQL aplica restricciones de exclusión al final.

**¿Cómo funciona el límite de intervalos?** Se ocupa `[inicio,fin)`, por lo que una cita que termina a las 10:30 no impide otra que empieza exactamente a las 10:30. Canceladas no bloquean.

**¿Se validan las ediciones?** Sí; el modelo usa las mismas reglas dentro de la transacción y bloquea recursos antiguos/nuevos. No se permite modificar el origen de una atención ya asociada.

**¿Por qué PROTECT?** Evita borrar accidentalmente el tutor o paciente que sostiene una historia clínica. La API comunica conflicto 409. Las cuentas se desactivan.

**¿Dónde están las contraseñas?** Hash seguro oficial de Django, nunca texto plano. SECRET_KEY, contraseña PostgreSQL y SMTP están en `.env`, ignorado por Git; la demo genera claves y las muestra una sola vez.

**¿Qué diferencia hay entre autenticación y autorización?** La sesión identifica al usuario; grupos y permisos de objeto limitan sus acciones. Recepción autenticada aún recibe 403 para fichas.

**¿El calendario está en tiempo real?** Actualiza mediante sondeo cada 15 segundos y valida cada escritura en servidor. No utiliza WebSockets; esa diferencia debe explicarse con precisión.

**¿Cómo se programan avisos?** Señal al guardar una vacuna y comando idempotente de reconciliación con timer/cron. Los correos requieren SMTP; el sistema funciona con notificaciones internas si no se configura.

**¿Se garantiza exactamente un correo?** Se evita reenvío ordinario con fecha de envío y bloqueo, pero un fallo entre aceptación SMTP y commit puede duplicarlo. Es semántica de al menos una vez.

**¿Qué hace collectstatic?** Reúne estáticos de Django/DRF/app en un directorio servido por Nginx con DEBUG=False.

**¿Qué puertos se exponen?** 22 restringido a la IP del estudiante, 80 y 443 cuando corresponda. PostgreSQL 5432 y Gunicorn 8001 permanecen locales.

## Checklist de prueba manual, pendiente de ejecutar con PostgreSQL

- Login de cada rol, logout y cambio de contraseña.
- Registrar/editar/eliminar tutor sin mascota; rechazar RUT duplicado/erróneo.
- Dos mascotas del mismo tutor, peso y nacimiento inválidos rechazados.
- Crear profesional y franjas; reservar y editar cita; probar límite de horario y duración.
- Reservar misma hora con dos clientes; comprobar que solo una operación se confirma.
- Cancelar y volver a reservar; probar citas adyacentes y distintos veterinarios.
- Ficha completa, consulta/edición e impresión; recepción no puede acceder por URL/API.
- Vacuna próxima/atrasada, ejecutar comando dos veces sin duplicar, atender aviso/cerrar seguimiento.
- Buscar/filtrar/paginar y refrescar para demostrar persistencia.
- Admin: listados/inlines; DELETE con historial devuelve conflicto.
- Responsive: 1440×900 y 390×844; teclado, foco de formularios y modales.
- EC2: acceso externo, estáticos, gunicorn.service, timer, TLS si se configura.

## Capturas que deben incorporarse

Crear `docs/capturas/` con imágenes reales tras levantar el sistema: `01-login.png`, `02-dashboard.png`, `03-tutores-mascotas.png`, `04-agenda.png`, `05-solapamiento.png`, `06-ficha.png`, `07-vacunas-recordatorios.png`, `08-admin.png`, `09-tests.png`, `10-ec2.png`. No incluir contraseñas, SECRET_KEY, `.env` ni credenciales AWS. Las capturas no están generadas en esta entrega por falta de servidor operativo.

## Defensa del rediseño: nueve temas obligatorios

1. **Conexión:** `petcare/settings.py` carga `.env` y configura `django.db.backends.postgresql`; Psycopg abre la conexión. Mostrar DB_HOST/NAME sin revelar contraseñas. `CONN_MAX_AGE` reutiliza conexiones; migraciones crean incrementos de esquema.
2. **ORM:** cada clase de `clinica/models.py` corresponde a una tabla. `Mascota.objects.filter(tutor__usuario=request.user)` expresa un JOIN y un WHERE; no se concatenan parámetros SQL. Las relaciones usan claves foráneas y PROTECT conserva historial.
3. **CRUD:** ModelSerializer transforma y valida datos, ModelViewSet proporciona list/retrieve/create/update/destroy y el router construye URLs. El portal usa formularios Django y transacciones. Mostrar crear y editar una mascota propia, recargar y verificar persistencia.
4. **Admin:** branding propio en `templates/admin/`, list_display/list_filter/search_fields, fieldsets, inlines, autocomplete y select_related en `clinica/admin.py`. El admin exige staff y permisos Django además del rol clínico; el Tutor recibe rechazo aunque alguien marque staff accidentalmente.
5. **Permisos:** `role()` usa grupos explícitos y perfiles activos. `get_queryset()` limita por propietario antes de resolver un ID. `PetCarePermission` protege métodos/objetos; serializers rechazan cambio de dueño, estado indebido y suplantación del veterinario. Usar dos tutores y demostrar 404 al pedir una mascota ajena.
6. **Solapamientos:** una validación previa mejora el mensaje pero no basta ante concurrencia. `transaction.atomic`, `select_for_update` y exclusiones PostgreSQL GiST por profesional y mascota conservan la integridad. Las canceladas quedan fuera del índice parcial y se aceptan citas adyacentes `[inicio,fin)`.
7. **API:** sesión y CSRF, querysets filtrados, campos sensibles restringidos, paginación, filtros, throttling y validación del modelo. El Tutor solo solicita citas pendientes o cancela futuras; no edita fichas. Recuperación con token temporal e inválido después del cambio; límite compartido en PostgreSQL por cuenta e IP, sin bloqueos permanentes.
8. **EC2:** Nginx en 80/443 → Gunicorn loopback → Django → PostgreSQL localhost. systemd usa usuario sin root; Security Group no publica 5432 ni 8000/8001. Verificar TLS antes de HSTS, respaldos, journald, Fail2ban y actualizaciones. La instancia no es inmune a saturación volumétrica.
9. **IA:** se utilizó Codex para inspección, implementación, generación de pruebas y documentación, además de consulta de documentación oficial Django. No se usaron agentes secundarios, imágenes generadas ni despliegues AWS automáticos. La documentación distingue pruebas ejecutadas y pruebas bloqueadas por sockets; el estudiante debe explicar y revisar las decisiones.

Para la demostración del portal: registrar Tutor → agregar mascota → reservar (cinco pasos) → clínica confirma y registra atención → Tutor consulta historial y vacunas → probar aislamiento usando un segundo Tutor. Comprobar en móvil y escritorio y registrar capturas reales; todavía no se han tomado capturas ni comprobado un navegador con PostgreSQL desde este entorno.
