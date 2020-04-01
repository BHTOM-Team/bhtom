"""django URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.2/topics/http/urls/
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
from django.urls import path, include

from django.views.generic import TemplateView
from .views import BlackHoleListView

from django.contrib import admin
from django.urls import path
from django.urls import include
from django.views.generic import TemplateView
from django.contrib.auth.views import LoginView, LogoutView
from django.conf import settings
from django.conf.urls.static import static
from rest_framework import routers, permissions
from myapp import views
from myapp.views import DataProductUploadView, TargetDetailView, CreateObservatory, ObservatoryList

router = routers.DefaultRouter()
#router.register('Upload', views.fits_upload)
router.register('result', views.result_fits)
router.register('status', views.status_fits)

urlpatterns = [
    path('targets/ <pk>/', TargetDetailView.as_view(), name='detail'),
    path('', include('tom_common.urls')),
    path('datatools/', include('datatools.urls')),
    path('about/', TemplateView.as_view(template_name='tom_common/about.html'), name='about'),
    path('bhlist/', BlackHoleListView.as_view(template_name='tom_common/bhlist.html'), name='bhlist'),
    path('bhlist/', BlackHoleListView.as_view(template_name='tom_common/bhlist.html'), name='targets'),
    path('bhlist/<pk>/', TargetDetailView.as_view(), name='bhlist_detail'),
    path('targets/list', BlackHoleListView.as_view(template_name='tom_common/bhlist.html'), name='targets'),
    path('', include(router.urls)),
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),
    path('upload/', DataProductUploadView.as_view(), name='upload'),
    path('observatory/create', CreateObservatory.as_view(), name='observatory_create'),
    path('observatory/list', ObservatoryList.as_view(), name='observatory'),

    # The static helper below only works in development see
    # https://docs.djangoproject.com/en/2.1/howto/static-files/#serving-files-uploaded-by-a-user-during-development
 ] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)