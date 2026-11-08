"""Regresiones de reservas futuras; las integraciones usan solo la BD de pruebas."""
from datetime import date, datetime, time, timedelta, timezone as dt_timezone
from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.forms import modelform_factory
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from clinica.models import Cita, Disponibilidad
from .test_api import DataMixin


class BookingClockTests(SimpleTestCase):
    @patch('clinica.models.timezone.now')
    def test_clinic_day_and_strict_future(self, now):
        # 02:00 UTC aún es el día anterior en Santiago (invierno).
        now.return_value = datetime(2030, 7, 9, 2, tzinfo=dt_timezone.utc)
        for day, hour, rejected in [
            (date(2030, 7, 7), time(23), True),
            (date(2030, 7, 8), time(21), True),
            (date(2030, 7, 8), time(22), True),
            (date(2030, 7, 8), time(23), False),
            (date(2030, 7, 9), time(9), False),
        ]:
            with self.subTest(day=day, hour=hour):
                cita = Cita(mascota_id=1, veterinario_id=1, fecha=day,
                            hora_inicio=hour, hora_termino=time(hour.hour, 30), estado='Cancelada')
                if rejected:
                    with self.assertRaisesMessage(ValidationError, 'estrictamente futuras'):
                        cita.clean()
                else:
                    cita.clean()

    @patch('clinica.models.timezone.now')
    def test_clinic_timezone_independent_of_active_timezone(self, now):
        now.return_value = datetime(2030, 1, 9, 2, tzinfo=dt_timezone.utc)
        with timezone.override('Asia/Tokyo'):
            Cita(mascota_id=1, veterinario_id=1, fecha=date(2030, 1, 8),
                 hora_inicio=time(23, 30), hora_termino=time(23, 59), estado='Cancelada').clean()


class BookingIntegrationTests(DataMixin, TestCase):
    def setUp(self):
        self.create_data()

    def test_manipulated_post_and_cancelled_post_rejected(self):
        for state in ['Pendiente', 'Cancelada', 'Completada']:
            response = self.client.post('/api/citas/', self.appointment(
                fecha=str(timezone.localdate()-timedelta(days=1)), estado=state))
            self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(Cita.objects.count(), 0)

    def test_future_update_cannot_move_to_past(self):
        response = self.client.post('/api/citas/', self.appointment())
        self.assertEqual(response.status_code, 201, response.data)
        pk = response.data['id']
        for method in [self.client.patch, self.client.put]:
            payload = self.appointment(fecha=str(timezone.localdate()-timedelta(days=1)))
            response = method(f'/api/citas/{pk}/', payload)
            self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(Cita.objects.get(pk=pk).fecha, self.day)

    def test_history_visible_and_status_editable(self):
        response = self.client.post('/api/citas/', self.appointment())
        pk = response.data['id']
        # Simular el paso del tiempo sin insertar reservas históricas inválidas.
        with patch('django.utils.timezone.now', return_value=timezone.now()+timedelta(days=30)):
            self.assertEqual(self.client.get(f'/api/citas/{pk}/').status_code, 200)
            for state in ['Completada', 'Cancelada']:
                response = self.client.patch(f'/api/citas/{pk}/', {'estado': state})
                self.assertEqual(response.status_code, 200, response.data)
            response = self.client.patch(f'/api/citas/{pk}/', {'estado': 'Pendiente'})
            self.assertEqual(response.status_code, 400, response.data)
            response = self.client.patch(f'/api/citas/{pk}/', {'hora_inicio': '11:00', 'hora_termino': '11:30'})
            self.assertEqual(response.status_code, 400, response.data)

    def test_completed_history_cannot_be_reopened(self):
        response = self.client.post('/api/citas/', self.appointment(estado='Completada'))
        self.assertEqual(response.status_code, 201, response.data)
        pk = response.data['id']
        with patch('django.utils.timezone.now', return_value=timezone.now()+timedelta(days=30)):
            for state in ['Pendiente', 'Confirmada']:
                response = self.client.patch(f'/api/citas/{pk}/', {'estado': state})
                self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(Cita.objects.get(pk=pk).estado, 'Completada')

    def test_admin_model_form_rejects_past(self):
        form_class = modelform_factory(Cita, exclude=['creada'])
        form = form_class(data=self.appointment(fecha=str(timezone.localdate()-timedelta(days=1))))
        self.assertFalse(form.is_valid())
        self.assertIn('estrictamente futuras', str(form.errors))

    def test_today_future_tomorrow_and_occupied(self):
        today = timezone.localdate()
        for day in [today, today+timedelta(days=1)]:
            Disponibilidad.objects.get_or_create(veterinario=self.vet, dia_semana=day.weekday(),
                                               defaults={'hora_inicio': time(9), 'hora_termino': time(18)})
        clock = timezone.make_aware(datetime.combine(today, time(10)))
        with patch('django.utils.timezone.now', return_value=clock):
            self.assertEqual(self.client.post('/api/citas/', self.appointment(fecha=str(today))).status_code, 400)
            payload = self.appointment(fecha=str(today), hora_inicio='11:00', hora_termino='11:30')
            self.assertEqual(self.client.post('/api/citas/', payload).status_code, 201)
            self.assertEqual(self.client.post('/api/citas/', payload).status_code, 400)
            self.assertEqual(self.client.post('/api/citas/', self.appointment(fecha=str(today+timedelta(days=1)))).status_code, 201)
