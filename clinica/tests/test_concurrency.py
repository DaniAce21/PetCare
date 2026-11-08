"""Usa conexiones PostgreSQL independientes. No simula bloqueos ni usa SQLite."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.db import close_old_connections, connection, transaction, IntegrityError
from django.test import TransactionTestCase
from rest_framework.test import APIClient
from clinica.models import Cita, Veterinario, Disponibilidad
from django.contrib.auth import get_user_model
from datetime import time
from .test_api import DataMixin

class ConcurrentBookingTests(DataMixin,TransactionTestCase):
    reset_sequences=True
    def setUp(self):
        self.create_data()
        self.assertEqual(connection.vendor,'postgresql')
    def run_parallel(self,requests):
        barrier=Barrier(len(requests),timeout=15)
        def worker(item):
            close_old_connections()
            try:
                client=APIClient();client.force_authenticate(get_user_model().objects.get(pk=self.admin.pk))
                barrier.wait()
                method,path,data=item
                response=getattr(client,method)(path,data,format='json')
                return response.status_code
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=len(requests)) as pool:
            return list(pool.map(worker,requests))
    def test_reserva_simultanea_mismo_veterinario(self):
        result=self.run_parallel([('post','/api/citas/',self.appointment()),('post','/api/citas/',self.appointment(mascota=self.pet2.pk))])
        self.assertEqual(sorted(result),[201,400])
        self.assertEqual(Cita.objects.count(),1)
    def test_reserva_simultanea_misma_mascota(self):
        user=get_user_model().objects.create_user(username='otro')
        vet=Veterinario.objects.create(usuario=user,nombre='Otro profesional')
        Disponibilidad.objects.create(veterinario=vet,dia_semana=self.day.weekday(),hora_inicio=time(9),hora_termino=time(18))
        result=self.run_parallel([('post','/api/citas/',self.appointment()),('post','/api/citas/',self.appointment(veterinario=vet.pk))])
        self.assertEqual(sorted(result),[201,400])
        self.assertEqual(Cita.objects.count(),1)
    def test_cambio_disponibilidad_y_reserva_concurrentes(self):
        result=self.run_parallel([('post','/api/citas/',self.appointment()),('patch',f'/api/disponibilidades/{self.slot.pk}/',{'hora_termino':'10:00'})])
        self.assertEqual(result.count(400),1)
        self.assertIn(201 if result[0]==201 else 200,result)
        if Cita.objects.exists():
            self.slot.refresh_from_db();self.assertEqual(self.slot.hora_termino,time(18))

    def test_limite_login_compartido_simultaneo(self):
        from clinica.models import LoginWindow
        results=self.run_parallel([('post','/login/',{'username':'desconocido','password':'incorrecta'}) for _ in range(12)])
        self.assertEqual(results.count(200),10)
        self.assertEqual(results.count(429),2)
        self.assertFalse(LoginWindow.objects.filter(attempts__gt=10).exists())
