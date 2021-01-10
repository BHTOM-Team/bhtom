from django.urls import path

from datatools.views import UpdateReducedDataView, FetchTargetNames

app_name = 'datatools'


urlpatterns = [
    path('data/update/', UpdateReducedDataView.as_view(), name='update-reduced-data-gaia'),
    path('data/fetch-target-names/', FetchTargetNames.as_view(), name='fetch-target-names')
]