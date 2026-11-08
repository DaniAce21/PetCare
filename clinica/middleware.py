import hashlib
import logging
from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin
from .models import LoginWindow
from .permissions import role, ADMIN, VET

logger = logging.getLogger('petcare.security')

class SecurityGate(MiddlewareMixin):
    def process_view(self, request, view_func, view_args, view_kwargs):
        if request.path.startswith('/admin/') and request.user.is_authenticated:
            if role(request.user) not in (ADMIN,VET):
                return HttpResponse('Acceso reservado al personal autorizado.',status=403)
        sensitive = request.path in ('/login/','/admin/login/','/registro/','/recuperar/')
        if request.method != 'POST' or not sensitive:
            return None
        # REMOTE_ADDR solo se reemplaza si el par es el proxy local configurado.
        peer = request.META.get('REMOTE_ADDR','unknown')
        if peer in settings.TRUSTED_PROXY_IPS:
            peer = request.META.get('HTTP_X_REAL_IP',peer)
        keys = [hashlib.sha256((settings.SECRET_KEY+':ip:'+peer).encode()).hexdigest()]
        if request.path in ('/login/','/admin/login/'):
            username = request.POST.get('username','').strip().casefold()[:150]
            keys.append(hashlib.sha256((settings.SECRET_KEY+':account:'+username).encode()).hexdigest())
        now = timezone.now()
        blocked = False
        with transaction.atomic():
            for key in sorted(keys):
                obj, _ = LoginWindow.objects.get_or_create(key=key,defaults={'expires':now+timedelta(minutes=5)})
                obj = LoginWindow.objects.select_for_update().get(pk=obj.pk)
                if obj.expires <= now:
                    obj.attempts = 0
                    obj.expires = now+timedelta(minutes=5)
                if obj.attempts >= 10:
                    blocked = True
                else:
                    obj.attempts += 1
                    obj.save(update_fields=['attempts','expires'])
        if blocked:
            logger.warning('authentication_rate_limited')
            response = HttpResponse('Demasiados intentos. Espera 5 minutos antes de volver a intentarlo.',status=429)
            response['Retry-After'] = '300'
            return response
