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

from tom_common.views import UserListView, UserPasswordChangeView, UserCreateView, UserDeleteView, UserUpdateView
from tom_common.views import CommentDeleteView, GroupCreateView, GroupUpdateView, GroupDeleteView

from myapp import views
from myapp.views import DataProductUploadView, TargetDetailView, CreateObservatory, ObservatoryList, TargetFileDetailView
from myapp.views import TargetCreateView, TargetUpdateView, TargetDeleteView, TargetFileView, UpdateObservatory, DeleteObservatory

urlpatterns = [
    path('', include('tom_common.urls')),
    path('datatools/', include('datatools.urls')),
    path('about/', TemplateView.as_view(template_name='tom_common/about.html'), name='about'),
    path('bhlist/', BlackHoleListView.as_view(template_name='tom_common/bhlist.html'), name='bhlist'),
    path('bhlist/', BlackHoleListView.as_view(template_name='tom_common/bhlist.html'), name='targets'),
    path('bhlist/create/', TargetCreateView.as_view(), name='bhlist_create'),
    path('bhlist/<pk>/update/', TargetUpdateView.as_view(), name='bhlist_update'),
    path('bhlist/<pk>/delete/', TargetDeleteView.as_view(), name='bhlist_delete'),
    path('bhlist/<pk>/', TargetDetailView.as_view(), name='bhlist_detail'),
    # The static helper below only works in development see
    # https://docs.djangoproject.com/en/2.1/howto/static-files/#serving-files-uploaded-by-a-user-during-development
 ] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)


