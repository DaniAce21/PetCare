import os
import secrets
from datetime import timedelta, time
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand,CommandError
from django.db import transaction
from django.utils import timezone
from clinica.models import Tutor,Mascota,Veterinario,Disponibilidad,Cita,FichaClinica,Vacuna,Recordatorio

class Command(BaseCommand):
    help = 'Carga datos ficticios una sola vez; genera contraseñas seguras o lee PETCARE_DEMO_PASSWORD.'
    @transaction.atomic
    def handle(self,*args,**options):
        if Tutor.objects.exists() or get_user_model().objects.filter(username__in=['demo_admin','demo_vet','demo_recepcion']).exists():
            raise CommandError('Ya hay datos o usuarios demo. No se sobrescribe información existente.')
        passwords = []
        for username,group in [('demo_admin','Administrador'),('demo_vet','Veterinario'),('demo_recepcion','Recepcionista')]:
            password = os.getenv('PETCARE_DEMO_PASSWORD') or secrets.token_urlsafe(16)
            from django.contrib.auth.password_validation import validate_password
            validate_password(password)
            user = get_user_model().objects.create_user(username=username,password=password,is_staff=group=='Administrador')
            user.groups.add(Group.objects.get(name=group))
            passwords.append((username,password))
        vet = Veterinario.objects.create(usuario=get_user_model().objects.get(username='demo_vet'),nombre='Dra. Antonia Ejemplo',especialidad='Medicina general')
        for day in range(5):
            Disponibilidad.objects.create(veterinario=vet,dia_semana=day,hora_inicio=time(9),hora_termino=time(18))
        today = timezone.localdate()
        tutors = []
        for name,last,rut,email in [('Camila','Demostración','11111111-1','camila@example.invalid'),('Martín','Ficticio','22222222-2','martin@example.invalid'),('Valentina','Ejemplo','33333333-3','vale@example.invalid')]:
            tutors.append(Tutor.objects.create(nombre=name,apellidos=last,rut=rut,telefono='+56 9 5555 0101',correo=email,direccion='Dirección ficticia, Santiago'))
        pets = []
        for tutor,name,species,breed,weight in [(tutors[0],'Luna','Perro','Mestizo','18.5'),(tutors[1],'Simón','Gato','Europeo','4.2'),(tutors[2],'Milo','Conejo','Mestizo','2.1')]:
            pets.append(Mascota.objects.create(tutor=tutor,nombre=name,especie=species,raza=breed,sexo='Sin especificar',fecha_nacimiento=today-timedelta(days=730),peso=weight,observaciones='Paciente ficticio para evaluación académica.'))
        day = today + timedelta(days=1)
        while day.weekday()>4:
            day += timedelta(days=1)
        for i,pet in enumerate(pets):
            Cita.objects.create(mascota=pet,veterinario=vet,fecha=day,hora_inicio=time(10+i),hora_termino=time(10+i,30),motivo='Control de demostración',estado='Confirmada')
        FichaClinica.objects.create(mascota=pets[0],veterinario=vet,fecha_atencion=today-timedelta(days=10),motivo='Consulta ficticia',sintomas='Texto ficticio para probar el formulario',diagnostico='Ejemplo académico sin validez clínica',tratamiento='Campo de demostración',observaciones='No corresponde a una atención real.')
        for pet,offset in [(pets[0],5),(pets[1],-3)]:
            Vacuna.objects.create(mascota=pet,veterinario=vet,nombre='Vacuna de demostración',fecha_aplicacion=today-timedelta(days=360),fecha_proxima_dosis=today+timedelta(days=offset),observaciones='Esquema ficticio; no constituye indicación médica.')
        Recordatorio.objects.create(mascota=pets[2],tipo='Control',fecha_programada=today+timedelta(days=2),mensaje='Agendar control de demostración.')
        self.stdout.write(self.style.SUCCESS('Datos ficticios cargados. Guarda estas claves; solo se muestran en esta ejecución.'))
        for username,password in passwords:
            self.stdout.write(f'{username}: {password}')
