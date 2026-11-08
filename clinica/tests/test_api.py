from datetime import time, timedelta
from io import StringIO
import secrets
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command, CommandError
from django.core.exceptions import ValidationError
from django.db import IntegrityError,transaction
from django.test import TestCase,override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from clinica.models import Tutor,Mascota,Veterinario,Disponibilidad,Cita,FichaClinica,Vacuna,Recordatorio,Actividad
from clinica.services import actualizar_recordatorios,enviar_recordatorios

PASSWORD=secrets.token_urlsafe(24)
NEW_PASSWORD=secrets.token_urlsafe(24)

class DataMixin:
    def create_data(self):
        User=get_user_model()
        self.admin=User.objects.create_superuser(username='admin',password=PASSWORD,email='admin@example.invalid')
        self.vetuser=User.objects.create_user(username='veterinario',password=PASSWORD)
        self.vetuser.groups.add(Group.objects.get(name='Veterinario'))
        self.reception=User.objects.create_user(username='recepcion',password=PASSWORD)
        self.reception.groups.add(Group.objects.get(name='Recepcionista'))
        self.vet=Veterinario.objects.create(usuario=self.vetuser,nombre='Veterinaria de prueba',especialidad='General')
        self.tutor=Tutor.objects.create(nombre='Tutor',apellidos='Ficticio',rut='12345678-5',telefono='+56 9 5555 0101',correo='tutor@example.invalid',direccion='Dirección de prueba')
        self.pet=Mascota.objects.create(tutor=self.tutor,nombre='Luna',especie='Perro',raza='Mestizo',sexo='Hembra',fecha_nacimiento='2020-01-01',peso='12.50')
        self.pet2=Mascota.objects.create(tutor=self.tutor,nombre='Milo',especie='Gato',sexo='Macho',fecha_nacimiento='2021-01-01',peso='4.00')
        self.day=timezone.localdate()+timedelta(days=14)
        self.slot=Disponibilidad.objects.create(veterinario=self.vet,dia_semana=self.day.weekday(),hora_inicio=time(9),hora_termino=time(18))
        self.client=APIClient()
        self.client.force_authenticate(self.admin)
    def appointment(self,**kwargs):
        return {'mascota':self.pet.pk,'veterinario':self.vet.pk,'fecha':str(self.day),'hora_inicio':'10:00','hora_termino':'10:30','motivo':'Control ficticio','estado':'Confirmada',**kwargs}
    def ficha(self,**kwargs):
        return {'mascota':self.pet.pk,'veterinario':self.vet.pk,'fecha_atencion':str(timezone.localdate()),'motivo':'Control ficticio','sintomas':'Ejemplo académico','diagnostico':'Ejemplo sin validez clínica','tratamiento':'Campo de prueba',**kwargs}
    def vacuna(self,**kwargs):
        return {'mascota':self.pet.pk,'veterinario':self.vet.pk,'nombre':'Vacuna ficticia','fecha_aplicacion':str(timezone.localdate()-timedelta(days=300)),'fecha_proxima_dosis':str(timezone.localdate()+timedelta(days=3)),**kwargs}

class CRUDTests(DataMixin,TestCase):
    def setUp(self):self.create_data()
    def test_crud_tutores(self):
        payload={'nombre':'Otra','apellidos':'Persona ficticia','rut':'11.111.111-1','telefono':'955550102','correo':'otro@example.invalid','direccion':'Dirección ficticia'}
        response=self.client.post('/api/tutores/',payload)
        self.assertEqual(response.status_code,201,response.data)
        pk=response.data['id']
        self.assertEqual(response.data['rut'],'11111111-1')
        response=self.client.patch(f'/api/tutores/{pk}/',{'nombre':'Editado'})
        self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(self.client.get(f'/api/tutores/{pk}/').data['nombre'],'Editado')
        self.assertEqual(self.client.delete(f'/api/tutores/{pk}/').status_code,204)
        self.assertEqual(self.client.get(f'/api/tutores/{pk}/').status_code,404)
    def test_tutor_rut_duplicado(self):
        data={'nombre':'Repetido','apellidos':'Ficticio','rut':'12.345.678-5','telefono':'955550102','correo':'otro@example.invalid','direccion':'Dirección'}
        self.assertEqual(self.client.post('/api/tutores/',data).status_code,400)
    def test_campos_obligatorios(self):
        for endpoint in ['tutores','mascotas','citas','fichas','vacunas','disponibilidades']:
            self.assertEqual(self.client.post(f'/api/{endpoint}/',{}).status_code,400)
    def test_crud_mascotas_y_relacion(self):
        data={'tutor':self.tutor.pk,'nombre':'Sol','especie':'Ave','sexo':'Sin especificar','fecha_nacimiento':'2022-01-01','peso':'0.5'}
        response=self.client.post('/api/mascotas/',data)
        self.assertEqual(response.status_code,201,response.data)
        pk=response.data['id']
        self.assertEqual(self.tutor.mascotas.count(),3)
        response=self.client.put(f'/api/mascotas/{pk}/',{**data,'nombre':'Sol actualizado'})
        self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(self.client.delete(f'/api/mascotas/{pk}/').status_code,204)
    def test_peso_y_fecha_mascota(self):
        self.assertEqual(self.client.patch(f'/api/mascotas/{self.pet.pk}/',{'peso':'-1'}).status_code,400)
        self.assertEqual(self.client.patch(f'/api/mascotas/{self.pet.pk}/',{'fecha_nacimiento':str(timezone.localdate()+timedelta(days=1))}).status_code,400)
    def test_eliminacion_protegida(self):
        self.assertEqual(self.client.delete(f'/api/tutores/{self.tutor.pk}/').status_code,409)
        self.assertTrue(Tutor.objects.filter(pk=self.tutor.pk).exists())
    def test_busqueda_filtros_paginacion(self):
        response=self.client.get('/api/mascotas/?search=Luna&especie=Perro')
        self.assertEqual(response.data['count'],1)
        self.assertEqual(response.data['results'][0]['nombre'],'Luna')
        self.assertIn('next',response.data)
        self.assertEqual(self.client.get('/api/citas/?desde=fecha-invalida').status_code,400)
        self.assertEqual(self.client.get('/api/citas/?veterinario=no').status_code,400)
    def test_auditoria(self):
        self.client.patch(f'/api/tutores/{self.tutor.pk}/',{'nombre':'Modificado'})
        self.assertTrue(Actividad.objects.filter(usuario=self.admin,entidad='tutores',accion='Registro actualizado').exists())
    def test_dashboard(self):
        response=self.client.get('/api/dashboard/')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.data['mascotas'],2)
        self.assertIn('actividad',response.data)

class AgendaTests(DataMixin,TestCase):
    def setUp(self):self.create_data()
    def test_crear_modificar_cancelar_eliminar(self):
        response=self.client.post('/api/citas/',self.appointment())
        self.assertEqual(response.status_code,201,response.data)
        pk=response.data['id']
        response=self.client.patch(f'/api/citas/{pk}/',{'hora_inicio':'11:00','hora_termino':'11:30'})
        self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(self.client.post(f'/api/citas/{pk}/cancelar/').data['estado'],'Cancelada')
        self.assertEqual(self.client.delete(f'/api/citas/{pk}/').status_code,204)
    def test_superposicion_veterinario(self):
        self.assertEqual(self.client.post('/api/citas/',self.appointment()).status_code,201)
        response=self.client.post('/api/citas/',self.appointment(mascota=self.pet2.pk,hora_inicio='10:15',hora_termino='10:45'))
        self.assertEqual(response.status_code,400,response.data)
    def test_superposicion_mascota_otro_veterinario(self):
        other=get_user_model().objects.create_user(username='otro')
        vet=Veterinario.objects.create(usuario=other,nombre='Otro veterinario')
        Disponibilidad.objects.create(veterinario=vet,dia_semana=self.day.weekday(),hora_inicio=time(9),hora_termino=time(18))
        self.client.post('/api/citas/',self.appointment())
        self.assertEqual(self.client.post('/api/citas/',self.appointment(veterinario=vet.pk)).status_code,400)
    def test_intervalos_adyacentes(self):
        self.client.post('/api/citas/',self.appointment())
        response=self.client.post('/api/citas/',self.appointment(hora_inicio='10:30',hora_termino='11:00'))
        self.assertEqual(response.status_code,201,response.data)
    def test_cancelada_libera_horario(self):
        self.client.post('/api/citas/',self.appointment(estado='Cancelada'))
        self.assertEqual(self.client.post('/api/citas/',self.appointment()).status_code,201)
    def test_disponibilidad_y_duracion(self):
        for changes in [{'hora_inicio':'08:30','hora_termino':'09:30'},{'hora_inicio':'18:00','hora_termino':'18:30'},{'fecha':str(self.day+timedelta(days=1))},{'hora_inicio':'10:00','hora_termino':'09:00'},{'hora_inicio':'09:00','hora_termino':'14:00'},{'hora_inicio':'10:00:01'}]:
            with self.subTest(changes=changes):
                self.assertEqual(self.client.post('/api/citas/',self.appointment(**changes)).status_code,400)
    def test_validacion_al_modificar(self):
        a=self.client.post('/api/citas/',self.appointment()).data
        b=self.client.post('/api/citas/',self.appointment(hora_inicio='11:00',hora_termino='11:30')).data
        self.assertEqual(self.client.patch(f"/api/citas/{b['id']}/",{'hora_inicio':'10:15','hora_termino':'10:45'}).status_code,400)
        self.assertEqual(self.client.patch(f"/api/citas/{a['id']}/",{'hora_inicio':'07:00'}).status_code,400)
    def test_vet_inactivo(self):
        self.vet.activo=False;self.vet.save()
        self.assertEqual(self.client.post('/api/citas/',self.appointment()).status_code,400)
    def test_horario_no_deja_citas_fuera(self):
        self.client.post('/api/citas/',self.appointment())
        response=self.client.patch(f'/api/disponibilidades/{self.slot.pk}/',{'hora_termino':'10:00'})
        self.assertEqual(response.status_code,400,response.data)
        self.slot.refresh_from_db();self.assertEqual(self.slot.hora_termino,time(18))
        self.assertEqual(self.client.delete(f'/api/disponibilidades/{self.slot.pk}/').status_code,400)
    def test_franjas_superpuestas(self):
        data={'veterinario':self.vet.pk,'dia_semana':self.day.weekday(),'hora_inicio':'10:00','hora_termino':'11:00'}
        self.assertEqual(self.client.post('/api/disponibilidades/',data).status_code,400)
    def test_exclusion_postgresql_incluso_bulk_create(self):
        a=Cita(mascota=self.pet,veterinario=self.vet,fecha=self.day,hora_inicio=time(10),hora_termino=time(11),motivo='Ficticio')
        Cita.objects.bulk_create([a])
        with self.assertRaises(IntegrityError),transaction.atomic():
            Cita.objects.bulk_create([Cita(mascota=self.pet2,veterinario=self.vet,fecha=self.day,hora_inicio=time(10,30),hora_termino=time(11,30),motivo='Conflicto')])

class ClinicalTests(DataMixin,TestCase):
    def setUp(self):self.create_data()
    def test_ficha_crud_historial_impresion(self):
        response=self.client.post('/api/fichas/',self.ficha(receta_medica='Ejemplo ficticio',examenes_solicitados='Campo de prueba',resultados='Ficticio'))
        self.assertEqual(response.status_code,201,response.data)
        pk=response.data['id']
        self.assertEqual(self.client.patch(f'/api/fichas/{pk}/',{'observaciones':'Actualizado'}).status_code,200)
        self.assertEqual(self.client.get(f'/api/fichas/?mascota={self.pet.pk}').data['count'],1)
        self.client.force_login(self.admin)
        response=self.client.get(f'/mascotas/{self.pet.pk}/imprimir/')
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'Ejemplo ficticio')
        self.assertEqual(self.client.delete(f'/api/fichas/{pk}/').status_code,204)
    def test_ficha_coincide_cita(self):
        a=self.client.post('/api/citas/',self.appointment()).data
        response=self.client.post('/api/fichas/',self.ficha(mascota=self.pet2.pk,cita=a['id']))
        self.assertEqual(response.status_code,400,response.data)
    def test_cita_con_ficha_conserva_relacion(self):
        a=self.client.post('/api/citas/',self.appointment()).data
        self.assertEqual(self.client.post('/api/fichas/',self.ficha(cita=a['id'])).status_code,201)
        self.assertEqual(self.client.patch(f"/api/citas/{a['id']}/",{'mascota':self.pet2.pk}).status_code,400)
    def test_vacuna_recordatorio_idempotente(self):
        response=self.client.post('/api/vacunas/',self.vacuna())
        self.assertEqual(response.status_code,201,response.data)
        pk=response.data['id']
        self.assertEqual(Recordatorio.objects.count(),1)
        actualizar_recordatorios();actualizar_recordatorios()
        self.assertEqual(Recordatorio.objects.count(),1)
        due=timezone.localdate()+timedelta(days=6)
        self.assertEqual(self.client.patch(f'/api/vacunas/{pk}/',{'fecha_proxima_dosis':str(due)}).status_code,200)
        self.assertEqual(Recordatorio.objects.get().fecha_programada,due)
        self.assertEqual(self.client.post('/api/vacunas/',self.vacuna()).status_code,400)
    def test_vacunas_vencidas_y_cerradas(self):
        a=self.client.post('/api/vacunas/',self.vacuna(fecha_proxima_dosis=str(timezone.localdate()-timedelta(days=1))))
        self.assertEqual(a.status_code,201,a.data)
        self.assertTrue(a.data['vencida'])
        self.assertEqual(self.client.get('/api/vacunas/?seguimiento=vencidas').data['count'],1)
        self.client.patch(f"/api/vacunas/{a.data['id']}/",{'seguimiento_cerrado':True})
        self.assertEqual(Recordatorio.objects.get().estado,'Atendido')
        self.assertEqual(self.client.get('/api/vacunas/?seguimiento=vencidas').data['count'],0)
    def test_fechas_vacuna_invalidas(self):
        self.assertEqual(self.client.post('/api/vacunas/',self.vacuna(fecha_proxima_dosis='2000-01-01')).status_code,400)
        self.assertEqual(self.client.post('/api/vacunas/',self.vacuna(fecha_aplicacion=str(timezone.localdate()+timedelta(days=10)))).status_code,400)
    def test_control_y_atender(self):
        payload={'mascota':self.pet.pk,'tipo':'Control','fecha_programada':str(self.day),'mensaje':'Control ficticio'}
        a=self.client.post('/api/recordatorios/',payload)
        self.assertEqual(a.status_code,201,a.data)
        self.assertEqual(self.client.post('/api/recordatorios/',payload).status_code,400)
        self.assertEqual(self.client.post(f"/api/recordatorios/{a.data['id']}/atender/").data['estado'],'Atendido')
    def test_recordatorio_automatico_no_cambia_origen(self):
        self.client.post('/api/vacunas/',self.vacuna())
        r=Recordatorio.objects.get()
        self.assertEqual(self.client.patch(f'/api/recordatorios/{r.pk}/',{'mascota':self.pet2.pk}).status_code,400)
    @override_settings(SMTP_CONFIGURED=True)
    @patch('clinica.services.send_mail',return_value=1)
    def test_correo_no_duplicado(self,send):
        self.client.post('/api/vacunas/',self.vacuna())
        self.assertEqual(enviar_recordatorios(),1)
        self.assertEqual(enviar_recordatorios(),0)
        self.assertEqual(send.call_count,1)
    @override_settings(SMTP_CONFIGURED=True)
    @patch('clinica.services.send_mail',side_effect=RuntimeError('secreto nunca persistido'))
    def test_error_smtp_no_expone_secretos(self,send):
        self.client.post('/api/vacunas/',self.vacuna())
        self.assertEqual(enviar_recordatorios(),0)
        self.assertNotIn('secreto',Recordatorio.objects.get().error_envio)
    def test_comando_recordatorios(self):
        self.client.post('/api/vacunas/',self.vacuna())
        out=StringIO();call_command('generar_recordatorios',stdout=out)
        self.assertEqual(Recordatorio.objects.count(),1)
        self.assertIn('Recordatorios nuevos: 0',out.getvalue())

    def test_recordatorio_mensaje_largo(self):
        # Evita superar el límite de filas de índice PostgreSQL con mensajes válidos extensos.
        message=secrets.token_urlsafe(2400)
        response=self.client.post('/api/recordatorios/',{'mascota':self.pet.pk,'tipo':'Control','fecha_programada':str(self.day),'mensaje':message})
        self.assertEqual(response.status_code,201,response.data)
        self.assertEqual(Recordatorio.objects.get().mensaje,message)

class AuthenticationTests(DataMixin,TestCase):
    def setUp(self):self.create_data()
    def test_login_hash_logout(self):
        self.assertNotEqual(self.admin.password,PASSWORD)
        self.assertTrue(self.admin.check_password(PASSWORD))
        client=APIClient()
        response=client.post('/login/',{'username':'admin','password':PASSWORD})
        self.assertEqual(response.status_code,302)
        self.assertEqual(client.get('/api/perfil/').data['rol'],'Administrador')
        self.assertEqual(client.post('/logout/').status_code,302)
        self.assertEqual(client.get('/api/mascotas/').status_code,403)
    def test_recepcion_no_accede_fichas(self):
        self.client.force_authenticate(self.reception)
        self.assertEqual(self.client.get('/api/fichas/').status_code,403)
        self.assertEqual(self.client.post('/api/fichas/',self.ficha()).status_code,403)
        self.assertEqual(self.client.post('/api/vacunas/',self.vacuna()).status_code,403)
        self.assertEqual(self.client.get('/api/usuarios/').status_code,403)
        self.assertEqual(self.client.post('/api/citas/',self.appointment()).status_code,201)
        self.client.force_login(self.reception)
        self.assertEqual(self.client.get(f'/mascotas/{self.pet.pk}/imprimir/').status_code,403)
    def test_veterinario_propio(self):
        self.client.force_authenticate(self.vetuser)
        self.assertEqual(self.client.post('/api/fichas/',self.ficha()).status_code,201)
        other=get_user_model().objects.create_user(username='otro_vet')
        vet=Veterinario.objects.create(usuario=other,nombre='Otro')
        self.assertEqual(self.client.post('/api/fichas/',self.ficha(veterinario=vet.pk)).status_code,403)
        self.client.force_authenticate(self.admin)
        other_record=self.client.post('/api/fichas/',self.ficha(veterinario=vet.pk)).data
        self.client.force_authenticate(self.vetuser)
        self.assertEqual(self.client.patch(f"/api/fichas/{other_record['id']}/",{'diagnostico':'Cambio ajeno'}).status_code,403)
        self.assertEqual(self.client.delete(f"/api/fichas/{other_record['id']}/").status_code,403)
    def test_usuario_sin_rol(self):
        user=get_user_model().objects.create_user(username='sinrol',password=PASSWORD)
        self.client.force_authenticate(user)
        self.assertEqual(self.client.get('/api/mascotas/').status_code,403)
    def test_perfil_no_escala_privilegios(self):
        self.client.force_authenticate(self.reception)
        self.assertEqual(self.client.patch('/api/perfil/',{'is_superuser':True}).status_code,400)
        self.assertEqual(self.client.patch('/api/perfil/',{'password':NEW_PASSWORD,'current_password':'incorrecta'}).status_code,400)
        self.assertEqual(self.client.patch('/api/perfil/',{'password':NEW_PASSWORD,'current_password':PASSWORD}).status_code,200)
        self.reception.refresh_from_db();self.assertTrue(self.reception.check_password(NEW_PASSWORD))
    def test_usuario_administracion(self):
        response=self.client.post('/api/usuarios/',{'username':'nuevo','password':NEW_PASSWORD,'rol':'Recepcionista'})
        self.assertEqual(response.status_code,201,response.data)
        self.assertNotIn('password',response.data)
        self.assertEqual(response.data['rol'],'Recepcionista')
        self.assertEqual(self.client.patch(f'/api/usuarios/{self.admin.pk}/',{'is_active':False}).status_code,400)
    def test_csrf_api_sesion(self):
        client=APIClient(enforce_csrf_checks=True)
        client.force_login(self.admin)
        response=client.post('/api/tutores/',{})
        self.assertEqual(response.status_code,403)
    def test_admin_modelos(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get('/admin/').status_code,200)
        for model in ['tutor','mascota','veterinario','disponibilidad','cita','fichaclinica','vacuna','recordatorio','actividad']:
            response=self.client.get(f'/admin/clinica/{model}/')
            self.assertEqual(response.status_code,200,model)

class DemoTests(TestCase):
    def test_demo_y_reejecucion_segura(self):
        out=StringIO();call_command('cargar_demo',stdout=out)
        self.assertEqual(Tutor.objects.count(),3)
        self.assertEqual(Cita.objects.count(),3)
        self.assertEqual(Recordatorio.objects.count(),3)
        with self.assertRaises(CommandError):call_command('cargar_demo',stdout=StringIO())
