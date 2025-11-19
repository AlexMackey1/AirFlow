from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.map_view, name='map'),
    path('api/heatmap/', views.heatmap_data_api, name='heatmap_api'),
]