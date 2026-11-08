from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from .models import Tutor, Mascota, Veterinario, Disponibilidad, Cita, FichaClinica, Vacuna, Recordatorio
from .permissions import ADMIN, VET, RECEPTION, TUTOR, role
from .validators import normalizar_rut

class TutorSerializer(serializers.ModelSerializer):
    nombre_completo = serializers.SerializerMethodField()
    class Meta:
        model = Tutor
        fields = '__all__'
        read_only_fields = ['fecha_registro','usuario']
        extra_kwargs = {'rut':{'validators':[]}}
    def get_nombre_completo(self,obj):
        return str(obj)
    def validate_rut(self,value):
        try:
            value = normalizar_rut(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages)
        if Tutor.objects.filter(rut=value).exclude(pk=self.instance.pk if self.instance else None).exists():
            raise serializers.ValidationError('Ya existe un tutor con este RUT.')
        return value

class OwnedSerializer(serializers.ModelSerializer):
    def lock_patient(self, attrs):
        request = self.context.get('request')
        if not request or role(request.user) != TUTOR or self.Meta.model != Cita:
            return
        professional = attrs.get('veterinario',getattr(self.instance,'veterinario',None))
        patient = attrs.get('mascota',getattr(self.instance,'mascota',None))
        if professional and patient:
            Veterinario.objects.select_for_update().get(pk=professional.pk)
            patient = Mascota.objects.select_for_update().get(pk=patient.pk)
            if 'mascota' in attrs:
                attrs['mascota'] = patient
            elif self.instance:
                self.instance.mascota = patient
    def create(self, validated_data):
        from django.db import transaction
        with transaction.atomic():
            self.lock_patient(validated_data)
            self.validate(validated_data)
            return super().create(validated_data)
    def update(self, instance, validated_data):
        from django.db import transaction
        with transaction.atomic():
            instance = type(instance).objects.select_for_update().get(pk=instance.pk)
            self.instance = instance
            self.lock_patient(validated_data)
            self.validate(validated_data)
            return super().update(instance,validated_data)

    def validate(self, attrs):
        request = self.context.get('request')
        if request and role(request.user) == TUTOR:
            if self.Meta.model == Mascota:
                owner = attrs.get('tutor', getattr(self.instance, 'tutor', None))
                if owner != request.user.tutor:
                    raise serializers.ValidationError('Selecciona tu propio perfil de tutor.')
            if self.Meta.model == Cita:
                from django.utils import timezone
                from datetime import datetime
                pet = attrs.get('mascota', getattr(self.instance, 'mascota', None))
                if not pet or pet.tutor_id != request.user.tutor.pk:
                    raise serializers.ValidationError('Selecciona una mascota de tu cuenta.')
                if self.instance:
                    if set(attrs) != {'estado'} or attrs['estado'] != 'Cancelada':
                        raise serializers.ValidationError('Solo puedes cancelar una reserva; para reprogramar, cancela y reserva otra hora.')
                    if self.instance.estado not in ('Pendiente','Confirmada'):
                        raise serializers.ValidationError('Esta cita ya no se puede cancelar.')
                elif attrs.get('estado', 'Pendiente') != 'Pendiente':
                    raise serializers.ValidationError('Las reservas nuevas quedan pendientes de confirmación.')
                if not self.instance:
                    from datetime import timedelta
                    day_value = attrs.get('fecha')
                    start_value, end_value = attrs.get('hora_inicio'), attrs.get('hora_termino')
                    if day_value and day_value > timezone.localdate()+timedelta(days=180):
                        raise serializers.ValidationError('Reserva dentro de los próximos 180 días.')
                    if start_value and end_value and datetime.combine(timezone.localdate(),end_value)-datetime.combine(timezone.localdate(),start_value) != timedelta(minutes=30):
                        raise serializers.ValidationError('Las reservas del portal duran 30 minutos.')
                day = attrs.get('fecha', getattr(self.instance,'fecha',None))
                hour = attrs.get('hora_inicio', getattr(self.instance,'hora_inicio',None))
                if day and hour and timezone.make_aware(datetime.combine(day,hour)) <= timezone.now():
                    raise serializers.ValidationError('Solo puedes reservar o cancelar citas futuras.')
        return super().validate(attrs)

class MascotaSerializer(OwnedSerializer):
    tutor_nombre = serializers.CharField(source='tutor.__str__',read_only=True)
    class Meta:
        model = Mascota
        fields = '__all__'

class VeterinarioSerializer(serializers.ModelSerializer):
    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        if request and role(request.user) == TUTOR:
            data.pop('usuario', None)
            data.pop('usuario_nombre', None)
        return data

    usuario_nombre = serializers.CharField(source='usuario.username',read_only=True)
    class Meta:
        model = Veterinario
        fields = '__all__'
    def validate_usuario(self,value):
        if not value.is_active or not value.groups.filter(name=VET).exists():
            raise serializers.ValidationError('Asocia un usuario activo del grupo Veterinario.')
        return value

class ClinicalSerializer(serializers.ModelSerializer):
    def validate(self, attrs):
        request = self.context.get('request')
        if request and role(request.user) == VET:
            professional = attrs.get('veterinario',getattr(self.instance,'veterinario',None))
            if professional is None or professional.usuario_id != request.user.pk:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied('Solo puedes registrar información bajo tu perfil veterinario.')
        return super().validate(attrs)

class DisponibilidadSerializer(ClinicalSerializer):
    veterinario_nombre = serializers.CharField(source='veterinario.nombre',read_only=True)
    dia_nombre = serializers.CharField(source='get_dia_semana_display',read_only=True)
    class Meta:
        model = Disponibilidad
        fields = '__all__'

class CitaSerializer(OwnedSerializer):
    ficha_id = serializers.IntegerField(source="ficha.pk",read_only=True,default=None)
    mascota_nombre = serializers.CharField(source='mascota.nombre',read_only=True)
    veterinario_nombre = serializers.CharField(source='veterinario.nombre',read_only=True)
    tutor_nombre = serializers.CharField(source='mascota.tutor.__str__',read_only=True)
    class Meta:
        model = Cita
        fields = '__all__'
        read_only_fields = ['creada']
        # El modelo valida dentro de una transacción; las restricciones son la última barrera.
        validators = []

class FichaClinicaSerializer(ClinicalSerializer):
    mascota_nombre = serializers.CharField(source='mascota.nombre',read_only=True)
    veterinario_nombre = serializers.CharField(source='veterinario.nombre',read_only=True)
    class Meta:
        model = FichaClinica
        fields = '__all__'
        read_only_fields = ['actualizada']

class VacunaSerializer(ClinicalSerializer):
    mascota_nombre = serializers.CharField(source='mascota.nombre',read_only=True)
    veterinario_nombre = serializers.CharField(source='veterinario.nombre',read_only=True)
    vencida = serializers.SerializerMethodField()
    class Meta:
        model = Vacuna
        fields = '__all__'
    def get_vencida(self,obj):
        from django.utils import timezone
        return not obj.seguimiento_cerrado and obj.fecha_proxima_dosis < timezone.localdate()

class RecordatorioSerializer(serializers.ModelSerializer):
    mascota_nombre = serializers.CharField(source='mascota.nombre',read_only=True)
    class Meta:
        model = Recordatorio
        fields = '__all__'
        read_only_fields = ['fecha_creacion','correo_enviado','error_envio','vacuna']
    def validate(self,attrs):
        if self.instance and self.instance.vacuna_id:
            for field in ('mascota','tipo','fecha_programada','mensaje'):
                if field in attrs and attrs[field] != getattr(self.instance,field):
                    raise serializers.ValidationError('Modifica la vacuna de origen para cambiar este recordatorio automático; aquí puedes actualizar su estado.')
        elif attrs.get('tipo',getattr(self.instance,'tipo',None)) != 'Control':
            raise serializers.ValidationError('Los recordatorios manuales deben ser de tipo Control. Los de vacuna se generan automáticamente.')
        return attrs

class UsuarioSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True,required=False,trim_whitespace=False)
    class Meta:
        model = get_user_model()
        fields = ['id','username','first_name','last_name','email','is_active','rol','password']
    def to_representation(self,obj):
        result = super().to_representation(obj)
        result['rol'] = role(obj) or next(iter(obj.groups.values_list('name',flat=True)), '')
        return result
    def validate(self,attrs):
        if not self.instance and not attrs.get('password'):
            raise serializers.ValidationError({'password':'La contraseña es obligatoria.'})
        if attrs.get('password'):
            user = self.instance or get_user_model()(username=attrs.get('username',''))
            try:
                password_validation.validate_password(attrs['password'],user)
            except DjangoValidationError as exc:
                raise serializers.ValidationError({'password':exc.messages})
        if self.instance and self.instance.is_superuser and attrs.get('rol',ADMIN) != ADMIN:
            raise serializers.ValidationError('Un superusuario mantiene el rol Administrador; gestiona sus privilegios desde Django Admin.')
        if self.instance and self.instance == self.context['request'].user:
            if not attrs.get('is_active',True) or attrs.get('rol',ADMIN) != ADMIN:
                raise serializers.ValidationError('No puedes desactivar ni retirar tu propio rol administrador.')
        return attrs
    def create(self,validated_data):
        group = validated_data.pop('rol')
        password = validated_data.pop('password')
        user = get_user_model().objects.create_user(password=password,**validated_data)
        user.groups.set([Group.objects.get(name=group)])
        user.is_staff = group == ADMIN
        user.save(update_fields=['is_staff'])
        return user
    def update(self,instance,validated_data):
        group = validated_data.pop('rol',None)
        password = validated_data.pop('password',None)
        for key,value in validated_data.items():
            setattr(instance,key,value)
        if password:
            instance.set_password(password)
        if group:
            instance.groups.set([Group.objects.get(name=group)])
            instance.is_staff = group == ADMIN
        instance.save()
        return instance
    # El campo no es un atributo del modelo: representación calculada.
    rol = serializers.ChoiceField(choices=[ADMIN,VET,RECEPTION],default=RECEPTION)
