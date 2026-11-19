from django.db import models
from django.contrib.auth.models import AbstractUser


class Usuario(AbstractUser):
    ROLES = (
        ('CLIENTE', 'Cliente'),
        ('BARBERO', 'Especialista / Barbero'),
        ('RECEPCION', 'Recepción / Mostrador'),
        ('ADMIN', 'Administrador / Dueño'),
    )
    telefono = models.CharField(max_length=20, blank=True)
    rol = models.CharField(max_length=15, choices=ROLES, default='CLIENTE')

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.rol})"


class Sucursal(models.Model):
    nombre = models.CharField(max_length=100)  # Ej: Las Condes — El Golf
    direccion = models.CharField(max_length=200)
    comuna = models.CharField(max_length=80)
    activa = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.comuna} — {self.nombre}"


class Especialista(models.Model):
    usuario = models.OneToOneField(Usuario, on_delete=models.PROTECT, related_name='perfil_especialista')
    sucursal = models.ForeignKey(Sucursal, on_delete=models.PROTECT, related_name='especialistas')
    especialidad = models.CharField(max_length=120)
    biografia = models.TextField(blank=True)
    anos_experiencia = models.PositiveIntegerField(default=1)
    porcentaje_comision = models.DecimalField(max_digits=5, decimal_places=2, default=50.00)

    def __str__(self):
        return f"{self.usuario.get_full_name()} ({self.sucursal.comuna})"


class Servicio(models.Model):
    nombre = models.CharField(max_length=100)  # Ej: Corte Clásico (30m), Corte y Barba (60m)
    duracion_minutos = models.PositiveIntegerField(default=30)
    precio = models.PositiveIntegerField()
    activo = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.nombre} ({self.duracion_minutos} min - ${self.precio})"


class Cita(models.Model):
    ESTADOS = (
        ('PENDIENTE', 'Pendiente'),
        ('CONFIRMADA', 'Confirmada'),
        ('CANCELADA', 'Cancelada'),
        ('ATENDIDA', 'Atendida'),
        ('NO_SHOW', 'No-Show'),
    )
    cliente_nombre = models.CharField(max_length=120)
    cliente_telefono = models.CharField(max_length=20)
    cliente_correo = models.EmailField()
    especialista = models.ForeignKey(Especialista, on_delete=models.PROTECT, related_name='citas')
    sucursal = models.ForeignKey(Sucursal, on_delete=models.PROTECT, related_name='citas')
    servicio = models.ForeignKey(Servicio, on_delete=models.PROTECT, related_name='citas')
    fecha_hora = models.DateTimeField()
    estado = models.CharField(max_length=15, choices=ESTADOS, default='PENDIENTE')
    es_walk_in = models.BooleanField(default=False)

    # Cumplimiento Ley N° 21.719 (HU-09)
    consentimiento_aceptado = models.BooleanField(default=False)
    fecha_consentimiento = models.DateTimeField(auto_now_add=True)
    version_politica = models.CharField(max_length=20, default='v1.0-2026')

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['especialista', 'fecha_hora'],
                condition=~models.Q(estado='CANCELADA'),
                name='unique_bloque_activo_especialista'
            )
        ]

    def __str__(self):
        return f"Cita #{self.id} - {self.cliente_nombre} con {self.especialista}"


class Atencion(models.Model):
    cita = models.OneToOneField(Cita, on_delete=models.PROTECT, related_name='atencion')
    monto_cobrado = models.PositiveIntegerField()
    observacion = models.TextField(blank=True)
    fecha_cierre = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Atención Cita #{self.cita.id} - ${self.monto_cobrado}"


class Comision(models.Model):
    atencion = models.OneToOneField(Atencion, on_delete=models.PROTECT, related_name='comision')
    especialista = models.ForeignKey(Especialista, on_delete=models.PROTECT, related_name='comisiones')
    porcentaje_aplicado = models.DecimalField(max_digits=5, decimal_places=2)
    monto_comision = models.PositiveIntegerField()
    fecha_calculo = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Comisión {self.especialista} - ${self.monto_comision}"


class Auditoria(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True)
    accion = models.CharField(max_length=120)
    motivo = models.TextField()
    metadata_json = models.JSONField(default=dict, blank=True)
    fecha = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.fecha:%Y-%m-%d %H:%M}] {self.accion}"