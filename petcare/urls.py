from django.contrib import admin
from django.contrib.auth.views import LogoutView, PasswordResetView, PasswordResetDoneView, PasswordResetConfirmView, PasswordResetCompleteView
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from clinica import api, views
router = DefaultRouter()
for prefix,view in [('tutores',api.TutorViewSet),('mascotas',api.MascotaViewSet),
 ('veterinarios',api.VeterinarioViewSet),('disponibilidades',api.DisponibilidadViewSet),
 ('citas',api.CitaViewSet),('fichas',api.FichaClinicaViewSet),('vacunas',api.VacunaViewSet),
 ('recordatorios',api.RecordatorioViewSet),('usuarios',api.UsuarioViewSet)]:
    router.register(prefix,view,basename=prefix)
urlpatterns = [
 path('registro/',views.registro,name='registro'),
 path('mi-cuenta/',views.mi_cuenta,name='mi-cuenta'),
 path('mis-mascotas/',views.mascotas,name='mis-mascotas'),
 path('mis-mascotas/agregar/',views.mascota_editar,name='mascota-agregar'),
 path('mis-mascotas/<int:pk>/editar/',views.mascota_editar,name='mascota-editar'),
 path('mis-mascotas/<int:pk>/historial/',views.historial,name='historial'),
 path('mis-citas/',views.mis_citas,name='mis-citas'),
 path('reservar/',views.reservar,name='reservar'),
 path('cuidados/',views.cuidados,name='cuidados'),
 path('recuperar/',PasswordResetView.as_view(template_name='registration/reset_form.html'),name='password_reset'),
 path('recuperar/enviado/',PasswordResetDoneView.as_view(template_name='registration/reset_done.html'),name='password_reset_done'),
 path('recuperar/<uidb64>/<token>/',PasswordResetConfirmView.as_view(template_name='registration/reset_confirm.html'),name='password_reset_confirm'),
 path('recuperar/completo/',PasswordResetCompleteView.as_view(template_name='registration/reset_complete.html'),name='password_reset_complete'),path('admin/',admin.site.urls),path('login/',views.PetCareLoginView.as_view(),name='login'),
 path('logout/',LogoutView.as_view(),name='logout'),path('',views.inicio,name='inicio'),
 path('mascotas/<int:pk>/imprimir/',views.historial_imprimible,name='imprimir'),
 path('api/perfil/',api.perfil,name='perfil'),path('api/dashboard/',api.dashboard,name='dashboard'),
 path('api/',include(router.urls))]
