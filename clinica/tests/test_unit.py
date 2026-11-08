"""Pruebas sin base de datos: se ejecutan incluso si PostgreSQL está detenido."""
from types import SimpleNamespace
from django.core.exceptions import ValidationError
from django.template.loader import get_template, render_to_string
from django.test import SimpleTestCase, override_settings
from django.urls import reverse, resolve
from rest_framework.test import APIRequestFactory
from clinica.validators import normalizar_rut, validar_telefono, no_futura
from clinica.permissions import PetCarePermission
from datetime import date, timedelta
from django.utils import timezone

class ValidatorsTests(SimpleTestCase):
    def test_rut_normaliza(self):
        self.assertEqual(normalizar_rut('12.345.678-5'),'12345678-5')
    def test_rut_k(self):
        # 11.111.112-K es un identificador de prueba con verificador K.
        self.assertEqual(normalizar_rut('11.111.112-k'),'11111112-K')
    def test_rut_invalido(self):
        for value in ['12345678-9','0-0','<script>','111','null']:
            with self.subTest(value=value),self.assertRaises(ValidationError):
                normalizar_rut(value)
    def test_telefono(self):
        validar_telefono('+56 9 5555 0101')
        for value in ['abc','123','<script>12345678']:
            with self.assertRaises(ValidationError):validar_telefono(value)
    def test_fecha_no_futura(self):
        no_futura(date(2020,1,1))
        with self.assertRaises(ValidationError):no_futura(timezone.localdate()+timedelta(days=1))

class PublicPagesTests(SimpleTestCase):
    def test_templates_compilan(self):
        for name in ['registration/login.html','clinica/app.html','clinica/imprimir.html','portal/base.html','portal/inicio.html','portal/form.html','portal/mascotas.html','portal/citas.html','portal/cuidados.html','portal/historial.html','portal/reservar.html','registration/reset_form.html','registration/reset_done.html','registration/reset_confirm.html','registration/reset_complete.html','admin/index.html','admin/base_site.html','400.html']:
            self.assertIsNotNone(get_template(name))
    def test_login_espanol_csrf(self):
        response=self.client.get('/login/')
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'csrfmiddlewaretoken')
        self.assertContains(response,'Ingresar a PetCare')
        self.assertIn('csrftoken',response.cookies)
    def test_inicio_exige_login(self):
        self.assertRedirects(self.client.get('/'),'/login/?next=/',fetch_redirect_response=False)
    def test_anonimo_no_consulta_api(self):
        for path in ['tutores','mascotas','veterinarios','disponibilidades','citas','fichas','vacunas','recordatorios','usuarios','dashboard','perfil']:
            self.assertIn(self.client.get(f'/api/{path}/').status_code,[401,403])
    def test_logout_requiere_post(self):
        self.assertEqual(self.client.get('/logout/').status_code,405)
    def test_csrf_login_rechaza_solicitud_sin_token(self):
        from django.test import Client
        response=Client(enforce_csrf_checks=True).post('/login/',{'username':'test','password':'test'})
        self.assertEqual(response.status_code,403)
    def test_rutas_router(self):
        for name in ['tutores','mascotas','veterinarios','disponibilidades','citas','fichas','vacunas','recordatorios']:
            self.assertEqual(resolve(reverse(f'{name}-list')).url_name,f'{name}-list')
    @override_settings(HTTPS_ENABLED=True,SESSION_COOKIE_SECURE=True,CSRF_COOKIE_SECURE=True,SECURE_SSL_REDIRECT=True)
    def test_redireccion_https(self):
        response=self.client.get('/login/')
        self.assertEqual(response.status_code,301)
        self.assertTrue(response['Location'].startswith('https://'))

class BusinessRulesWithoutDatabaseTests(SimpleTestCase):
    def test_intervalos_invalidos_sin_acceder_a_bd(self):
        from clinica.models import Cita
        from datetime import time
        for start,end in [(time(10),time(9)),(time(9),time(14)),(time(10),time(10)),(time(10,0,1),time(11))]:
            with self.subTest(start=start,end=end),self.assertRaises(ValidationError):
                Cita(mascota_id=1,veterinario_id=1,fecha=date(2030,1,7),hora_inicio=start,hora_termino=end).clean()
    def test_cita_cancelada_no_bloquea_disponibilidad(self):
        from clinica.models import Cita
        from datetime import time
        Cita(mascota_id=1,veterinario_id=1,fecha=date(2030,1,7),hora_inicio=time(10),hora_termino=time(11),estado='Cancelada').clean()
    def test_vacuna_orden_fechas(self):
        from clinica.models import Vacuna
        with self.assertRaises(ValidationError):
            Vacuna(fecha_aplicacion=date(2026,1,2),fecha_proxima_dosis=date(2026,1,1)).clean()
    def test_exclusiones_compilan_a_rangos_postgresql(self):
        from clinica.models import Cita
        from django.db import connection
        for constraint in Cita._meta.constraints[-2:]:
            expr=constraint.expressions[1][0]
            query=Cita.objects.annotate(rango=expr).values('rango').query
            sql,params=query.get_compiler(connection=connection).as_sql()
            self.assertIn('tsrange(',sql)
            self.assertIn('[)',params)
    def test_migracion_habilita_btree_gist(self):
        import importlib
        from django.contrib.postgres.operations import BtreeGistExtension
        migration=importlib.import_module('clinica.migrations.0001_initial').Migration
        self.assertIsInstance(migration.operations[0],BtreeGistExtension)

class PermissionRulesTests(SimpleTestCase):
    def user(self,group,vet_id=1):
        class Groups:
            def filter(self,**kwargs):return SimpleNamespace(exists=lambda:kwargs['name']==group)
        return SimpleNamespace(is_authenticated=True,is_active=True,is_superuser=group=='Administrador',groups=Groups(),veterinario=SimpleNamespace(pk=vet_id,activo=True))
    def allowed(self,group,resource,method):
        request=SimpleNamespace(user=self.user(group),method=method)
        return PetCarePermission().has_permission(request,SimpleNamespace(resource=resource))
    def test_recepcion_datos_clinicos_bloqueados(self):
        for method in ['GET','POST','PATCH','DELETE']:
            self.assertFalse(self.allowed('Recepcionista','fichas',method))
        self.assertFalse(self.allowed('Recepcionista','vacunas','POST'))
        self.assertFalse(self.allowed('Recepcionista','usuarios','GET'))
        self.assertFalse(self.allowed('Recepcionista','disponibilidades','PATCH'))
    def test_recepcion_agenda_y_admin(self):
        self.assertTrue(self.allowed('Recepcionista','citas','POST'))
        self.assertTrue(self.allowed('Recepcionista','citas','PATCH'))
        self.assertTrue(self.allowed('Recepcionista','tutores','DELETE'))
        self.assertFalse(self.allowed('Recepcionista','citas','DELETE'))
    def test_administrador_todos_los_modulos(self):
        for resource in ['tutores','mascotas','veterinarios','disponibilidades','citas','fichas','vacunas','recordatorios','usuarios']:
            for method in ['GET','POST','PUT','PATCH','DELETE']:
                self.assertTrue(self.allowed('Administrador',resource,method))
    def test_veterinario_no_suplanta_profesional(self):
        permission=PetCarePermission()
        request=SimpleNamespace(user=self.user('Veterinario'),method='PATCH')
        self.assertTrue(permission.has_object_permission(request,SimpleNamespace(resource='fichas'),SimpleNamespace(veterinario_id=1)))
        self.assertFalse(permission.has_object_permission(request,SimpleNamespace(resource='fichas'),SimpleNamespace(veterinario_id=2)))
        self.assertFalse(self.allowed('Veterinario','fichas','DELETE'))
    def test_usuario_sin_grupo_no_accede(self):
        self.assertFalse(self.allowed('Sin rol','mascotas','GET'))

class TutorPermissionTests(SimpleTestCase):
    allowed = PermissionRulesTests.allowed
    def user(self,group,vet_id=1):
        user=PermissionRulesTests.user(self,group,vet_id)
        user.tutor=SimpleNamespace(pk=7)
        user.pk=8
        return user
    def test_tutor_mutaciones_limitadas(self):
        for resource in ['fichas','vacunas','recordatorios','tutores','veterinarios','usuarios','disponibilidades']:
            self.assertFalse(self.allowed('Tutor',resource,'POST'))
        self.assertTrue(self.allowed('Tutor','mascotas','POST'))
        self.assertTrue(self.allowed('Tutor','citas','POST'))
    def test_tutor_objeto_ajeno(self):
        perm=PetCarePermission()
        req=SimpleNamespace(user=self.user('Tutor'),method='GET')
        view=SimpleNamespace(resource='mascotas')
        self.assertTrue(perm.has_object_permission(req,view,SimpleNamespace(tutor=SimpleNamespace(usuario_id=8))))
        self.assertFalse(perm.has_object_permission(req,view,SimpleNamespace(tutor=SimpleNamespace(usuario_id=9))))

class IncrementalMigrationTests(SimpleTestCase):
    def test_migraciones_no_destructivas(self):
        import importlib
        from django.db.migrations.operations.fields import AddField
        from django.db.migrations.operations.models import CreateModel
        second=importlib.import_module('clinica.migrations.0002_tutor_usuario').Migration
        third=importlib.import_module('clinica.migrations.0003_loginwindow').Migration
        self.assertEqual(len(second.operations),1)
        self.assertIsInstance(second.operations[0],AddField)
        self.assertTrue(second.operations[0].field.null)
        self.assertIsInstance(third.operations[0],CreateModel)
