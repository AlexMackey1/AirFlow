"""
Author: Alexander Mackey
Student ID: C22739165
Description: URL routing configuration for core app. Maps URL patterns to view functions, 
defining the main map page route and API endpoint for heatmap data retrieval.
"""

from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.map_view, name='map'),
    path('api/heatmap/', views.heatmap_data_api, name='heatmap_api'),
]