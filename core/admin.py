from django.contrib import admin
from .models import Usuario, Sucursal, Especialista, Servicio, Cita, Atencion, Comision, Auditoria

admin.site.register([Usuario, Sucursal, Especialista, Servicio, Cita, Atencion, Comision, Auditoria])