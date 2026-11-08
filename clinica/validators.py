import re
from django.core.exceptions import ValidationError
from django.utils import timezone

def normalizar_rut(value):
    value = str(value).upper().replace('.', '').replace(' ', '').replace('-', '')
    if not re.fullmatch(r'\d{7,8}[\dK]', value):
        raise ValidationError('Ingresa un RUT válido, por ejemplo 12.345.678-5.')
    body, digit = value[:-1], value[-1]
    total = sum(int(n) * (2 + i % 6) for i, n in enumerate(reversed(body)))
    result = 11 - total % 11
    expected = '0' if result == 11 else 'K' if result == 10 else str(result)
    if digit != expected or int(body) == 0:
        raise ValidationError('El dígito verificador del RUT no es válido.')
    return f'{int(body)}-{digit}'

def validar_rut(value):
    normalizar_rut(value)

def validar_telefono(value):
    if not re.fullmatch(r'\+?[\d ()-]{8,24}', value) or len(re.sub(r'\D','',value)) < 8:
        raise ValidationError('Ingresa un teléfono válido de al menos 8 dígitos.')

def no_futura(value):
    if value > timezone.localdate():
        raise ValidationError('La fecha no puede ser futura.')
