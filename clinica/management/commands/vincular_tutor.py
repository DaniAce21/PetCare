from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from clinica.models import Tutor

class Command(BaseCommand):
    help = 'Vincula explícitamente un tutor existente con una cuenta normal, después de verificar su identidad.'
    def add_arguments(self, parser):
        parser.add_argument('username')
        parser.add_argument('tutor_id',type=int)
    @transaction.atomic
    def handle(self,*args,**options):
        try:
            user=get_user_model().objects.select_for_update().get(username=options['username'])
            tutor=Tutor.objects.select_for_update().get(pk=options['tutor_id'])
        except (get_user_model().DoesNotExist,Tutor.DoesNotExist):
            raise CommandError('No existe esa cuenta o ese tutor.')
        if user.is_staff or user.is_superuser or hasattr(user,'veterinario') or user.groups.filter(name__in=['Administrador','Veterinario']).exists():
            raise CommandError('Usa una cuenta normal sin privilegios clínicos ni técnicos.')
        if (tutor.usuario_id and tutor.usuario_id != user.pk) or Tutor.objects.filter(usuario=user).exclude(pk=tutor.pk).exists():
            raise CommandError('La cuenta o el tutor ya tiene otra vinculación; no se sobrescribe.')
        tutor.usuario=user;tutor.save()
        user.groups.remove(*Group.objects.filter(name='Recepcionista'))
        user.groups.add(Group.objects.get_or_create(name='Tutor')[0])
        user.first_name,user.last_name,user.email=tutor.nombre,tutor.apellidos,tutor.correo
        user.save(update_fields=['first_name','last_name','email'])
        self.stdout.write(self.style.SUCCESS('Vinculación realizada. Se conservaron las mascotas y el historial.'))
