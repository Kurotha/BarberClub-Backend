from django.db import transaction, IntegrityError
from datetime import datetime, timedelta
from django.views.decorators.csrf import ensure_csrf_cookie
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.throttling import AnonRateThrottle
from rest_framework.response import Response
from rest_framework.generics import ListAPIView
from .models import Sucursal, Especialista, Servicio, Cita, Atencion, Comision, Auditoria, Usuario
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


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([AnonRateThrottle])
def auth_register(request):
    if request.method != 'POST':
        return Response({'detail': 'Método no permitido.'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)
    username = str(request.data.get('username', '')).strip()
    email = str(request.data.get('email', '')).strip().lower()
    password = str(request.data.get('password', ''))
    first_name = str(request.data.get('first_name', '')).strip()
    telefono = str(request.data.get('telefono', '')).strip()
    if not username or not email or not password:
        return Response({'detail': 'Usuario, correo y contraseña son obligatorios.'}, status=status.HTTP_400_BAD_REQUEST)
    if len(first_name) < 3 or not all(char.isalpha() or char.isspace() for char in first_name):
        return Response({'detail': 'El nombre completo debe contener solo letras y tener al menos 3 caracteres.'}, status=status.HTTP_400_BAD_REQUEST)
    import re
    if telefono and not re.fullmatch(r'\+569[0-9]{8}', telefono):
        return Response({'detail': 'El teléfono debe usar el formato chileno +569 seguido de 8 dígitos.'}, status=status.HTTP_400_BAD_REQUEST)
    if Usuario.objects.filter(username=username).exists():
        return Response({'detail': 'El usuario ya existe.'}, status=status.HTTP_409_CONFLICT)
    if Usuario.objects.filter(email=email).exists():
        return Response({'detail': 'El correo ya está registrado.'}, status=status.HTTP_409_CONFLICT)
    usuario = Usuario(username=username, email=email, first_name=first_name, telefono=telefono, rol='CLIENTE')
    try:
        validate_password(password, usuario)
    except DjangoValidationError as exc:
        return Response({'detail': exc.messages}, status=status.HTTP_400_BAD_REQUEST)
    usuario.set_password(password)
    usuario.save()
    login(request, usuario)
    return Response(auth_user_data(usuario), status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([AnonRateThrottle])
def auth_login(request):
    if request.method != 'POST':
        return Response({'detail': 'Método no permitido.'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)
    usuario = authenticate(
        request,
        username=str(request.data.get('username', '')).strip(),
        password=str(request.data.get('password', '')),
    )
    if usuario is None:
        return Response({'detail': 'Credenciales inválidas.'}, status=status.HTTP_401_UNAUTHORIZED)
    login(request, usuario)
    return Response(auth_user_data(usuario))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def auth_logout(request):
    if request.method != 'POST':
        return Response({'detail': 'Método no permitido.'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)
    logout(request)
    return Response({'detail': 'Sesión cerrada.'})


@api_view(['GET'])
@permission_classes([AllowAny])
@ensure_csrf_cookie
def auth_me(request):
    if not request.user.is_authenticated:
        return Response({'authenticated': False}, status=status.HTTP_200_OK)
    return Response({'authenticated': True, **auth_user_data(request.user)})


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([AnonRateThrottle])
def password_reset_request(request):
    email = str(request.data.get('email', '')).strip().lower()
    if not email:
        return Response({'detail': 'Ingrese el correo electrónico.'}, status=status.HTTP_400_BAD_REQUEST)

    usuario = Usuario.objects.filter(email__iexact=email, is_active=True).first()
    if usuario:
        token = PasswordResetTokenGenerator().make_token(usuario)
        uid = urlsafe_base64_encode(force_bytes(usuario.pk))
        frontend_url = str(request.data.get('frontend_url', 'http://127.0.0.1:5173')).rstrip('/')
        reset_url = f"{frontend_url}/?reset=1&uid={uid}&token={token}"
        send_mail(
            subject='Restablecer contraseña - BarberClub',
            message=(
                'Solicitaste restablecer tu contraseña de BarberClub.\n\n'
                f'Abre este enlace: {reset_url}\n\n'
                'Si no solicitaste este cambio, puedes ignorar el correo.'
            ),
            from_email='no-reply@barberclub.cl',
            recipient_list=[usuario.email],
            fail_silently=False,
        )
    return Response({
        'detail': 'Si el correo existe, recibirás un enlace para restablecer la contraseña.'
    })


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([AnonRateThrottle])
def password_reset_confirm(request):
    uid = str(request.data.get('uid', '')).strip()
    token = str(request.data.get('token', '')).strip()
    password = str(request.data.get('password', ''))
    try:
        user_id = urlsafe_base64_decode(uid).decode()
        usuario = Usuario.objects.get(pk=user_id)
    except (Usuario.DoesNotExist, ValueError, TypeError, OverflowError):
        return Response({'detail': 'El enlace no es válido.'}, status=status.HTTP_400_BAD_REQUEST)

    if not PasswordResetTokenGenerator().check_token(usuario, token):
        return Response({'detail': 'El enlace expiró o ya fue utilizado.'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        validate_password(password, usuario)
    except DjangoValidationError as exc:
        return Response({'detail': exc.messages}, status=status.HTTP_400_BAD_REQUEST)
    usuario.set_password(password)
    usuario.save(update_fields=['password'])
    return Response({'detail': 'Contraseña restablecida correctamente.'})


def auth_user_data(usuario):
    return {
        'id': usuario.id,
        'username': usuario.username,
        'email': usuario.email,
        'first_name': usuario.first_name,
        'telefono': usuario.telefono,
        'rol': usuario.rol,
    }


class SucursalViewSet(viewsets.ModelViewSet):
    queryset = Sucursal.objects.all()
    serializer_class = SucursalSerializer

    @action(detail=False, methods=['get'])
    def active(self, request):
        Sucursales = Sucursal.objects.filter(
            activa = True
        )

        serializer = self.get_serializer(
            Sucursales,
            many = True
        )
        return Response(serializer.data)


class EspecialistaViewSet(viewsets.ModelViewSet):
    queryset = Especialista.objects.select_related('usuario', 'sucursal').all()
    serializer_class = EspecialistaSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        sucursal_id = self.request.query_params.get('sucursal')
        if sucursal_id:
            qs = qs.filter(sucursal_id=sucursal_id)
        return qs

    @action(detail=False, methods=['get'])
    def active(self, request):
        especialistas = Especialista.objects.filter(
            activo = True
        )

        serializer = self.get_serializer(
            especialistas,
            many = True
        )

        return Response(serializer.data)


class ServicioViewSet(viewsets.ModelViewSet):
    queryset = Servicio.objects.all()
    serializer_class = ServicioSerializer

    @action(detail=False, methods=['get'])
    def active(self, request):
        servicios = Servicio.objects.filter(
            activo=True
        )

        serializer = self.get_serializer(
            servicios,
            many=True
        )
        return Response(serializer.data)



class CitaViewSet(viewsets.ModelViewSet):
    queryset = Cita.objects.select_related('especialista__usuario', 'sucursal', 'servicio').all().order_by('fecha_hora')
    serializer_class = CitaSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_authenticated:
            return qs.none()
        if self.request.user.rol in ('ADMIN', 'RECEPCION'):
            return qs
        if self.request.user.rol == 'BARBERO':
            return qs.filter(especialista__usuario=self.request.user)
        return qs.filter(cliente_correo=self.request.user.email)

    def perform_create(self, serializer):
        cita = serializer.save()
        Auditoria.objects.create(
            usuario=self.request.user if self.request.user.is_authenticated else None,
            accion='CITA_CREADA',
            motivo='Reserva creada desde el sitio público',
            metadata_json={
                'cita_id': cita.id,
                'ip': self.request.META.get('REMOTE_ADDR', ''),
                'consentimiento': cita.consentimiento_aceptado,
            },
        )

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        especialista = serializer.validated_data['especialista']
        fecha_hora = serializer.validated_data['fecha_hora']
        sucursal = serializer.validated_data['sucursal']
        cliente_correo = serializer.validated_data['cliente_correo'].lower()

        conflicto_personal = Cita.objects.select_for_update().filter(
            cliente_correo__iexact=cliente_correo,
            fecha_hora=fecha_hora,
        ).exclude(estado='CANCELADA').exists()
        if conflicto_personal:
            return Response({
                'detail': 'Ya tienes una reserva en ese horario. Elige otra hora aunque sea con otro peluquero.',
                'sugerencia_sucursal_cercana': [],
            }, status=status.HTTP_409_CONFLICT)

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

        try:
            self.perform_create(serializer)
        except IntegrityError:
            return Response(
                {'detail': 'El bloque horario ya está ocupado por otra reserva.'},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'])
    def disponibilidad(self, request):
        especialista_id = request.query_params.get('especialista')
        fecha = request.query_params.get('fecha')
        if not especialista_id or not fecha:
            return Response({'detail': 'Se requieren especialista y fecha.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            inicio = datetime.strptime(fecha, '%Y-%m-%d')
            fin = inicio + timedelta(days=1)
        except ValueError:
            return Response({'detail': 'Formato de fecha inválido.'}, status=status.HTTP_400_BAD_REQUEST)
        ocupados = Cita.objects.filter(
            especialista_id=especialista_id,
            fecha_hora__gte=inicio,
            fecha_hora__lt=fin,
        ).exclude(estado='CANCELADA').values_list('fecha_hora', flat=True)
        bloques = sorted({
            cita.strftime('%H:%M')
            for cita in ocupados
        })
        return Response({'bloques_ocupados': bloques})

    @action(detail=True, methods=['post'])
    def confirmar(self, request, pk=None):
        cita = self.get_object()
        if not request.user.is_authenticated or request.user.rol not in ('ADMIN', 'RECEPCION', 'BARBERO'):
            return Response({'detail': 'No autorizado.'}, status=status.HTTP_403_FORBIDDEN)
        cita.estado = 'CONFIRMADA'
        cita.save()
        Auditoria.objects.create(
            usuario=request.user, accion='CITA_CONFIRMADA',
            motivo='Confirmación administrativa',
            metadata_json={'cita_id': cita.id},
        )
        return Response({'status': 'Cita confirmada correctamente'})

    @action(detail=True, methods=['post'])
    def cancelar(self, request, pk=None):
        cita = self.get_object()
        if not request.user.is_authenticated:
            return Response({'detail': 'Autenticación requerida.'}, status=status.HTTP_401_UNAUTHORIZED)
        if request.user.rol == 'CLIENTE' and cita.cliente_correo.lower() != request.user.email.lower():
            return Response({'detail': 'No autorizado.'}, status=status.HTTP_403_FORBIDDEN)
        cita.estado = 'CANCELADA'
        cita.save()
        Auditoria.objects.create(
            usuario=request.user, accion='CITA_CANCELADA',
            motivo='Cancelación por cliente o personal autorizado',
            metadata_json={'cita_id': cita.id},
        )
        return Response({'status': 'Cita cancelada y bloque liberado'})


class AtencionViewSet(viewsets.ModelViewSet):
    queryset = Atencion.objects.all()
    serializer_class = AtencionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.rol in ('ADMIN', 'RECEPCION'):
            return qs
        if self.request.user.rol == 'BARBERO':
            return qs.filter(cita__especialista__usuario=self.request.user)
        return qs.none()

class ComisionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Comision.objects.select_related('especialista__usuario', 'atencion').all()
    serializer_class = ComisionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.rol == 'ADMIN':
            return qs
        if self.request.user.rol == 'BARBERO':
            return qs.filter(especialista__usuario=self.request.user)
        return qs.none()