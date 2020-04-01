from django.urls import path

from datatools.views import UpdateReducedDataView

app_name = 'datatools'


urlpatterns = [
    # path('data/', DataProductListView.as_view(), name='list'),
    # path('data/group/create/', DataProductGroupCreateView.as_view(), name='group-create'),
    # path('data/group/list/', DataProductGroupListView.as_view(), name='group-list'),
    # path('data/group/add/', DataProductGroupDataView.as_view(), name='group-data'),
    # path('data/group/<pk>/', DataProductGroupDetailView.as_view(), name='group-detail'),
    # path('data/group/<pk>/delete/', DataProductGroupDeleteView.as_view(), name='group-delete'),
    # path('data/upload/', DataProductUploadView.as_view(), name='upload'),
    path('data/update/', UpdateReducedDataView.as_view(), name='update-reduced-data-gaia'),
]