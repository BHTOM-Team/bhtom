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

from django.conf import settings
from django.conf.urls.static import static
from django.urls import include
from django.urls import path
from django.views.generic import TemplateView
from rest_framework import routers

from bhtom import views
from bhtom.views import DataProductUploadView, TargetDetailView, TargetInteractivePhotometryView, \
    TargetDownloadPhotometryDataView, TargetDownloadPhotometryStatsView, \
    TargetDownloadSpectroscopyDataView, TargetFileDetailView, TargetDownloadPhotometryStatsLatexTableView, \
    TargetMicrolensingView, ObservatoryDetailView, TargetInteractiveDeletingPhotometryView, BHtomCatalogQueryView
from bhtom.views import DeleteInstrument, UpdateInstrument, CreateInstrument, DataProductDeleteView
from bhtom.views import DeleteObservatory, UpdateObservatory, ObservatoryList, CreateObservatory
from bhtom.views import RegisterUser, DataProductFeatureView, UserUpdateView, photometry_download, fits_download
from bhtom.views import TargetCreateView, TargetUpdateView, TargetDeleteView, TargetGroupingView
from bhtom.views import data_download, CommentDeleteView, TargetAddRemoveGroupingView
from .data_rest_api.data_upload import PhotometryUpload
from .views import BlackHoleListView

router = routers.DefaultRouter()
router.register('upload', views.fits_upload)
router.register('result', views.result_fits)
#router.register('status', views.status_fits)

urlpatterns = [
    path('', include('tom_common.urls')),
    path('datatools/', include('datatools.urls')),
    path('about/', TemplateView.as_view(template_name='tom_common/about.html'), name='about'),
    path('bhlist/', BlackHoleListView.as_view(template_name='tom_common/bhlist.html'), name='bhlist'),
    path('bhlist/', BlackHoleListView.as_view(template_name='tom_common/bhlist.html'), name='targets'),
    path('django_plotly_dash/', include('django_plotly_dash.urls')),
    path('bhlist/create/', TargetCreateView.as_view(), name='bhlist_create'),
    path('bhlist/<int:pk>/update/', TargetUpdateView.as_view(), name='bhlist_update'),
    path('bhlist/<int:pk>/delete/', TargetDeleteView.as_view(), name='bhlist_delete'),
    path('bhlist/<int:pk>/file/<int:pk_fit>', TargetFileDetailView.as_view(), name='bhlist_file_detail'),
    path('bhlist/<int:pk>/', TargetDetailView.as_view(), name='bhlist_detail'),
    path('observatory/<int:pk>/', ObservatoryDetailView.as_view(template_name='bhtom/observatory_detail.html'), name='observatory_detail'),
    path('bhlist/<int:pk>/iphotometry', TargetInteractivePhotometryView.as_view(), name='bhlist_i_photometry'),
    path('bhlist/<int:pk>/idphotometry', TargetInteractiveDeletingPhotometryView.as_view(), name='bhlist_i_d_photometry'),
    path('bhlist/<int:pk>/microlensing', TargetMicrolensingView.as_view(), name="bhlist_i_microlensing"),
    path('bhlist/<int:pk>/download-photometry', TargetDownloadPhotometryDataView.as_view(), name='bhlist_download_photometry_data'),
    path('bhlist/<int:pk>/download-photometry-stats',
         TargetDownloadPhotometryStatsView.as_view(),
         name='bhlist_download_photometry_stats'),
    path('bhlist/<int:pk>/download-photometry-stats-latex',
         TargetDownloadPhotometryStatsLatexTableView.as_view(),
         name='bhlist_download_photometry_stats_latex'),
    path('bhlist/<int:pk>/download-spectroscopy', TargetDownloadSpectroscopyDataView.as_view(), name='bhlist_download_spectroscopy_data'),
    path('bhlist/grouping/', TargetGroupingView.as_view(), name='targetgrouping'),
    path('bhlist/<int:pk_target>/file/<int:pk>/delete/', DataProductDeleteView.as_view(), name='data_delete'),
    path('bhlist/<int:pk_target>/comment/<int:pk>/delete', CommentDeleteView.as_view(), name='comment_delete'),
    path('', include(router.urls)),
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),
    path('dataUpload/', DataProductUploadView.as_view(), name='data_upload'),
    path('photometry-upload/', PhotometryUpload.as_view(), name='photometry_upload'),
    path('instrument/create/', CreateInstrument.as_view(), name='instrument_create'),
    path('instrument/<int:pk>/delete/', DeleteInstrument.as_view(), name='instrument_delete'),
    path('instrument/<int:pk>/update/', UpdateInstrument.as_view(), name='instrument_update'),
    path('bhcatalogs/query/', BHtomCatalogQueryView.as_view(), name='catalogs_query'),
    path('observatory/create/', CreateObservatory.as_view(), name='observatory_create'),
    path('observatory/<int:pk>/update/', UpdateObservatory.as_view(), name='observatory_update'),
    path('observatory/<int:pk>/delete/', DeleteObservatory.as_view(), name='observatory_delete'),
    path('observatory/list/', ObservatoryList.as_view(), name='observatory'),
    path('user/create/', RegisterUser.as_view(), name='register_user'),
    path('user/<int:pk>/update/', UserUpdateView.as_view(), name='user-update'),
    path('tom_dataproducts/data/<int:pk>/feature/', DataProductFeatureView.as_view(), name='bhtom_feature'),

    path('download/fits/<int:file_id>/', fits_download.as_view(), name='fits_download'),
    path('download/photometry/<int:file_id>/', photometry_download.as_view(), name='photometry_download'),
    path('download/data/<int:file_id>/', data_download.as_view(), name='data_download'),

    path('add_remove_grouping/', TargetAddRemoveGroupingView.as_view(), name='add_remove_grouping'),

    # The static helper below only works in development see
    # https://docs.djangoproject.com/en/2.1/howto/static-files/#serving-files-uploaded-by-a-user-during-development
 ]
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)