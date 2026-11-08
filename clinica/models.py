from datetime import datetime, timedelta
from decimal import Decimal
from django.conf import settings
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateTimeRangeField
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models, transaction
from django.db.models import F, Q, Value, Func
from django.db.models.functions import MD5
from django.utils import timezone
from .validators import validar_rut, normalizar_rut, validar_telefono, no_futura

class ValidatedModel(models.Model):
    """Validaciones compartidas también en escrituras del admin/ORM (no bulk_update)."""
    class Meta:
        abstract = True
    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

class Tutor(ValidatedModel):
    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="tutor", null=True, blank=True)
    nombre = models.CharField(max_length=100)
    apellidos = models.CharField(max_length=150)
    rut = models.CharField(max_length=12, unique=True, validators=[validar_rut])
    telefono = models.CharField(max_length=24, validators=[validar_telefono])
    correo = models.EmailField()
    direccion = models.CharField(max_length=250)
    fecha_registro = models.DateTimeField(auto_now_add=True)
    class Meta:
        verbose_name = 'tutor'
        verbose_name_plural = 'tutores'
        ordering = ['apellidos','nombre']
    def clean(self):
        self.rut = normalizar_rut(self.rut)
        self.correo = self.correo.lower().strip()
    def __str__(self):
        return f'{self.nombre} {self.apellidos}'

class Mascota(ValidatedModel):
    tutor = models.ForeignKey(Tutor, on_delete=models.PROTECT, related_name='mascotas')
    nombre = models.CharField(max_length=100)
    especie = models.CharField(max_length=12, choices=[(x,x) for x in ['Perro','Gato','Ave','Conejo','Otro']])
    raza = models.CharField(max_length=100, blank=True)
    sexo = models.CharField(max_length=20, choices=[(x,x) for x in ['Macho','Hembra','Sin especificar']])
    fecha_nacimiento = models.DateField(validators=[no_futura])
    peso = models.DecimalField(max_digits=6,decimal_places=2,validators=[MinValueValidator(Decimal('0.01')),MaxValueValidator(1000)])
    observaciones = models.TextField(blank=True, max_length=4000)
    class Meta:
        ordering = ['nombre']
        constraints = [models.CheckConstraint(condition=Q(peso__gt=0,peso__lte=1000), name='mascota_peso_valido')]
    def __str__(self):
        return self.nombre

class Veterinario(ValidatedModel):
    usuario = models.OneToOneField(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='veterinario')
    nombre = models.CharField(max_length=150)
    especialidad = models.CharField(max_length=150,default='Medicina general')
    activo = models.BooleanField(default=True)
    class Meta:
        ordering = ['nombre']
    def __str__(self):
        return self.nombre

DIAS = [(0,'Lunes'),(1,'Martes'),(2,'Miércoles'),(3,'Jueves'),(4,'Viernes'),(5,'Sábado'),(6,'Domingo')]

class Disponibilidad(ValidatedModel):
    veterinario = models.ForeignKey(Veterinario,on_delete=models.CASCADE,related_name='disponibilidades')
    dia_semana = models.PositiveSmallIntegerField(choices=DIAS)
    hora_inicio = models.TimeField()
    hora_termino = models.TimeField()
    class Meta:
        verbose_name_plural = 'disponibilidades'
        ordering = ['veterinario','dia_semana','hora_inicio']
        constraints = [models.CheckConstraint(condition=Q(hora_termino__gt=F('hora_inicio')),name='disponibilidad_orden_horas'),
                       models.CheckConstraint(condition=Q(dia_semana__gte=0,dia_semana__lte=6),name='disponibilidad_dia_valido')]
    def __str__(self):
        return f'{self.veterinario} · {self.get_dia_semana_display()} {self.hora_inicio:%H:%M}–{self.hora_termino:%H:%M}'
    def clean(self):
        if self.hora_inicio and self.hora_termino and self.hora_inicio >= self.hora_termino:
            raise ValidationError('El término debe ser posterior al inicio.')
        if self.veterinario_id and self.dia_semana is not None and self.hora_inicio and self.hora_termino:
            conflict = Disponibilidad.objects.filter(veterinario_id=self.veterinario_id,dia_semana=self.dia_semana,
                       hora_inicio__lt=self.hora_termino,hora_termino__gt=self.hora_inicio).exclude(pk=self.pk)
            if conflict.exists():
                raise ValidationError('Esta franja se superpone con otra disponibilidad.')
    def save(self,*args,**kwargs):
        with transaction.atomic():
            previous = Disponibilidad.objects.select_for_update().filter(pk=self.pk).first() if self.pk else None
            ids = sorted({v for v in [self.veterinario_id, previous.veterinario_id if previous else None] if v})
            list(Veterinario.objects.select_for_update().filter(pk__in=ids).order_by('pk'))
            result = super().save(*args,**kwargs)
            for vet_id in ids:
                validar_citas_futuras(vet_id)
            return result
    def delete(self,*args,**kwargs):
        with transaction.atomic():
            Veterinario.objects.select_for_update().get(pk=self.veterinario_id)
            result = super().delete(*args,**kwargs)
            validar_citas_futuras(self.veterinario_id)
            return result

class Cita(ValidatedModel):
    ESTADOS = [(x,x) for x in ['Pendiente','Confirmada','Completada','Cancelada']]
    mascota = models.ForeignKey(Mascota,on_delete=models.PROTECT,related_name='citas')
    veterinario = models.ForeignKey(Veterinario,on_delete=models.PROTECT,related_name='citas')
    fecha = models.DateField(db_index=True)
    hora_inicio = models.TimeField()
    hora_termino = models.TimeField()
    motivo = models.CharField(max_length=500)
    estado = models.CharField(max_length=12,choices=ESTADOS,default='Pendiente')
    creada = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['fecha','hora_inicio','id']
        indexes = [models.Index(fields=['veterinario','fecha']),models.Index(fields=['mascota','fecha'])]
        constraints = [
            models.CheckConstraint(condition=Q(hora_termino__gt=F('hora_inicio')),name='cita_orden_horas'),
            models.CheckConstraint(condition=Q(estado__in=['Pendiente','Confirmada','Completada','Cancelada']),name='cita_estado_valido'),
            ExclusionConstraint(name='cita_veterinario_sin_solapamiento',expressions=[
                ('veterinario','='),(Func(F('fecha')+F('hora_inicio'),F('fecha')+F('hora_termino'),Value('[)'),function='tsrange',output_field=DateTimeRangeField()),'&&')],condition=~Q(estado='Cancelada')),
            ExclusionConstraint(name='cita_mascota_sin_solapamiento',expressions=[
                ('mascota','='),(Func(F('fecha')+F('hora_inicio'),F('fecha')+F('hora_termino'),Value('[)'),function='tsrange',output_field=DateTimeRangeField()),'&&')],condition=~Q(estado='Cancelada')),
        ]
    def __str__(self):
        return f'{self.mascota} · {self.fecha} {self.hora_inicio:%H:%M}'
    def clean(self):
        if not all([self.fecha,self.hora_inicio,self.hora_termino,self.veterinario_id,self.mascota_id]):
            return
        start = datetime.combine(self.fecha,self.hora_inicio)
        end = datetime.combine(self.fecha,self.hora_termino)
        if end <= start or end-start > timedelta(hours=4):
            raise ValidationError('La cita debe durar entre 1 minuto y 4 horas.')
        if self.hora_inicio.second or self.hora_termino.second or self.hora_inicio.microsecond or self.hora_termino.microsecond:
            raise ValidationError('Utiliza horas y minutos, sin segundos.')
        # Conservar el horario histórico permite actualizar notas y estados,
        # pero nunca crear o trasladar una reserva al pasado (incluso cancelada).
        previous = Cita.objects.filter(pk=self.pk).first() if self.pk else None
        booking_fields = ('fecha', 'hora_inicio', 'hora_termino', 'mascota_id', 'veterinario_id')
        booking_changed = previous is None or any(
            getattr(previous, field) != getattr(self, field) for field in booking_fields
        )
        if previous and previous.estado != self.estado and self.estado in ('Pendiente', 'Confirmada'):
            booking_changed = True
        local_now = timezone.localtime(timezone.now(), timezone.get_default_timezone()).replace(tzinfo=None)
        if booking_changed and start <= local_now:
            raise ValidationError({'fecha': 'La cita debe comenzar en una fecha y hora estrictamente futuras.'})
        if self.pk and FichaClinica.objects.filter(cita_id=self.pk).exists():
            old = Cita.objects.get(pk=self.pk)
            if old.mascota_id != self.mascota_id or old.veterinario_id != self.veterinario_id or self.estado == 'Cancelada':
                raise ValidationError('La cita tiene una atención clínica. Conserva su paciente, profesional e historial.')
        if self.estado == 'Cancelada':
            return
        if not Veterinario.objects.filter(pk=self.veterinario_id,activo=True,usuario__is_active=True).exists():
            raise ValidationError('El veterinario está inactivo.')
        if not Disponibilidad.objects.filter(veterinario_id=self.veterinario_id,dia_semana=self.fecha.weekday(),
                  hora_inicio__lte=self.hora_inicio,hora_termino__gte=self.hora_termino).exists():
            raise ValidationError('La cita está fuera de la disponibilidad del profesional.')
        if Cita.objects.filter(Q(veterinario_id=self.veterinario_id)|Q(mascota_id=self.mascota_id),fecha=self.fecha,
                  hora_inicio__lt=self.hora_termino,hora_termino__gt=self.hora_inicio).exclude(pk=self.pk).exclude(estado='Cancelada').exists():
            raise ValidationError('Horario ocupado: el profesional o la mascota tiene otra cita en ese intervalo.')
    def save(self,*args,**kwargs):
        with transaction.atomic():
            previous = Cita.objects.select_for_update().filter(pk=self.pk).first() if self.pk else None
            vet_ids = {self.veterinario_id}
            pet_ids = {self.mascota_id}
            if previous:
                vet_ids.add(previous.veterinario_id)
                pet_ids.add(previous.mascota_id)
            # Orden global: primero profesionales, luego mascotas; una fila estable incluso con agenda vacía.
            list(Veterinario.objects.select_for_update().filter(pk__in=vet_ids).order_by('pk'))
            list(Mascota.objects.select_for_update().filter(pk__in=pet_ids).order_by('pk'))
            # Las exclusiones PostgreSQL vuelven a proteger incluso una escritura externa al servicio.
            self.full_clean(validate_constraints=False)
            return models.Model.save(self,*args,**kwargs)

def validar_citas_futuras(vet_id):
    now = timezone.localtime()
    qs = Cita.objects.filter(veterinario_id=vet_id,estado__in=['Pendiente','Confirmada']).filter(
        Q(fecha__gt=now.date())|Q(fecha=now.date(),hora_termino__gte=now.time().replace(tzinfo=None)))
    for cita in qs:
        if not Disponibilidad.objects.filter(veterinario_id=vet_id,dia_semana=cita.fecha.weekday(),
              hora_inicio__lte=cita.hora_inicio,hora_termino__gte=cita.hora_termino).exists():
            raise ValidationError('El cambio deja citas futuras fuera de horario. Reprograma o cancela las citas primero.')

class FichaClinica(ValidatedModel):
    mascota = models.ForeignKey(Mascota,on_delete=models.PROTECT,related_name='fichas')
    veterinario = models.ForeignKey(Veterinario,on_delete=models.PROTECT,related_name='fichas')
    cita = models.OneToOneField(Cita,on_delete=models.PROTECT,related_name='ficha',blank=True,null=True)
    fecha_atencion = models.DateField(default=timezone.localdate,validators=[no_futura])
    motivo = models.CharField(max_length=500)
    sintomas = models.TextField(max_length=5000)
    diagnostico = models.TextField(max_length=5000)
    tratamiento = models.TextField(max_length=5000)
    receta_medica = models.TextField(blank=True,max_length=5000)
    examenes_solicitados = models.TextField(blank=True,max_length=5000)
    resultados = models.TextField(blank=True,max_length=5000)
    observaciones = models.TextField(blank=True,max_length=5000)
    actualizada = models.DateTimeField(auto_now=True)
    class Meta:
        verbose_name = 'ficha clínica'
        verbose_name_plural = 'fichas clínicas'
        ordering = ['-fecha_atencion','-id']
    def clean(self):
        if self.cita_id:
            cita = Cita.objects.get(pk=self.cita_id)
            if cita.mascota_id != self.mascota_id or cita.veterinario_id != self.veterinario_id:
                raise ValidationError('La cita debe corresponder a la misma mascota y al mismo veterinario.')
            if cita.estado == 'Cancelada':
                raise ValidationError('No se puede asociar una atención a una cita cancelada.')
    def __str__(self):
        return f'{self.mascota} · atención {self.fecha_atencion}'

class Vacuna(ValidatedModel):
    mascota = models.ForeignKey(Mascota,on_delete=models.PROTECT,related_name='vacunas')
    nombre = models.CharField(max_length=150)
    fecha_aplicacion = models.DateField(validators=[no_futura])
    fecha_proxima_dosis = models.DateField(db_index=True)
    veterinario = models.ForeignKey(Veterinario,on_delete=models.PROTECT,related_name='vacunas')
    observaciones = models.TextField(blank=True,max_length=4000)
    seguimiento_cerrado = models.BooleanField(default=False,help_text='Marcar al registrar la nueva dosis o resolver el seguimiento.')
    class Meta:
        ordering = ['fecha_proxima_dosis','id']
        constraints = [models.CheckConstraint(condition=Q(fecha_proxima_dosis__gte=F('fecha_aplicacion')),name='vacuna_orden_fechas'),
                       models.UniqueConstraint(fields=['mascota','nombre','fecha_aplicacion'],name='vacuna_aplicacion_unica')]
    def clean(self):
        if self.fecha_aplicacion and self.fecha_proxima_dosis and self.fecha_proxima_dosis < self.fecha_aplicacion:
            raise ValidationError('La próxima dosis no puede ser anterior a la aplicación.')
    def save(self,*args,**kwargs):
        with transaction.atomic():
            return super().save(*args,**kwargs)
    def __str__(self):
        return f'{self.nombre} · {self.mascota}'

class Recordatorio(ValidatedModel):
    mascota = models.ForeignKey(Mascota,on_delete=models.PROTECT,related_name='recordatorios')
    vacuna = models.OneToOneField(Vacuna,on_delete=models.CASCADE,related_name='recordatorio',null=True,blank=True)
    tipo = models.CharField(max_length=10,choices=[('Vacuna','Vacuna'),('Control','Control')])
    fecha_programada = models.DateField(db_index=True)
    mensaje = models.TextField(max_length=4000)
    estado = models.CharField(max_length=10,choices=[('Pendiente','Pendiente'),('Atendido','Atendido')],default='Pendiente')
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    correo_enviado = models.DateTimeField(null=True,blank=True)
    error_envio = models.CharField(max_length=200,blank=True)
    class Meta:
        ordering = ['fecha_programada','id']
        constraints = [models.CheckConstraint(condition=Q(estado__in=['Pendiente','Atendido']),name='recordatorio_estado_valido'),
                       models.UniqueConstraint(F('mascota'),F('tipo'),F('fecha_programada'),MD5('mensaje'),name='recordatorio_unico')]
    def clean(self):
        if self.vacuna_id and (self.tipo != 'Vacuna' or self.vacuna.mascota_id != self.mascota_id):
            raise ValidationError('El recordatorio debe corresponder a la mascota y al tipo de la vacuna.')
    def __str__(self):
        return f'{self.tipo} · {self.mascota} · {self.fecha_programada}'

class Actividad(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True)
    accion = models.CharField(max_length=150)
    entidad = models.CharField(max_length=80)
    objeto_id = models.PositiveBigIntegerField(null=True)
    fecha = models.DateTimeField(auto_now_add=True)
    class Meta:
        verbose_name_plural = 'actividad reciente'
        ordering = ['-fecha','-id']
    def __str__(self):
        return f'{self.accion} · {self.entidad}'

class LoginWindow(models.Model):
    """Contador compartido en PostgreSQL, sin dirección ni identidad en claro."""
    key = models.CharField(max_length=64, unique=True)
    attempts = models.PositiveIntegerField(default=0)
    expires = models.DateTimeField()
