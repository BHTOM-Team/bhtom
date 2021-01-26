from django.urls import path

from datatools.views import UpdateReducedDataView, FetchTargetNames, obsInfo_download, observatory_fits_download

app_name = 'datatools'


urlpatterns = [
    path('data/update/', UpdateReducedDataView.as_view(), name='update-reduced-data-gaia'),
    path('data/fetch-target-names/', FetchTargetNames.as_view(), name='fetch-target-names'),
    path('download/obsInfo/<str:id>/', obsInfo_download.as_view(), name='obsInfo_download'),
    path('download/obsFits/<str:id>/', observatory_fits_download.as_view(), name='obsFits_download'),
]