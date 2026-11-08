from django.db.models.signals import post_migrate, post_save
from django.dispatch import receiver
from django.contrib.auth.models import Group, Permission
from .models import Vacuna
from .services import actualizar_recordatorios

@receiver(post_save,sender=Vacuna)
def vaccine_saved(sender,instance,raw=False,**kwargs):
    if not raw:
        actualizar_recordatorios(instance.pk)

@receiver(post_migrate)
def crear_roles(sender,**kwargs):
    if sender.name != 'clinica':
        return
    admin,_ = Group.objects.get_or_create(name='Administrador')
    admin.permissions.set(Permission.objects.filter(content_type__app_label__in=['clinica','auth']))
    for name in ['Veterinario','Recepcionista','Tutor']:
        Group.objects.get_or_create(name=name)


from django.contrib.auth.signals import user_login_failed, user_logged_in
import logging

@receiver(user_login_failed)
def registrar_fallo_login(sender, **kwargs):
    logging.getLogger('petcare.security').warning('login_failed')

@receiver(user_logged_in)
def registrar_acceso(sender, **kwargs):
    logging.getLogger('petcare.security').info('login_succeeded')
