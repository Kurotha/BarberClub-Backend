from rest_framework import serializers
from django.db import IntegrityError
from django.utils import timezone
from .models import Usuario, Sucursal, Especialista, Servicio, Cita, Atencion, Comision, Auditoria


class SucursalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sucursal
        fields = '__all__'


class EspecialistaSerializer(serializers.ModelSerializer):
    nombre_completo = serializers.CharField(source='usuario.get_full_name', read_only=True)
    sucursal_nombre = serializers.CharField(source='sucursal.nombre', read_only=True)
    sucursal_comuna = serializers.CharField(source='sucursal.comuna', read_only=True)

    class Meta:
        model = Especialista
        fields = [
            'id', 'nombre_completo', 'sucursal', 'sucursal_nombre',
            'sucursal_comuna', 'especialidad', 'biografia', 'anos_experiencia'
        ]


class ServicioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Servicio
        fields = '__all__'


class CitaSerializer(serializers.ModelSerializer):
    especialista_nombre = serializers.CharField(source='especialista.usuario.get_full_name', read_only=True)
    sucursal_nombre = serializers.CharField(source='sucursal.nombre', read_only=True)
    servicio_nombre = serializers.CharField(source='servicio.nombre', read_only=True)
    duracion_minutos = serializers.IntegerField(source='servicio.duracion_minutos', read_only=True)

    class Meta:
        model = Cita
        validators = []
        fields = [
            'id', 'cliente_nombre', 'cliente_telefono', 'cliente_correo',
            'especialista', 'especialista_nombre', 'sucursal', 'sucursal_nombre',
            'servicio', 'servicio_nombre', 'duracion_minutos', 'fecha_hora',
            'estado', 'es_walk_in', 'consentimiento_aceptado', 'version_politica'
        ]
        read_only_fields = ['estado']

    def validate_consentimiento_aceptado(self, value):
        if not value:
            raise serializers.ValidationError(
                "Debe aceptar expresamente el tratamiento de datos personales conforme a la Ley N.° 21.719."
            )
        return value

    def validate_cliente_nombre(self, value):
        value = ' '.join(value.split())
        if len(value) < 3:
            raise serializers.ValidationError('Ingrese un nombre válido.')
        if not all(char.isalpha() or char.isspace() for char in value):
            raise serializers.ValidationError('El nombre debe contener solo letras.')
        return value

    def validate_cliente_telefono(self, value):
        import re
        if not re.fullmatch(r'\+569[0-9]{8}', value):
            raise serializers.ValidationError(
                'Ingrese un teléfono chileno con el formato +569 seguido de 8 dígitos.'
            )
        return value.strip()

    def validate_fecha_hora(self, value):
        if value <= timezone.now():
            raise serializers.ValidationError('La fecha y hora deben ser futuras.')
        return value

    def create(self, validated_data):
        try:
            return super().create(validated_data)
        except IntegrityError:
            raise


class AtencionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Atencion
        fields = ['id', 'cita', 'monto_cobrado', 'observacion', 'fecha_cierre']

    def create(self, validated_data):
        atencion = super().create(validated_data)
        cita = atencion.cita
        cita.estado = 'ATENDIDA'
        cita.save()

        # Cálculo automático 1 a 1 de comisión (HU-02 / RF-06)
        porcentaje = cita.especialista.porcentaje_comision
        monto_comision = round((atencion.monto_cobrado * porcentaje) / 100)
        Comision.objects.create(
            atencion=atencion,
            especialista=cita.especialista,
            porcentaje_aplicado=porcentaje,
            monto_comision=monto_comision
        )
        return atencion


class ComisionSerializer(serializers.ModelSerializer):
    especialista_nombre = serializers.CharField(source='especialista.usuario.get_full_name', read_only=True)

    class Meta:
        model = Comision
        fields = ['id', 'atencion', 'especialista', 'especialista_nombre', 'porcentaje_aplicado', 'monto_comision', 'fecha_calculo']