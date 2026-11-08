from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.exceptions import PermissionDenied
from django.shortcuts import render, get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from .models import Mascota
from .permissions import role, ADMIN, VET

@method_decorator(never_cache,name='dispatch')
class PetCareLoginView(LoginView):
    template_name = 'registration/login.html'
    redirect_authenticated_user = True

@login_required
@never_cache
def inicio(request):
    if not role(request.user):
        raise PermissionDenied('Tu cuenta no tiene un rol activo. Contacta a administración.')
    if role(request.user) == 'Tutor':
        return render(request,'portal/inicio.html')
    return render(request,'clinica/app.html',{'rol':role(request.user)})

@login_required
@never_cache
def historial_imprimible(request,pk):
    if role(request.user) not in (ADMIN,VET):
        raise PermissionDenied('Las fichas clínicas están restringidas al personal clínico.')
    mascota = get_object_or_404(Mascota.objects.select_related('tutor'),pk=pk)
    return render(request,'clinica/imprimir.html',{'mascota':mascota,
       'fichas':mascota.fichas.select_related('veterinario','cita'),
       'vacunas':mascota.vacunas.select_related('veterinario')})

def csrf_failure(request,reason=''):
    return render(request,'403.html',status=403)

from datetime import datetime, timedelta, date
from django import forms
from django.contrib import messages
from django.contrib.auth import login
from django.db import transaction, IntegrityError
from django.core.exceptions import ValidationError
from django.shortcuts import redirect
from django.utils import timezone
from .forms import RegistroForm, CuentaForm, MascotaForm
from .models import Tutor, Veterinario, Disponibilidad, Cita, Vacuna, Recordatorio
from .permissions import TUTOR

@never_cache
def registro(request):
    if request.user.is_authenticated:
        return redirect('inicio')
    form = RegistroForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            user = form.save()
        except (ValidationError, IntegrityError):
            form.add_error(None,'No fue posible crear la cuenta con estos datos. Revisa los campos o recupera tu acceso.')
        else:
            login(request,user)
            return redirect('inicio')
    return render(request,'portal/form.html',{'form':form,'titulo':'Crear mi cuenta','boton':'Registrarme'})

def tutor_actual(request):
    if role(request.user) != TUTOR:
        raise PermissionDenied('Esta sección corresponde al portal de tutores.')
    return request.user.tutor

@login_required
@never_cache
def mi_cuenta(request):
    tutor = tutor_actual(request)
    form = CuentaForm(request.POST or None,instance=tutor)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            form.save()
            user = request.user
            user.first_name, user.last_name, user.email = tutor.nombre,tutor.apellidos,tutor.correo
            user.save(update_fields=['first_name','last_name','email'])
        messages.success(request,'Tus datos se guardaron.')
        return redirect('mi-cuenta')
    return render(request,'portal/form.html',{'form':form,'titulo':'Mi cuenta','boton':'Guardar datos'})

@login_required
@never_cache
def mascotas(request):
    tutor = tutor_actual(request)
    pets = tutor.mascotas.prefetch_related('vacunas')
    for pet in pets:
        pet.edad = max(0,(timezone.localdate()-pet.fecha_nacimiento).days//365)
        pet.proxima = pet.vacunas.filter(seguimiento_cerrado=False).first()
    return render(request,'portal/mascotas.html',{'mascotas':pets})

@login_required
@never_cache
def mascota_editar(request,pk=None):
    tutor = tutor_actual(request)
    instance = get_object_or_404(tutor.mascotas,pk=pk) if pk else Mascota(tutor=tutor)
    form = MascotaForm(request.POST or None,instance=instance)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request,'La información de tu mascota se guardó.')
        return redirect('mis-mascotas')
    return render(request,'portal/form.html',{'form':form,'titulo':'Editar mascota' if pk else 'Agregar mascota','boton':'Guardar mascota'})

@login_required
@never_cache
def mis_citas(request):
    tutor = tutor_actual(request)
    if request.method == 'POST':
        from .serializers import CitaSerializer
        if not str(request.POST.get('cita','')).isdigit():
            return render(request,'400.html',status=400)
        cita = get_object_or_404(Cita,pk=request.POST.get('cita'),mascota__tutor=tutor)
        serializer = CitaSerializer(cita,data={'estado':'Cancelada'},partial=True,context={'request':request})
        if serializer.is_valid():
            try:
                serializer.save()
                messages.success(request,'Tu cita fue cancelada.')
            except (ValidationError,IntegrityError):
                messages.error(request,'No fue posible cancelar esta atención.')
        else:
            messages.error(request,'Solo puedes cancelar reservas pendientes o confirmadas antes de su inicio.')
        return redirect('mis-citas')
    upcoming, previous = [], []
    for cita in Cita.objects.filter(mascota__tutor=tutor).select_related('mascota','veterinario'):
        future = timezone.make_aware(datetime.combine(cita.fecha,cita.hora_inicio)) > timezone.now()
        cita.cancelable = future and cita.estado in ('Pendiente','Confirmada')
        (upcoming if cita.cancelable else previous).append(cita)
    return render(request,'portal/citas.html',{'grupos_citas':[('Próximas citas',upcoming),('Citas anteriores y canceladas',list(reversed(previous)))]})

@login_required
@never_cache
def cuidados(request):
    tutor = tutor_actual(request)
    return render(request,'portal/cuidados.html',{'vacunas':Vacuna.objects.filter(mascota__tutor=tutor).select_related('mascota'),'recordatorios':Recordatorio.objects.filter(mascota__tutor=tutor).select_related('mascota'),'hoy':timezone.localdate()})

@login_required
@never_cache
def historial(request,pk):
    tutor = tutor_actual(request)
    pet = get_object_or_404(tutor.mascotas,pk=pk)
    return render(request,'portal/historial.html',{'mascota':pet,'fichas':pet.fichas.select_related('veterinario')})

def horarios(vet,pet,day):
    slots = []
    if not vet or not pet or day < timezone.localdate() or day > timezone.localdate()+timedelta(days=180):
        return slots
    for window in Disponibilidad.objects.filter(veterinario=vet,dia_semana=day.weekday()):
        start = datetime.combine(day,window.hora_inicio)
        end = datetime.combine(day,window.hora_termino)
        while start+timedelta(minutes=30) <= end:
            finish = start+timedelta(minutes=30)
            from django.db.models import Q
            occupied = Cita.objects.filter(Q(veterinario=vet)|Q(mascota=pet),fecha=day,hora_inicio__lt=finish.time(),hora_termino__gt=start.time()).exclude(estado='Cancelada').exists()
            if not occupied and timezone.make_aware(start)>timezone.now():
                slots.append(start.strftime('%H:%M'))
            start = finish
    return sorted(set(slots))

@login_required
@never_cache
def reservar(request):
    tutor = tutor_actual(request)
    data = request.POST if request.method == 'POST' else request.GET
    pet = tutor.mascotas.filter(pk=data.get('mascota')).first() if str(data.get('mascota','')).isdigit() else None
    vet = Veterinario.objects.filter(pk=data.get('veterinario'),activo=True,usuario__is_active=True).first() if str(data.get('veterinario','')).isdigit() else None
    try:
        day = date.fromisoformat(data.get('fecha',''))
    except ValueError:
        day = None
    slots = horarios(vet,pet,day) if day else []
    chosen = data.get('hora','')
    if request.method == 'POST':
        if day and day < timezone.localdate():
            messages.error(request,'No puedes reservar citas en fechas pasadas.')
        elif chosen not in slots or not data.get('motivo','').strip() or len(data.get('motivo',''))>500:
            messages.error(request,'Revisa los datos. El horario puede haberse ocupado; selecciona uno disponible.')
        else:
            try:
                start = datetime.combine(day,datetime.strptime(chosen,'%H:%M').time())
                with transaction.atomic():
                    Veterinario.objects.select_for_update().get(pk=vet.pk)
                    pet = Mascota.objects.select_for_update().filter(pk=pet.pk,tutor=tutor).first()
                    if not pet:
                        raise ValidationError('La mascota ya no pertenece a tu cuenta.')
                    Cita.objects.create(mascota=pet,veterinario=vet,fecha=day,hora_inicio=start.time(),hora_termino=(start+timedelta(minutes=30)).time(),motivo=data['motivo'].strip())
            except (ValidationError,IntegrityError):
                messages.error(request,'Ese horario ya no está disponible. Selecciona otro.')
            else:
                messages.success(request,'¡Reserva solicitada! Puedes revisar su estado en Mis citas.')
                return redirect('mis-citas')
    return render(request,'portal/reservar.html',{'mascotas':tutor.mascotas.all(),'veterinarios':Veterinario.objects.filter(activo=True,usuario__is_active=True),'pet':pet,'vet':vet,'fecha':day,'horarios':slots,'hora':chosen,'hoy':timezone.localdate()})
