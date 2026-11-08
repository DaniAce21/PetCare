from datetime import timedelta
from django.contrib.auth import get_user_model, password_validation, update_session_auth_hash
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from .models import Tutor, Mascota, Veterinario, Disponibilidad, Cita, FichaClinica, Vacuna, Recordatorio, Actividad
from .serializers import (TutorSerializer,MascotaSerializer,VeterinarioSerializer,DisponibilidadSerializer,
    CitaSerializer,FichaClinicaSerializer,VacunaSerializer,RecordatorioSerializer,UsuarioSerializer)
from .permissions import PetCarePermission,role,vet_id,ADMIN,VET,TUTOR

class BaseViewSet(viewsets.ModelViewSet):
    permission_classes = [PetCarePermission]
    ordering_fields = ['id']
    filters = {}
    def get_queryset(self):
        qs = super().get_queryset()
        if role(self.request.user) == TUTOR:
            owner = self.request.user.tutor
            if self.resource == 'tutores':
                qs = qs.filter(pk=owner.pk)
            elif self.resource == 'mascotas':
                qs = qs.filter(tutor=owner)
            elif self.resource in ('citas','fichas','vacunas','recordatorios'):
                qs = qs.filter(mascota__tutor=owner)
            elif self.resource == 'veterinarios':
                qs = qs.filter(activo=True, usuario__is_active=True)
            elif self.resource == 'disponibilidades':
                qs = qs.filter(veterinario__activo=True, veterinario__usuario__is_active=True)
            else:
                qs = qs.none()
        for param,lookup in self.filters.items():
            value = self.request.query_params.get(param)
            if value:
                try:
                    if lookup.endswith('_id') and (not value.isdigit() or len(value)>12):
                        raise ValueError()
                    if 'fecha' in lookup:
                        from datetime import date
                        date.fromisoformat(value)
                    if lookup == 'dia_semana' and (not value.isdigit() or int(value)>6):
                        raise ValueError()
                    qs = qs.filter(**{lookup:value})
                except (ValueError,TypeError):
                    raise ValidationError({param:'Filtro inválido.'})
        return qs
    def check_professional(self,serializer):
        if self.resource in ('fichas','vacunas','disponibilidades') and role(self.request.user)==VET:
            professional = serializer.validated_data.get('veterinario',getattr(serializer.instance,'veterinario',None))
            if not professional or professional.pk != vet_id(self.request.user):
                raise PermissionDenied('Solo puedes registrar o modificar información bajo tu propio perfil veterinario.')
    @transaction.atomic
    def perform_create(self,serializer):
        self.check_professional(serializer)
        instance = serializer.save()
        self.audit('Registro creado',instance)
    @transaction.atomic
    def perform_update(self,serializer):
        self.check_professional(serializer)
        instance = serializer.save()
        self.audit('Registro actualizado',instance)
    @transaction.atomic
    def perform_destroy(self,instance):
        self.audit('Registro eliminado',instance)
        instance.delete()
    def audit(self,action,instance):
        Actividad.objects.create(usuario=self.request.user,accion=action,entidad=self.resource,objeto_id=instance.pk)

class TutorViewSet(BaseViewSet):
    resource = 'tutores'
    queryset = Tutor.objects.all()
    serializer_class = TutorSerializer
    search_fields = ['nombre','apellidos','rut','correo','telefono']
    ordering_fields = ['id','apellidos','nombre','fecha_registro']

class MascotaViewSet(BaseViewSet):
    resource = 'mascotas'
    queryset = Mascota.objects.select_related('tutor')
    serializer_class = MascotaSerializer
    search_fields = ['nombre','raza','tutor__nombre','tutor__apellidos','tutor__rut']
    filters = {'tutor':'tutor_id','especie':'especie'}
    ordering_fields = ['id','nombre','fecha_nacimiento']

class VeterinarioViewSet(BaseViewSet):
    resource = 'veterinarios'
    queryset = Veterinario.objects.select_related('usuario')
    serializer_class = VeterinarioSerializer
    search_fields = ['nombre','especialidad']

class DisponibilidadViewSet(BaseViewSet):
    resource = 'disponibilidades'
    queryset = Disponibilidad.objects.select_related('veterinario')
    serializer_class = DisponibilidadSerializer
    filters = {'veterinario':'veterinario_id','dia':'dia_semana'}
    search_fields = ['veterinario__nombre']

class CitaViewSet(BaseViewSet):
    resource = 'citas'
    queryset = Cita.objects.select_related('mascota__tutor','veterinario')
    serializer_class = CitaSerializer
    search_fields = ['motivo','mascota__nombre','veterinario__nombre']
    filters = {'mascota':'mascota_id','veterinario':'veterinario_id','estado':'estado','desde':'fecha__gte','hasta':'fecha__lte'}
    ordering_fields = ['id','fecha','hora_inicio']
    @action(detail=True,methods=['post'])
    def cancelar(self,request,pk=None):
        instance = self.get_object()
        serializer = self.get_serializer(instance,data={'estado':'Cancelada'},partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)

class FichaClinicaViewSet(BaseViewSet):
    resource = 'fichas'
    queryset = FichaClinica.objects.select_related('mascota','veterinario','cita')
    serializer_class = FichaClinicaSerializer
    search_fields = ['mascota__nombre','motivo','diagnostico']
    filters = {'mascota':'mascota_id','veterinario':'veterinario_id'}

class VacunaViewSet(BaseViewSet):
    resource = 'vacunas'
    queryset = Vacuna.objects.select_related('mascota','veterinario')
    serializer_class = VacunaSerializer
    search_fields = ['nombre','mascota__nombre']
    filters = {'mascota':'mascota_id','veterinario':'veterinario_id'}
    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get('seguimiento') == 'vencidas':
            qs = qs.filter(seguimiento_cerrado=False,fecha_proxima_dosis__lt=timezone.localdate())
        elif self.request.query_params.get('seguimiento') == 'proximas':
            qs = qs.filter(seguimiento_cerrado=False,fecha_proxima_dosis__range=[timezone.localdate(),timezone.localdate()+timedelta(days=7)])
        return qs

class RecordatorioViewSet(BaseViewSet):
    resource = 'recordatorios'
    queryset = Recordatorio.objects.select_related('mascota__tutor','vacuna')
    serializer_class = RecordatorioSerializer
    search_fields = ['mensaje','mascota__nombre']
    filters = {'mascota':'mascota_id','estado':'estado','tipo':'tipo'}
    @action(detail=True,methods=['post'])
    def atender(self,request,pk=None):
        serializer = self.get_serializer(self.get_object(),data={'estado':'Atendido'},partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)

class UsuarioViewSet(BaseViewSet):
    resource = 'usuarios'
    queryset = get_user_model().objects.prefetch_related('groups').order_by('username')
    serializer_class = UsuarioSerializer
    search_fields = ['username','first_name','last_name']
    def perform_destroy(self,instance):
        raise PermissionDenied('Desactiva el usuario para conservar su historial; no se eliminan cuentas.')

@api_view(['GET','PATCH'])
@permission_classes([PetCarePermission])
def perfil(request):
    user = request.user
    if request.method == 'PATCH':
        allowed = {'first_name','last_name','email','password','current_password'}
        if set(request.data)-allowed:
            raise ValidationError('El perfil no permite modificar roles o privilegios.')
        password = request.data.get('password')
        if password:
            if not user.check_password(request.data.get('current_password','')):
                raise ValidationError({'current_password':'La contraseña actual no coincide.'})
            password_validation.validate_password(password,user)
            user.set_password(password)
        for field in ['first_name','last_name','email']:
            if field in request.data:
                setattr(user,field,request.data[field])
        user.full_clean(exclude=['password'])
        user.save()
        update_session_auth_hash(request,user)
    return Response({'id':user.pk,'username':user.username,'first_name':user.first_name,'last_name':user.last_name,
                     'email':user.email,'rol':role(user),'veterinario':vet_id(user),'hoy':timezone.localdate()})

@api_view(['GET'])
@permission_classes([PetCarePermission])
def dashboard(request):
    if role(request.user) == TUTOR:
        raise PermissionDenied('El resumen clínico es exclusivo del personal autorizado.')
    now = timezone.localtime()
    today = now.date()
    upcoming = Cita.objects.select_related('mascota__tutor','veterinario').filter(estado__in=['Pendiente','Confirmada']).filter(Q(fecha__gt=today)|Q(fecha=today,hora_inicio__gte=now.time().replace(tzinfo=None)))[:8]
    vaccines = Vacuna.objects.select_related('mascota','veterinario').filter(seguimiento_cerrado=False,fecha_proxima_dosis__lte=today+timedelta(days=7))[:6]
    activities = Actividad.objects.select_related('usuario')
    if role(request.user) != ADMIN:
        activities = activities.exclude(entidad__in=['usuarios','fichas']) if role(request.user) != VET else activities.exclude(entidad='usuarios')
    return Response({'citas_del_dia':CitaSerializer(Cita.objects.filter(fecha=today).exclude(estado='Cancelada').select_related('mascota__tutor','veterinario')[:30],many=True).data,
        'consultas_recientes':FichaClinicaSerializer(FichaClinica.objects.select_related('mascota','veterinario').all()[:6],many=True).data if role(request.user) in (ADMIN,VET) else [],
        'hoy':today,'tutores':Tutor.objects.count(),'mascotas':Mascota.objects.count(),
        'citas_hoy':Cita.objects.filter(fecha=today).exclude(estado='Cancelada').count(),
        'vacunas_pendientes':Vacuna.objects.filter(seguimiento_cerrado=False,fecha_proxima_dosis__lte=today+timedelta(days=7)).count(),
        'recordatorios_pendientes':Recordatorio.objects.filter(estado='Pendiente',fecha_programada__lte=today+timedelta(days=7)).count(),
        'proximas_citas':CitaSerializer(upcoming,many=True).data,'vacunas':VacunaSerializer(vaccines,many=True).data,
        'actividad':[{'accion':a.accion,'entidad':a.entidad,'fecha':a.fecha,'usuario':a.usuario.username if a.usuario else 'Sistema'} for a in activities[:8]]})
