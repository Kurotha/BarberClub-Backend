from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from core.models import Sucursal, Especialista, Servicio


class Command(BaseCommand):
    help = 'Carga los catálogos iniciales de BarberClub'

    def handle(self, *args, **options):
        sucursales = [
            ('El Golf', 'Av. Isidora Goyenechea 3120', 'Las Condes'),
            ('Alonso de Córdova', 'Av. Alonso de Córdova 3890', 'Vitacura'),
            ('Pedro de Valdivia', 'Av. Pedro de Valdivia 1450', 'Providencia'),
            ('La Dehesa', 'Av. La Dehesa 1844', 'Lo Barnechea'),
        ]
        for nombre, direccion, comuna in sucursales:
            Sucursal.objects.get_or_create(
                nombre=nombre,
                defaults={'direccion': direccion, 'comuna': comuna, 'activa': True},
            )

        maestros = [
            ('Sebastian Krause', 'Las Condes', 'Maestro Barbero', 12),
            ('Valentina Restrepo', 'Vitacura', 'Estilista Senior', 11),
            ('Arturo Benavides', 'Providencia', 'Barbero Tradicional', 16),
            ('Sofia Montalva', 'Lo Barnechea', 'Colorista y Terapeuta', 9),
        ]
        Usuario = get_user_model()
        for index, (nombre, comuna, especialidad, experiencia) in enumerate(maestros, start=1):
            sucursal = Sucursal.objects.get(comuna=comuna)
            usuario, _ = Usuario.objects.get_or_create(
                username=f'maestro{index}',
                defaults={
                    'first_name': nombre,
                    'rol': 'BARBERO',
                    'is_active': True,
                },
            )
            if not usuario.has_usable_password():
                usuario.set_password('Cambiar123!')
                usuario.save(update_fields=['password'])
            Especialista.objects.get_or_create(
                usuario=usuario,
                defaults={
                    'sucursal': sucursal,
                    'especialidad': especialidad,
                    'anos_experiencia': experiencia,
                },
            )

        servicios = [
            ('Corte Clasico', 30, 18000, 'MASCULINO'),
            ('Corte y Barba', 60, 28000, 'MASCULINO'),
            ('Colorimetria Unisex', 60, 35000, 'UNISEX'),
            ('Ritual Integral Unisex', 90, 42000, 'RITUAL'),
        ]
        for nombre, duracion, precio, categoria in servicios:
            Servicio.objects.update_or_create(
                nombre=nombre,
                defaults={
                    'duracion_minutos': duracion,
                    'precio': precio,
                    'activo': True,
                    'categoria': categoria,
                },
            )

        self.stdout.write(self.style.SUCCESS('Catálogos iniciales cargados.'))
