"""Gunicorn detrás de Nginx; no se expone el puerto 8001 al exterior."""
import os
bind = '127.0.0.1:8001'
workers = int(os.getenv('WEB_CONCURRENCY','2'))
threads = 2
worker_class = 'gthread'
timeout = 60
accesslog = '-'
errorlog = '-'
capture_output = True
forwarded_allow_ips = '127.0.0.1'
# No registrar cookies, contraseñas ni cuerpos de solicitudes.
# Omitir la ruta: puede contener un token temporal de recuperación.
access_log_format = '%(h)s %(m)s %(s)s %(L)s'
