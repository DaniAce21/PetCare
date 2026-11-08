# Seguridad operativa del rediseño

## Aplicación

Mantener `DEBUG=False`, SECRET_KEY aleatoria privada, ALLOWED_HOSTS concreto y CSRF_TRUSTED_ORIGINS explícito. `.env` con modo 600. El login mantiene mensajes genéricos y registra únicamente el evento, sin usuario, contraseña ni dirección. Los contadores de intentos se comparten en PostgreSQL, con hash salado por SECRET_KEY, filas bloqueadas con `select_for_update` y ventanas fijas de cinco minutos. Máximo diez solicitudes por IP y por nombre de cuenta normalizado; también se cuentan aciertos para impedir carreras y abuso de sesiones. Se protege `/admin/login/`, registro y recuperación; estas dos últimas por IP. El bloqueo expira, no desactiva cuentas. Una IP compartida puede quedar limitada; la clave por cuenta reduce ataques distribuidos, pero puede causar bloqueo temporal deliberado. Programar diariamente:

```bash
/srv/petcare/.venv/bin/python /srv/petcare/manage.py limpiar_intentos
```

Sin conexión a PostgreSQL no se continúa la autenticación. No se usa un contador independiente en cada worker. Las pruebas de concurrencia de reservas ya existentes se conservan. La suite incluye límites, vencimiento y rechazo de encabezados IP falsificados; debe ejecutarse con PostgreSQL antes de publicar.

La recuperación usa vistas y tokens nativos de Django con `PASSWORD_RESET_TIMEOUT=3600`, respuesta igual para correo conocido/desconocido y validadores de contraseña. Configurar SMTP real y evitar almacenar enlaces de recuperación en logs. La protección de contenido de logs no protege un terminal de desarrollo cuyo backend de correo es consola; no usar ese backend con datos reales. Los tiempos de envío SMTP pueden variar: para escenarios de mayor exposición conviene una cola de correo que desacople el tiempo de respuesta.

## Proxy y TLS

Nginx reemplaza X-Real-IP y X-Forwarded-For con la IP del socket. Django ignora esos encabezados salvo cuando REMOTE_ADDR está en `TRUSTED_PROXY_IPS`. En EC2 con Nginx local, configurar `TRUSTED_PROXY_IPS=127.0.0.1`; nunca agregar redes públicas. Gunicorn escucha solo 127.0.0.1:8001 y confía en forwarded proto únicamente desde loopback. No exponer ese puerto ni 8000. No instalar detrás de un segundo balanceador sin redefinir explícitamente los proxies de confianza.

`deploy/nginx.conf` limita métodos, cuerpos a 1 MiB, tiempos, intentos de autenticación y tráfico de aplicación. Incluye un servidor predeterminado que rechaza hosts desconocidos; quitar el sitio default solo en una instancia dedicada donde no aloje trabajo ajeno. Sus logs omiten query strings, referers y tokens de recuperación. Gunicorn omite rutas para no registrar tokens. El rate limit Nginx es por IP de conexión, no por User-Agent ni encabezados enviados por clientes.

Primero comprobar el certificado, redirección y acceso de la aplicación por HTTPS real. Luego activar `HTTPS_ENABLED=True` para cookies seguras y redirect, manteniendo `HSTS_SECONDS=0`. Tras verificar nuevamente, probar HSTS con 300 segundos y elevar a 31536000 solo cuando sea estable. No se activa preload ni includeSubDomains automáticamente. Revisar:

```bash
sudo nginx -t
sudo systemctl restart petcare
sudo -u petcare /srv/petcare/.venv/bin/python /srv/petcare/manage.py check --deploy
curl -I https://DOMINIO_REAL/login/
```

## Sistema, red y AWS

Security Group: 22 únicamente desde tu IP `/32`; 80 para HTTP y 443 para TLS. Sin entradas para 5432/8000/8001. Revisar IPv6 además de IPv4. PostgreSQL debe escuchar localhost y usar SCRAM. Usar un rol de runtime sin SUPERUSER, CREATEDB ni CREATEROLE; separar del propietario usado para migrar. Ver `postgresql.md`.

Antes de habilitar UFW, mantener una segunda sesión SSH y autorizar tu IP real:

```bash
sudo apt-get update
sudo apt-get upgrade
sudo apt-get install ufw fail2ban unattended-upgrades
sudo ufw allow from TU_IP_REAL to any port 22 proto tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status verbose
```

No ejecutar literalmente TU_IP_REAL. Instalar `deploy/sshd-petcare.conf` en `/etc/ssh/sshd_config.d/` solo después de verificar que el acceso con clave funciona y que el usuario tiene sudo; comprobar `sudo sshd -t` y recargar `sudo systemctl reload ssh`. Instalar `deploy/fail2ban-petcare.conf` como `/etc/fail2ban/jail.d/petcare.local`, verificar `sudo fail2ban-client -t`, reiniciar y revisar `sudo fail2ban-client status sshd`. El jail protege SSH; los intentos web los limitan Django y Nginx.

Gunicorn usa cuenta petcare sin shell, reinicia al fallar, tiene dos workers por defecto y logs en journald. Revisar uso de memoria y ajustar WEB_CONCURRENCY. Revisar semanalmente:

```bash
sudo systemctl --failed
sudo systemctl status petcare nginx postgresql --no-pager
sudo journalctl -u petcare --since today
sudo journalctl --disk-usage
sudo fail2ban-client status sshd
free -h
df -h
ss -lnt
```

Nginx utiliza logrotate de Debian: comprobar que `/etc/logrotate.d/nginx` incluye `/var/log/nginx/*.log`; `sudo logrotate -d /etc/logrotate.conf` verifica sin rotar. Limitar journald mediante `SystemMaxUse=200M` en un drop-in de `/etc/systemd/journald.conf.d/` y reiniciar journald. Respaldar PostgreSQL a diario fuera del repositorio, con permisos 600 y copias cifradas externas; probar recuperación en una base separada. No eliminar ni restaurar encima de la BD clínica para probar.

Estos controles reducen ataques comunes. Una instancia EC2 pequeña puede agotarse ante ataques volumétricos; considerar protección de borde, balanceador y servicios administrados según el laboratorio y presupuesto. No se promete inmunidad a DDoS y no se bloquean nacionalidades o países.

Referencias: [checklist oficial de Django](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/), [bloqueos ORM](https://docs.djangoproject.com/en/5.2/ref/models/querysets/#select-for-update), [autenticación y recuperación](https://docs.djangoproject.com/en/5.2/topics/auth/default/).
