from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models.deletion import ProtectedError
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

def exception_handler(exc,context):
    if isinstance(exc,ValidationError):
        return Response(getattr(exc,'message_dict',{'detail':exc.messages}),status=400)
    if isinstance(exc,ProtectedError):
        return Response({'detail':'El registro tiene información relacionada. Conserva su historial o elimina primero las dependencias permitidas.'},status=409)
    if isinstance(exc,IntegrityError):
        return Response({'detail':'La operación entra en conflicto con otro registro, un horario ocupado o una relación protegida.'},status=409)
    return drf_exception_handler(exc,context)
