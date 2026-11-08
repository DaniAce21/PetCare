from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from clinica.models import LoginWindow
class Command(BaseCommand):
    help = 'Elimina únicamente contadores de autenticación expirados hace más de un día.'
    def handle(self,*args,**options):
        deleted,_=LoginWindow.objects.filter(expires__lt=timezone.now()-timedelta(days=1)).delete()
        self.stdout.write(f'Contadores antiguos eliminados: {deleted}')
