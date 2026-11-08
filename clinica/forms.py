from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction
from .models import Tutor, Mascota

class RegistroForm(UserCreationForm):
    nombre = forms.CharField(max_length=100)
    apellidos = forms.CharField(max_length=150)
    rut = forms.CharField(max_length=12)
    telefono = forms.CharField(max_length=24)
    correo = forms.EmailField()
    direccion = forms.CharField(max_length=250)
    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ('username','nombre','apellidos','rut','telefono','correo','direccion')
    def clean(self):
        data = super().clean()
        profile = Tutor(**{k:data.get(k,'') for k in ('nombre','apellidos','rut','telefono','correo','direccion')})
        try:
            profile.full_clean(exclude=['usuario'])
        except forms.ValidationError as exc:
            for key, errors in exc.message_dict.items():
                self.add_error(key if key in self.fields else None,errors)
        return data
    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        user.first_name = self.cleaned_data['nombre']
        user.last_name = self.cleaned_data['apellidos']
        user.email = self.cleaned_data['correo']
        user.is_staff = user.is_superuser = False
        user.save()
        user.groups.add(Group.objects.get_or_create(name='Tutor')[0])
        Tutor.objects.create(usuario=user,**{k:self.cleaned_data[k] for k in ('nombre','apellidos','rut','telefono','correo','direccion')})
        return user

class CuentaForm(forms.ModelForm):
    class Meta:
        model = Tutor
        fields = ['nombre','apellidos','telefono','correo','direccion']

class MascotaForm(forms.ModelForm):
    class Meta:
        model = Mascota
        fields = ['nombre','especie','raza','sexo','fecha_nacimiento','peso','observaciones']
        widgets = {'fecha_nacimiento':forms.DateInput(attrs={'type':'date'},format='%Y-%m-%d')}
