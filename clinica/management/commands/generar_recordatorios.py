from django.conf import settings
from django.core.management.base import BaseCommand
from clinica.services import actualizar_recordatorios,enviar_recordatorios

class Command(BaseCommand):
    help = 'Genera/actualiza avisos sin duplicarlos y opcionalmente envía correos de los próximos 7 días.'
    def add_arguments(self,parser):
        parser.add_argument('--enviar',action='store_true')
    def handle(self,*args,**options):
        created = actualizar_recordatorios()
        self.stdout.write(f'Recordatorios nuevos: {created}.')
        if options['enviar']:
            if not settings.SMTP_CONFIGURED:
                self.stdout.write(self.style.WARNING('SMTP no configurado: se conservan los avisos dentro del sistema.'))
            else:
                self.stdout.write(f'Correos enviados: {enviar_recordatorios()}.')
