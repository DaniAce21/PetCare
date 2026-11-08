# Modelo entidad-relación

```mermaid
erDiagram
    USUARIO ||--o| VETERINARIO : tiene_perfil
    USUARIO }o--o{ GRUPO : pertenece
    USUARIO ||--o{ ACTIVIDAD : realiza
    TUTOR ||--o{ MASCOTA : cuida
    VETERINARIO ||--o{ DISPONIBILIDAD : configura
    VETERINARIO ||--o{ CITA : atiende
    MASCOTA ||--o{ CITA : reserva
    MASCOTA ||--o{ FICHA_CLINICA : posee
    VETERINARIO ||--o{ FICHA_CLINICA : registra
    CITA |o--o| FICHA_CLINICA : puede_originar
    MASCOTA ||--o{ VACUNA : recibe
    VETERINARIO ||--o{ VACUNA : aplica
    MASCOTA ||--o{ RECORDATORIO : recibe
    VACUNA |o--o| RECORDATORIO : genera
    TUTOR {
        bigint id PK
        string nombre
        string apellidos
        string rut UK
        string telefono
        string correo
        string direccion
        datetime fecha_registro
    }
    MASCOTA {
        bigint id PK
        bigint tutor_id FK
        string nombre
        string especie
        string raza
        string sexo
        date fecha_nacimiento
        decimal peso
        text observaciones
    }
    VETERINARIO {
        bigint id PK
        bigint usuario_id FK,UK
        string nombre
        string especialidad
        boolean activo
    }
    DISPONIBILIDAD {
        bigint id PK
        bigint veterinario_id FK
        integer dia_semana
        time hora_inicio
        time hora_termino
    }
    CITA {
        bigint id PK
        bigint mascota_id FK
        bigint veterinario_id FK
        date fecha
        time hora_inicio
        time hora_termino
        string motivo
        string estado
    }
    FICHA_CLINICA {
        bigint id PK
        bigint mascota_id FK
        bigint veterinario_id FK
        bigint cita_id FK,UK
        date fecha_atencion
        string motivo
        text sintomas
        text diagnostico
        text tratamiento
        text receta_medica
        text examenes_solicitados
        text resultados
        text observaciones
    }
    VACUNA {
        bigint id PK
        bigint mascota_id FK
        bigint veterinario_id FK
        string nombre
        date fecha_aplicacion
        date fecha_proxima_dosis
        text observaciones
        boolean seguimiento_cerrado
    }
    RECORDATORIO {
        bigint id PK
        bigint mascota_id FK
        bigint vacuna_id FK,UK
        string tipo
        date fecha_programada
        text mensaje
        string estado
        datetime fecha_creacion
        datetime correo_enviado
    }
```

Usuarios, grupos, permisos y sesiones son tablas oficiales de Django; no se duplica el almacenamiento de contraseñas. FK crean índices ordinarios. Citas añade índices `(veterinario,fecha)` y `(mascota,fecha)`, índice por fecha y exclusiones GiST. Vacunas/recordatorios indexan próximas fechas. RUT es único; fecha de vacuna/nombre/mascota y recordatorio manual tienen restricciones de unicidad.

`Vacuna → Recordatorio` usa CASCADE para el aviso generado al eliminar una vacuna con autorización. Disponibilidades pertenecen al profesional y usan CASCADE. Datos clínicos hacia mascota/profesional/cita usan PROTECT. Actividad mantiene la acción si el usuario se elimina (`SET_NULL`). No se recomienda borrar usuarios: la interfaz administrativa permite desactivarlos.

## Extensión del portal (2026-11-05)

```mermaid
erDiagram
    AUTH_USER ||--o| TUTOR : "cuenta opcional y única"
    TUTOR ||--o{ MASCOTA : posee
    AUTH_USER ||--o| VETERINARIO : perfil
    VETERINARIO ||--o{ DISPONIBILIDAD : ofrece
    MASCOTA ||--o{ CITA : reserva
    VETERINARIO ||--o{ CITA : atiende
    CITA o|--o| FICHA_CLINICA : documenta
    MASCOTA ||--o{ FICHA_CLINICA : historial
    MASCOTA ||--o{ VACUNA : recibe
    VACUNA o|--o| RECORDATORIO : genera
    MASCOTA ||--o{ RECORDATORIO : controles
```

`Tutor.usuario` permite NULL para conservar tutores anteriores; una cuenta no puede vincularse a dos tutores. `LoginWindow` es una tabla operativa independiente con key hash única, contador y vencimiento; no almacena credenciales.
