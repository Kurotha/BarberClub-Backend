from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from django.test import override_settings
from rest_framework.test import APIClient

from .models import Sucursal, Especialista, Servicio, Cita, Auditoria


class BarberClubSecurityTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.sucursal = Sucursal.objects.create(
            nombre='El Golf', direccion='Av. Test 1', comuna='Las Condes'
        )
        barbero_user = get_user_model().objects.create_user(
            username='barbero', password='TestPassword!2026', rol='BARBERO'
        )
        self.especialista = Especialista.objects.create(
            usuario=barbero_user, sucursal=self.sucursal,
            especialidad='Barbería', anos_experiencia=10
        )
        self.servicio = Servicio.objects.create(
            nombre='Corte Clásico', duracion_minutos=30, precio=18000
        )

    def payload(self, **overrides):
        payload = {
            'cliente_nombre': 'Cliente Seguro',
            'cliente_telefono': '+56912345678',
            'cliente_correo': 'cliente@correo.cl',
            'especialista': self.especialista.id,
            'sucursal': self.sucursal.id,
            'servicio': self.servicio.id,
            'fecha_hora': (timezone.now() + timedelta(days=2)).isoformat(),
            'consentimiento_aceptado': True,
            'version_politica': 'v1.0-2026',
        }
        payload.update(overrides)
        return payload

    def test_reserva_requiere_consentimiento(self):
        response = self.client.post('/api/citas/', self.payload(consentimiento_aceptado=False), format='json')
        self.assertEqual(response.status_code, 400)
        self.assertNotIn('id', response.data)

    def test_reserva_crea_auditoria(self):
        response = self.client.post('/api/citas/', self.payload(), format='json')
        self.assertEqual(response.status_code, 201)
        self.assertTrue(Auditoria.objects.filter(accion='CITA_CREADA').exists())

    def test_bloque_horario_no_se_duplica(self):
        fecha = (timezone.now() + timedelta(days=3)).isoformat()
        first = self.client.post('/api/citas/', self.payload(fecha_hora=fecha), format='json')
        second = self.client.post('/api/citas/', self.payload(cliente_nombre='Otro Cliente', fecha_hora=fecha), format='json')
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 409)

    def test_dos_personas_no_comparten_horario_con_el_mismo_peluquero(self):
        fecha = (timezone.now() + timedelta(days=5)).isoformat()
        first = self.client.post(
            '/api/citas/',
            self.payload(
                cliente_nombre='Persona Uno',
                cliente_correo='persona1@correo.cl',
                fecha_hora=fecha,
            ),
            format='json',
        )
        second = self.client.post(
            '/api/citas/',
            self.payload(
                cliente_nombre='Persona Dos',
                cliente_correo='persona2@correo.cl',
                fecha_hora=fecha,
            ),
            format='json',
        )
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 409)

    def test_mismo_cliente_no_puede_reservar_dos_barberos_a_la_misma_hora(self):
        otro_usuario = get_user_model().objects.create_user(
            username='otro_barbero', password='TestPassword!2026', rol='BARBERO'
        )
        otro_especialista = Especialista.objects.create(
            usuario=otro_usuario, sucursal=self.sucursal,
            especialidad='Barbería', anos_experiencia=5
        )
        fecha = (timezone.now() + timedelta(days=4)).isoformat()
        first = self.client.post('/api/citas/', self.payload(fecha_hora=fecha), format='json')
        second = self.client.post(
            '/api/citas/',
            self.payload(especialista=otro_especialista.id, fecha_hora=fecha),
            format='json',
        )
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 409)

    def test_datos_personales_no_son_publicos(self):
        self.client.post('/api/citas/', self.payload(), format='json')
        response = self.client.get('/api/citas/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_atenciones_requieren_autenticacion(self):
        response = self.client.post('/api/atenciones/', {}, format='json')
        self.assertIn(response.status_code, (401, 403))

    def test_telefono_reserva_solo_admite_numeros(self):
        response = self.client.post(
            '/api/citas/',
            self.payload(cliente_telefono='+569abc123456'),
            format='json',
        )
        self.assertEqual(response.status_code, 400)

    def test_registro_rechaza_telefono_con_letras(self):
        response = self.client.post(
            '/api/auth/register/',
            {
                'username': 'prueba_telefono',
                'email': 'telefono@correo.cl',
                'password': 'TestPassword!2026',
                'telefono': '+569abc1234',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 400)

    def test_reserva_rechaza_numeros_en_nombre(self):
        response = self.client.post(
            '/api/citas/',
            self.payload(cliente_nombre='Freddy123 Carrasco'),
            format='json',
        )
        self.assertEqual(response.status_code, 400)

    def test_registro_rechaza_numeros_en_nombre(self):
        response = self.client.post(
            '/api/auth/register/',
            {
                'username': 'prueba_nombre',
                'email': 'nombre@correo.cl',
                'password': 'TestPassword!2026',
                'first_name': 'Freddy123',
                'telefono': '+56912345678',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 400)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_recuperacion_envia_correo_real_o_local(self):
        usuario = get_user_model().objects.create_user(
            username='recuperacion',
            email='recuperacion@correo.cl',
            password='TestPassword!2026',
        )
        response = self.client.post(
            '/api/auth/password-reset/',
            {'email': usuario.email, 'frontend_url': 'http://127.0.0.1:5173'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Restablecer contraseña', mail.outbox[0].subject)
        self.assertIn('reset=1', mail.outbox[0].body)

    def test_login_y_sesion(self):
        get_user_model().objects.create_user(
            username='cliente',
            email='cliente@correo.cl',
            password='TestPassword!2026',
            rol='CLIENTE',
            telefono='+56912345678',
        )
        response = self.client.post(
            '/api/auth/login/',
            {'username': 'cliente', 'password': 'TestPassword!2026'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        me = self.client.get('/api/auth/me/')
        self.assertTrue(me.json()['authenticated'])
        self.assertEqual(me.json()['telefono'], '+56912345678')
