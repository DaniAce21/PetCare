# Casos de uso y contrato funcional

## CU01 · Registrar tutor y sus mascotas

Actor: recepción, veterinario o administrador. Iniciar sesión → Tutores → Registrar tutor → completar nombre/apellidos, RUT, contacto y dirección. Si el RUT ya está registrado o tiene un verificador incorrecto, la API devuelve 400 sin crear el registro. Después crear una o más mascotas eligiendo al tutor. Peso positivo y nacimiento no futuro.

Consultar tutor muestra sus mascotas. Editar modifica PostgreSQL mediante PATCH. Eliminar tutor sin dependencias es posible; con mascotas retorna 409 para conservar integridad.

Ejemplo de POST `/api/tutores/` (datos ficticios):

```json
{"nombre":"Camila","apellidos":"Ejemplo","rut":"12.345.678-5","telefono":"+56 9 5555 0101","correo":"camila@example.invalid","direccion":"Dirección ficticia"}
```

Ejemplo de POST `/api/mascotas/` (usar ID real del tutor):

```json
{"tutor":1,"nombre":"Luna","especie":"Perro","raza":"Mestizo","sexo":"Hembra","fecha_nacimiento":"2022-01-01","peso":"12.50","observaciones":"Paciente de demostración"}
```

## CU02 · Agendar y reprogramar

Actor: personal autorizado. Administrador crea usuario Veterinario, su perfil y al menos una franja semanal. En Agenda seleccionar vista día/semana/mes y un profesional opcional, pulsar + Cita. El formulario muestra las franjas del día. La API valida nuevamente dentro de una transacción y retorna 201 o 400 si el horario está ocupado/fuera de disponibilidad. Una colisión detectada por la restricción de PostgreSQL retorna 409.

Modificar usa PATCH y vuelve a comprobar reglas. Cancelar usa acción POST y libera horario. Citas adyacentes son válidas. No se permite desplazar el paciente/profesional de una cita con ficha.

```json
{"mascota":1,"veterinario":1,"fecha":"2030-01-07","hora_inicio":"10:00","hora_termino":"10:30","motivo":"Control ficticio","estado":"Confirmada"}
```

La fecha del ejemplo es lunes y solo será válida si el profesional tiene disponibilidad ese día. Para una demostración real elegir una fecha y franja configuradas en el sistema. Dos navegadores pueden intentar reservar simultáneamente: solo uno debe confirmar si comparten veterinario o mascota.

## CU03 · Atención y ficha

Actor: veterinario o administrador. Mascotas → Ver → Registrar atención, o Fichas → Registrar atención. Guardar fecha, responsable, motivo, síntomas, diagnóstico, tratamiento y los campos adicionales. Cita opcional debe coincidir en mascota y veterinario, y no estar cancelada. Un veterinario no puede suplantar a otro ni editar sus fichas.

Consultar atención muestra receta/exámenes/resultados. Historial imprimible abre `/mascotas/<id>/imprimir/`, usa la sesión y permite imprimir/guardar PDF. Recepción recibe 403 incluso si escribe la URL directamente. Al editar se conserva timestamp de actualización y se registra actividad de la operación, no el texto clínico.

## CU04 · Vacunación y recordatorio

Actor de aplicación: veterinario/administrador. Registrar una vacuna con fechas válidas genera su recordatorio. Volver a ejecutar el comando actualiza el mismo aviso, sin duplicarlo. Vacunas próximas (7 días) o atrasadas se muestran en Dashboard y en filtros. El seguimiento cerrado no aparece como vencido.

Actor de seguimiento: personal autorizado; el Tutor consulta únicamente los avisos propios en lectura. Recordatorios → Atender cambia estado del aviso. No equivale a una vacuna aplicada: cuando se registra una nueva dosis, cerrar el seguimiento previo y agregar la nueva aplicación con su próxima fecha. Los recordatorios automáticos se modifican desde la vacuna de origen; en la pantalla de avisos se cambia su estado. Los controles manuales admiten CRUD y no requieren vacuna.

## CU05 · Acceso y perfil

Login con Django, sin token en localStorage. API usa la cookie de sesión y `X-CSRFToken` en escrituras. Logout solo por POST. Mi perfil permite editar nombre/correo y contraseña; para esta última se necesita la actual. Campos de privilegios enviados al perfil son rechazados. Un administrador crea/desactiva usuarios; sus contraseñas nunca aparecen en respuestas JSON.

## CU06 · Reporte y consulta administrativa

Dashboard agrega indicadores desde ORM y lista actividad reciente. Tablas tienen búsqueda, paginación y filtros. Admin registra todos los modelos y ofrece búsqueda/orden/relaciones. Los datos persistidos se mantienen al recargar/reiniciar el servicio, a diferencia de un prototipo con estado solo en navegador.

## Respuestas de la API

- 200 consulta/actualización; 201 alta; 204 eliminación.
- 400 datos inválidos o regla de negocio; 403 permisos/CSRF; 404 ID desconocido.
- 409 eliminación con dependencias o conflicto de restricción concurrente.
- 429 límite de intentos/login o frecuencia de la API.

La API devuelve listas paginadas. Ejemplos de consulta: `/api/citas/?desde=2030-01-01&hasta=2030-01-31&veterinario=1`, `/api/fichas/?mascota=1`, `/api/vacunas/?seguimiento=vencidas`, `/api/recordatorios/?estado=Pendiente`. Solo se permiten IDs reales y fechas ISO.


## CU07 · Portal privado del Tutor

Registro público siempre crea User y Tutor en una transacción; no acepta roles privilegiados. Login conduce a cuatro tarjetas sin administración. Mis mascotas admite altas/edición e historial propio de lectura. Reservar presenta mascota → profesional → fecha → horario → confirmación. Duración 30 minutos, horizonte 180 días, disponibilidad y ocupación reales; una carrera se resuelve al guardar. Mis citas separa próximas y anteriores/canceladas; solo cancela pendientes/confirmadas futuras. Vacunas y controles presenta próximos, atrasados y atendidos, sin permitir modificar datos clínicos.

Una URL o un identificador API ajeno devuelve 404. Tutor no tiene acceso a Django Admin, aun si su cuenta se marca accidentalmente como staff. Recuperación responde genéricamente para correos desconocidos y usa token temporal de una hora, invalidado al cambiar la contraseña. Contadores PostgreSQL limitan intentos temporalmente sin desactivar cuentas.
