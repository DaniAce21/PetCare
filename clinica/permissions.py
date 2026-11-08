from rest_framework.permissions import BasePermission, SAFE_METHODS

TUTOR = 'Tutor'
ADMIN = 'Administrador'
VET = 'Veterinario'
RECEPTION = 'Recepcionista'

def role(user):
    if not user.is_authenticated or not user.is_active:
        return None
    if user.is_superuser or user.groups.filter(name=ADMIN).exists():
        return ADMIN
    if user.groups.filter(name=VET).exists() and hasattr(user,'veterinario') and user.veterinario.activo:
        return VET
    if user.groups.filter(name=RECEPTION).exists():
        return RECEPTION
    if user.groups.filter(name=TUTOR).exists() and hasattr(user, 'tutor'):
        return TUTOR
    return None

def vet_id(user):
    return user.veterinario.pk if hasattr(user,'veterinario') else None

class PetCarePermission(BasePermission):
    message = 'Tu rol no permite realizar esta acción.'
    def has_permission(self,request,view):
        user_role = role(request.user)
        if not user_role:
            return False
        resource = getattr(view,'resource','')
        if user_role == TUTOR:
            if request.method in SAFE_METHODS:
                return resource != 'usuarios'
            return (resource == 'mascotas' and request.method in ('POST','PUT','PATCH')) or (resource == 'citas' and (request.method == 'POST' or getattr(view,'action','') == 'partial_update'))
        if user_role == ADMIN:
            return True
        if resource == 'usuarios':
            return False
        if resource == 'fichas':
            return user_role == VET and request.method != 'DELETE'
        if request.method in SAFE_METHODS:
            return True
        if request.method == 'DELETE' and resource in ('citas','fichas','vacunas','recordatorios'):
            return False
        if resource == 'vacunas':
            return user_role == VET
        if resource == 'veterinarios':
            return False
        if resource == 'disponibilidades':
            return user_role == VET
        if request.method == 'DELETE' and resource in ('citas','fichas','vacunas','recordatorios'):
            return False
        return True
    def has_object_permission(self,request,view,obj):
        if role(request.user) == TUTOR:
            if getattr(view,'resource','') in ('veterinarios','disponibilidades'):
                return request.method in SAFE_METHODS
            owner = obj if getattr(view,'resource','') == 'tutores' else getattr(obj,'tutor',None) if getattr(view,'resource','') == 'mascotas' else getattr(getattr(obj,'mascota',None),'tutor',None)
            return owner is not None and owner.usuario_id == request.user.pk
        if role(request.user) == ADMIN or request.method in SAFE_METHODS:
            return True
        if getattr(view,'resource','') in ('fichas','vacunas','disponibilidades'):
            return obj.veterinario_id == vet_id(request.user)
        return True
