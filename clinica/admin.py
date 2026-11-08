from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.db import transaction
from .permissions import role, ADMIN, VET, PetCarePermission
from django.core.exceptions import PermissionDenied
from types import SimpleNamespace
from .models import Tutor,Mascota,Veterinario,Disponibilidad,Cita,FichaClinica,Vacuna,Recordatorio,Actividad

admin.site.site_header = 'PetCare · Administración veterinaria'
admin.site.site_title = 'PetCare Admin'
admin.site.index_title = 'Gestión clínica y configuración'

class AuditedAdmin(admin.ModelAdmin):
    def clinical_allowed(self, request, obj=None, method='GET'):
        if role(request.user) == ADMIN:
            return True
        if role(request.user) != VET:
            return False
        resources = {'fichaclinica':'fichas','vacuna':'vacunas','disponibilidad':'disponibilidades','tutor':'tutores','mascota':'mascotas','cita':'citas','recordatorio':'recordatorios','veterinario':'veterinarios'}
        view = SimpleNamespace(resource=resources.get(self.model._meta.model_name,''))
        req = SimpleNamespace(user=request.user,method=method)
        permission = PetCarePermission()
        return permission.has_permission(req,view) and (obj is None or permission.has_object_permission(req,view,obj))
    def has_view_permission(self,request,obj=None):
        return super().has_view_permission(request,obj) and self.clinical_allowed(request,obj)
    def has_add_permission(self,request):
        return super().has_add_permission(request) and self.clinical_allowed(request,method='POST')
    def has_change_permission(self,request,obj=None):
        return super().has_change_permission(request,obj) and self.clinical_allowed(request,obj,'PATCH')
    def has_delete_permission(self,request,obj=None):
        return super().has_delete_permission(request,obj) and self.clinical_allowed(request,obj,'DELETE')
    def formfield_for_foreignkey(self,db_field,request,**kwargs):
        if db_field.name == 'veterinario' and role(request.user) == VET:
            kwargs['queryset'] = Veterinario.objects.filter(usuario=request.user)
        return super().formfield_for_foreignkey(db_field,request,**kwargs)

    def save_model(self,request,obj,form,change):
        if not self.clinical_allowed(request,obj,'PATCH' if change else 'POST'):
            raise PermissionDenied('No puedes registrar información bajo otro profesional.')
        super().save_model(request,obj,form,change)
        Actividad.objects.create(usuario=request.user,accion='Actualizado desde Admin' if change else 'Creado desde Admin',entidad=obj._meta.verbose_name,objeto_id=obj.pk)
    def delete_model(self,request,obj):
        if not self.clinical_allowed(request,obj,'DELETE'):
            raise PermissionDenied('No puedes eliminar recursos de otro profesional.')
        Actividad.objects.create(usuario=request.user,accion='Eliminado desde Admin',entidad=obj._meta.verbose_name,objeto_id=obj.pk)
        obj.delete()
    @transaction.atomic
    def delete_queryset(self,request,queryset):
        # Respetar las validaciones de delete() de cada disponibilidad.
        for obj in queryset.order_by('pk'):
            self.delete_model(request,obj)

class MascotaInline(admin.TabularInline):
    model = Mascota
    extra = 0
    fields = ['nombre','especie','sexo','fecha_nacimiento','peso']
    show_change_link = True

class DisponibilidadInline(admin.TabularInline):
    model = Disponibilidad
    extra = 0

@admin.register(Tutor)
class TutorAdmin(AuditedAdmin):
    list_display = ['nombre','apellidos','rut','telefono','correo','fecha_registro']
    list_filter = ['fecha_registro']
    search_fields = ['nombre','apellidos','rut','correo']
    ordering = ['apellidos','nombre']
    readonly_fields = ['fecha_registro','usuario']
    fieldsets = [('Datos personales',{'fields':['nombre','apellidos','rut','telefono','correo','direccion']}),('Cuenta vinculada',{'fields':['usuario','fecha_registro']})]
    inlines = [MascotaInline]

@admin.register(Mascota)
class MascotaAdmin(AuditedAdmin):
    list_display = ['nombre','especie','raza','sexo','peso','tutor']
    list_filter = ['especie','sexo']
    search_fields = ['nombre','tutor__rut','tutor__nombre','tutor__apellidos']
    list_select_related = ['tutor']
    autocomplete_fields = ['tutor']
    ordering = ['nombre']

@admin.register(Veterinario)
class VeterinarioAdmin(AuditedAdmin):
    list_display = ['nombre','especialidad','usuario','activo']
    list_filter = ['activo','especialidad']
    search_fields = ['nombre','usuario__username']
    list_select_related = ['usuario']
    ordering = ['nombre']
    inlines = [DisponibilidadInline]

@admin.register(Disponibilidad)
class DisponibilidadAdmin(AuditedAdmin):
    list_display = ['veterinario','dia_semana','hora_inicio','hora_termino']
    list_filter = ['dia_semana','veterinario']
    search_fields = ['veterinario__nombre']
    list_select_related = ['veterinario']
    ordering = ['veterinario','dia_semana','hora_inicio']

@admin.register(Cita)
class CitaAdmin(AuditedAdmin):
    list_display = ['fecha','hora_inicio','hora_termino','mascota','veterinario','estado']
    list_filter = ['estado','fecha','veterinario']
    search_fields = ['mascota__nombre','mascota__tutor__rut','motivo']
    list_select_related = ['mascota','veterinario']
    autocomplete_fields = ['mascota','veterinario']
    readonly_fields = ['creada']
    date_hierarchy = 'fecha'
    ordering = ['-fecha','hora_inicio']

@admin.register(FichaClinica)
class FichaClinicaAdmin(AuditedAdmin):
    list_display = ['fecha_atencion','mascota','veterinario','motivo','actualizada']
    list_filter = ['fecha_atencion','veterinario']
    search_fields = ['mascota__nombre','motivo','diagnostico']
    list_select_related = ['mascota','veterinario','cita']
    autocomplete_fields = ['mascota','veterinario','cita']
    readonly_fields = ['actualizada']
    ordering = ['-fecha_atencion','-id']

@admin.register(Vacuna)
class VacunaAdmin(AuditedAdmin):
    list_display = ['nombre','mascota','veterinario','fecha_aplicacion','fecha_proxima_dosis','seguimiento_cerrado']
    list_filter = ['seguimiento_cerrado','fecha_proxima_dosis','veterinario']
    search_fields = ['nombre','mascota__nombre']
    list_select_related = ['mascota','veterinario']
    ordering = ['fecha_proxima_dosis']

@admin.register(Recordatorio)
class RecordatorioAdmin(AuditedAdmin):
    list_display = ['mascota','tipo','fecha_programada','estado','correo_enviado']
    list_filter = ['tipo','estado','fecha_programada']
    search_fields = ['mascota__nombre','mensaje']
    list_select_related = ['mascota','vacuna']
    readonly_fields = ['fecha_creacion','correo_enviado','error_envio']
    ordering = ['fecha_programada']

@admin.register(Actividad)
class ActividadAdmin(admin.ModelAdmin):
    list_display = ['fecha','usuario','accion','entidad','objeto_id']
    list_filter = ['entidad','accion']
    search_fields = ['usuario__username','accion','entidad']
    list_select_related = ['usuario']
    readonly_fields = ['fecha','usuario','accion','entidad','objeto_id']
    ordering = ['-fecha']
    def has_add_permission(self,request):
        return False
    def has_change_permission(self,request,obj=None):
        return False
    def has_delete_permission(self,request,obj=None):
        return False

class VeterinarioUsuarioInline(admin.StackedInline):
    model = Veterinario
    extra = 0
    max_num = 1
    verbose_name_plural = 'Perfil veterinario (asignar además el grupo Veterinario)'

admin.site.unregister(User)
@admin.register(User)
class PetCareUserAdmin(UserAdmin):
    def has_module_permission(self,request):
        return role(request.user) == ADMIN and super().has_module_permission(request)
    def has_view_permission(self,request,obj=None):
        return role(request.user) == ADMIN and super().has_view_permission(request,obj)
    def has_add_permission(self,request):
        return role(request.user) == ADMIN and super().has_add_permission(request)
    def has_change_permission(self,request,obj=None):
        return role(request.user) == ADMIN and super().has_change_permission(request,obj)
    def has_delete_permission(self,request,obj=None):
        return role(request.user) == ADMIN and super().has_delete_permission(request,obj)

    list_display = ['username','first_name','last_name','email','is_active','is_staff']
    list_filter = ['groups','is_active','is_staff','is_superuser']
    search_fields = ['username','first_name','last_name','email']
    ordering = ['username']
    readonly_fields = ['last_login','date_joined']
    inlines = [VeterinarioUsuarioInline]

from django.contrib.auth.models import Group
from django.contrib.auth.admin import GroupAdmin
admin.site.unregister(Group)
@admin.register(Group)
class PetCareGroupAdmin(GroupAdmin):
    def has_module_permission(self,request):
        return role(request.user) == ADMIN and super().has_module_permission(request)
    def has_view_permission(self,request,obj=None):
        return role(request.user) == ADMIN and super().has_view_permission(request,obj)
    def has_add_permission(self,request):
        return role(request.user) == ADMIN and super().has_add_permission(request)
    def has_change_permission(self,request,obj=None):
        return role(request.user) == ADMIN and super().has_change_permission(request,obj)
    def has_delete_permission(self,request,obj=None):
        return role(request.user) == ADMIN and super().has_delete_permission(request,obj)
