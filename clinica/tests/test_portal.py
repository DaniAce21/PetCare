import re
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.db import connection
from django.test import TestCase, Client, override_settings
from django.utils import timezone
from clinica.models import Tutor, Mascota, LoginWindow
from .test_api import DataMixin, PASSWORD, NEW_PASSWORD

class PortalTests(DataMixin, TestCase):
    def setUp(self):
        self.create_data()
        self.owner = get_user_model().objects.create_user(username='tutor',password=PASSWORD,email='tutor@example.invalid')
        self.owner.groups.add(Group.objects.get(name='Tutor'))
        self.tutor.usuario = self.owner
        self.tutor.save()
        self.other = get_user_model().objects.create_user(username='otro_tutor',password=PASSWORD)
        self.other.groups.add(Group.objects.get(name='Tutor'))
        self.other_profile = Tutor.objects.create(usuario=self.other,nombre='Otro',apellidos='Tutor',rut='11111111-1',telefono='955550102',correo='otro@example.invalid',direccion='Otra dirección')
        self.other_pet = Mascota.objects.create(tutor=self.other_profile,nombre='Ajena',especie='Gato',sexo='Hembra',fecha_nacimiento='2020-01-01',peso=4)
        self.client.force_authenticate(self.owner)
    def test_reserva_post_fecha_pasada(self):
        from clinica.models import Cita
        self.client.force_login(self.owner)
        response = self.client.post('/reservar/', {
            'mascota': self.pet.pk, 'veterinario': self.vet.pk,
            'fecha': str(timezone.localdate()-timedelta(days=1)),
            'hora': '10:00', 'motivo': 'Intento manipulado',
        })
        self.assertContains(response, 'No puedes reservar citas en fechas pasadas.')
        self.assertFalse(Cita.objects.exists())

    def test_postgresql_persistencia(self):
        self.assertEqual(connection.vendor,'postgresql')
        self.pet.refresh_from_db()
        self.assertEqual(self.pet.tutor.usuario_id,self.owner.pk)
    def test_api_solo_propias(self):
        response = self.client.get('/api/mascotas/')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.data['count'],2)
        self.assertEqual(self.client.get(f'/api/mascotas/{self.other_pet.pk}/').status_code,404)
        self.assertEqual(self.client.patch(f'/api/mascotas/{self.other_pet.pk}/',{'nombre':'Ataque'}).status_code,404)
        self.assertEqual(self.client.patch(f'/api/mascotas/{self.pet.pk}/',{'tutor':self.other_profile.pk}).status_code,400)
    def test_api_crear_mascota_no_suplanta(self):
        data={'nombre':'Nueva','especie':'Gato','sexo':'Hembra','fecha_nacimiento':'2020-01-01','peso':4,'tutor':self.other_profile.pk}
        self.assertEqual(self.client.post('/api/mascotas/',data).status_code,400)
        data['tutor']=self.tutor.pk
        self.assertEqual(self.client.post('/api/mascotas/',data).status_code,201)
    def test_tutor_clinica_lectura(self):
        self.client.force_authenticate(self.admin)
        ficha=self.client.post('/api/fichas/',self.ficha()).data
        self.client.force_authenticate(self.owner)
        self.assertEqual(self.client.get(f"/api/fichas/{ficha['id']}/").status_code,200)
        self.assertEqual(self.client.patch(f"/api/fichas/{ficha['id']}/",{'diagnostico':'No'}).status_code,403)
        for path in ['fichas','vacunas','recordatorios','disponibilidades','veterinarios','tutores','usuarios']:
            self.assertEqual(self.client.post(f'/api/{path}/',{}).status_code,403,path)
        self.assertEqual(self.client.get('/api/dashboard/').status_code,403)
    def test_citas_ajenas_y_estado(self):
        data=self.appointment(estado='Pendiente')
        self.assertEqual(self.client.post('/api/citas/',dict(data,mascota=self.other_pet.pk)).status_code,400)
        self.assertEqual(self.client.post('/api/citas/',dict(data,estado='Confirmada')).status_code,400)
        response=self.client.post('/api/citas/',data)
        self.assertEqual(response.status_code,201,response.data)
        pk=response.data['id']
        self.assertEqual(self.client.patch(f'/api/citas/{pk}/',{'motivo':'Cambio'}).status_code,400)
        self.assertEqual(self.client.post(f'/api/citas/{pk}/cancelar/').status_code,200)
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(f'/api/citas/{pk}/').status_code,404)
    def test_portal_rutas_admin_y_idor(self):
        self.client.force_login(self.owner)
        for path in ['/','/mi-cuenta/','/mis-mascotas/','/mis-citas/','/cuidados/','/reservar/',f'/mis-mascotas/{self.pet.pk}/historial/']:
            self.assertEqual(self.client.get(path).status_code,200,path)
        self.assertContains(self.client.get('/'),'Bienvenido a PetCare')
        self.assertEqual(self.client.get(f'/mis-mascotas/{self.other_pet.pk}/editar/').status_code,404)
        self.assertEqual(self.client.get(f'/mis-mascotas/{self.other_pet.pk}/historial/').status_code,404)
        self.assertEqual(self.client.get('/admin/').status_code,403)
        self.owner.is_staff=True;self.owner.save()
        self.assertEqual(self.client.get('/admin/').status_code,403)
    def test_redireccion_y_logout(self):
        client=Client()
        self.assertEqual(client.post('/login/',{'username':'tutor','password':PASSWORD}).status_code,302)
        self.assertContains(client.get('/'),'Bienvenido a PetCare')
        self.assertEqual(client.get('/logout/').status_code,405)
        self.assertEqual(client.post('/logout/').status_code,302)
        self.assertEqual(client.get('/mis-mascotas/').status_code,302)
        client.force_login(self.vetuser)
        self.assertContains(client.get('/'),'Gestión veterinaria')
    def test_no_redireccion_abierta(self):
        response=Client().post('/login/?next=https://evil.invalid',{'username':'tutor','password':PASSWORD})
        self.assertEqual(response['Location'],'/')
    def test_csrf_formularios(self):
        client=Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        for path in ['/mis-citas/','/mi-cuenta/','/mis-mascotas/agregar/','/reservar/','/logout/','/registro/']:
            self.assertEqual(client.post(path,{}).status_code,403,path)
    def test_registro_siempre_tutor(self):
        response=Client().post('/registro/',{'username':'nueva','password1':NEW_PASSWORD,'password2':NEW_PASSWORD,'nombre':'Nueva','apellidos':'Persona','rut':'11111112-K','telefono':'955550103','correo':'nueva@example.invalid','direccion':'Dirección','rol':'Administrador','is_staff':'true','is_superuser':'true'})
        self.assertEqual(response.status_code,302)
        user=get_user_model().objects.get(username='nueva')
        self.assertFalse(user.is_staff or user.is_superuser)
        self.assertEqual(list(user.groups.values_list('name',flat=True)),['Tutor'])
        self.assertEqual(user.tutor.nombre,'Nueva')
    def test_login_limite_temporal(self):
        client=Client()
        for _ in range(10):
            self.assertEqual(client.post('/login/',{'username':'nadie','password':'incorrecta'}).status_code,200)
        self.assertEqual(client.post('/login/',{'username':'tutor','password':PASSWORD}).status_code,429)
        LoginWindow.objects.update(expires=timezone.now()-timedelta(seconds=1))
        self.assertEqual(client.post('/login/',{'username':'tutor','password':PASSWORD}).status_code,302)
    def test_proxy_falso_no_evade_limite(self):
        client=Client()
        for i in range(10):
            client.post('/login/',{'username':'nadie','password':'incorrecta'},HTTP_X_FORWARDED_FOR=f'192.0.2.{i}',HTTP_X_REAL_IP=f'192.0.2.{i}')
        self.assertEqual(client.post('/login/',{'username':'nadie','password':'incorrecta'}).status_code,429)
    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_recuperacion_no_enumera_y_token_unico(self):
        client=Client()
        response=client.post('/recuperar/',{'email':'tutor@example.invalid'})
        self.assertEqual(response.status_code,302)
        self.assertEqual(len(mail.outbox),1)
        unknown=client.post('/recuperar/',{'email':'nadie@example.invalid'})
        self.assertEqual(response['Location'],unknown['Location'])
        self.assertEqual(len(mail.outbox),1)
        token=default_token_generator.make_token(self.owner)
        self.assertTrue(default_token_generator.check_token(self.owner,token))
        url=re.search(r'https?://[^\s]+',mail.outbox[0].body).group(0)
        from urllib.parse import urlsplit
        first=client.get(urlsplit(url).path)
        self.assertEqual(first.status_code,302)
        result=client.post(first['Location'],{'new_password1':NEW_PASSWORD,'new_password2':NEW_PASSWORD})
        self.assertEqual(result.status_code,302)
        self.owner.refresh_from_db()
        self.assertTrue(self.owner.check_password(NEW_PASSWORD))
        self.assertFalse(default_token_generator.check_token(self.owner,token))

    def test_vinculacion_conserva_y_no_sobrescribe(self):
        from django.core.management import call_command, CommandError
        from io import StringIO
        legacy=Tutor.objects.create(nombre='Anterior',apellidos='Persona',rut='11111112-K',telefono='955550103',correo='anterior@example.invalid',direccion='Dirección')
        user=get_user_model().objects.create_user(username='legacy')
        user.groups.add(Group.objects.get(name='Recepcionista'))
        call_command('vincular_tutor','legacy',legacy.pk,stdout=StringIO())
        legacy.refresh_from_db()
        self.assertEqual(legacy.usuario_id,user.pk)
        self.assertTrue(user.groups.filter(name='Tutor').exists())
        self.assertFalse(user.groups.filter(name='Recepcionista').exists())
        with self.assertRaises(CommandError):
            call_command('vincular_tutor','legacy',self.tutor.pk,stdout=StringIO())

    def test_admin_veterinario_permisos_y_autoria(self):
        from django.contrib.auth.models import Permission
        self.vetuser.is_staff=True;self.vetuser.save()
        self.vetuser.user_permissions.add(*Permission.objects.filter(content_type__app_label='clinica',content_type__model='fichaclinica'))
        client=Client();client.force_login(self.vetuser)
        self.assertEqual(client.get('/admin/').status_code,200)
        self.assertEqual(client.get('/admin/clinica/fichaclinica/add/').status_code,200)
        self.assertEqual(client.get('/admin/auth/user/').status_code,403)
