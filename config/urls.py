"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from core.views import (
    SucursalViewSet, EspecialistaViewSet, ServicioViewSet,
    CitaViewSet, AtencionViewSet, ComisionViewSet,
    auth_register, auth_login, auth_logout, auth_me,
    password_reset_request, password_reset_confirm
)

router = DefaultRouter()
router.register(r'sucursales', SucursalViewSet)
router.register(r'especialistas', EspecialistaViewSet)
router.register(r'servicios', ServicioViewSet)
router.register(r'citas', CitaViewSet)
router.register(r'atenciones', AtencionViewSet)
router.register(r'comisiones', ComisionViewSet)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/register/', auth_register),
    path('api/auth/login/', auth_login),
    path('api/auth/logout/', auth_logout),
    path('api/auth/me/', auth_me),
    path('api/auth/password-reset/', password_reset_request),
    path('api/auth/password-reset-confirm/', password_reset_confirm),
    path('api/', include(router.urls)),
]