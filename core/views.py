from django.db import transaction
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Sucursal, Especialista, Servicio, Cita, Atencion, Comision, Auditoria
from .serializers import (
    SucursalSerializer, EspecialistaSerializer, ServicioSerializer,
    CitaSerializer, AtencionSerializer, ComisionSerializer
)

SUCURSALES_VECINAS = {
    'Providencia': 'Vitacura',
    'Vitacura': 'Providencia',
    'Las Condes': 'Lo Barnechea',
    'Lo Barnechea': 'Las Condes',
}


class SucursalViewSet(viewsets.ModelViewSet):
    queryset = Sucursal.objects.filter(activa=True)
    serializer_class = SucursalSerializer


class EspecialistaViewSet(viewsets.ModelViewSet):
    queryset = Especialista.objects.select_related('usuario', 'sucursal').all()
    serializer_class = EspecialistaSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        sucursal_id = self.request.query_params.get('sucursal')
        if sucursal_id:
            qs = qs.filter(sucursal_id=sucursal_id)
        return qs


class ServicioViewSet(viewsets.ModelViewSet):
    queryset = Servicio.objects.filter(activo=True)
    serializer_class = ServicioSerializer


class CitaViewSet(viewsets.ModelViewSet):
    queryset = Cita.objects.select_related('especialista__usuario', 'sucursal', 'servicio').all().order_by('fecha_hora')
    serializer_class = CitaSerializer

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        especialista = serializer.validated_data['especialista']
        fecha_hora = serializer.validated_data['fecha_hora']
        sucursal = serializer.validated_data['sucursal']

        # Bloqueo atómico para evitar doble reserva simultánea (RNF-04)
        conflicto = Cita.objects.select_for_update().filter(
            especialista=especialista,
            fecha_hora=fecha_hora
        ).exclude(estado='CANCELADA').exists()

        if conflicto:
            comuna_vecina = SUCURSALES_VECINAS.get(sucursal.comuna)
            alternativas = []
            if comuna_vecina:
                esps_vecinos = Especialista.objects.filter(sucursal__comuna=comuna_vecina)
                for esp in esps_vecinos:
                    ocupado = Cita.objects.filter(
                        especialista=esp, fecha_hora=fecha_hora
                    ).exclude(estado='CANCELADA').exists()
                    if not ocupado:
                        alternativas.append({
                            'especialista_id': esp.id,
                            'especialista': esp.usuario.get_full_name(),
                            'sucursal_id': esp.sucursal.id,
                            'sucursal': f"{esp.sucursal.comuna} — {esp.sucursal.nombre}",
                            'fecha_hora': fecha_hora
                        })

            return Response({
                'error': 'El bloque horario ya no está disponible en esta sucursal.',
                'sugerencia_sucursal_cercana': alternativas
            }, status=status.HTTP_409_CONFLICT)

        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def confirmar(self, request, pk=None):
        cita = self.get_object()
        cita.estado = 'CONFIRMADA'
        cita.save()
        return Response({'status': 'Cita confirmada correctamente'})

    @action(detail=True, methods=['post'])
    def cancelar(self, request, pk=None):
        cita = self.get_object()
        cita.estado = 'CANCELADA'
        cita.save()
        return Response({'status': 'Cita cancelada y bloque liberado'})


class AtencionViewSet(viewsets.ModelViewSet):
    queryset = Atencion.objects.all()
    serializer_class = AtencionSerializer


class ComisionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Comision.objects.select_related('especialista__usuario', 'atencion').all()
    serializer_class = ComisionSerializer