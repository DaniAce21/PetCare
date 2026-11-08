from datetime import timedelta
from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from .models import Vacuna, Recordatorio

@transaction.atomic
def actualizar_recordatorios(vacuna_id=None):
    vacunas = Vacuna.objects.select_for_update().select_related('mascota').order_by('pk')
    if vacuna_id:
        vacunas = vacunas.filter(pk=vacuna_id)
    count = 0
    for vacuna in vacunas:
        message = f'Próxima dosis de {vacuna.nombre} para {vacuna.mascota.nombre}: {vacuna.fecha_proxima_dosis:%d/%m/%Y}. Contacta a la clínica para agendar.'
        existing = Recordatorio.objects.filter(vacuna=vacuna).first()
        if vacuna.seguimiento_cerrado:
            if existing and existing.estado != 'Atendido':
                existing.estado = 'Atendido'
                existing.save()
            continue
        if not existing:
            Recordatorio.objects.create(vacuna=vacuna,mascota=vacuna.mascota,tipo='Vacuna',
                 fecha_programada=vacuna.fecha_proxima_dosis,mensaje=message)
            count += 1
        else:
            if existing.fecha_programada != vacuna.fecha_proxima_dosis:
                existing.estado = 'Pendiente'
                existing.correo_enviado = None
            existing.fecha_programada = vacuna.fecha_proxima_dosis
            existing.mascota = vacuna.mascota
            existing.mensaje = message
            existing.save()
    return count

def enviar_recordatorios():
    """Un proceso por fila con SKIP LOCKED. SMTP tiene semántica de al menos una vez."""
    if not settings.SMTP_CONFIGURED:
        return 0
    candidates = list(Recordatorio.objects.filter(estado='Pendiente',correo_enviado__isnull=True,
                      fecha_programada__lte=timezone.localdate()+timedelta(days=7)).values_list('pk',flat=True))
    sent = 0
    for pk in candidates:
        with transaction.atomic():
            reminder = Recordatorio.objects.select_for_update(skip_locked=True).filter(pk=pk,estado='Pendiente',correo_enviado__isnull=True).first()
            if not reminder:
                continue
            try:
                send_mail(f'PetCare · Recordatorio de {reminder.tipo.lower()}',reminder.mensaje,
                          settings.DEFAULT_FROM_EMAIL,[reminder.mascota.tutor.correo],fail_silently=False)
                reminder.correo_enviado = timezone.now()
                reminder.error_envio = ''
                sent += 1
            except Exception:
                # El proveedor SMTP puede incluir credenciales en su excepción: nunca persistir su texto.
                reminder.error_envio = 'No se pudo enviar. Revisa la configuración SMTP y la conectividad.'
            reminder.save()
    return sent
