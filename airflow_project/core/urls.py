"""
Author: Alexander Mackey
Student ID: C22739165
Description: URL routing configuration for core app. Maps URL patterns to view functions, 
defining the main map page route and API endpoints for heatmap data and hourly predictions.
"""

from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    # Main map view
    path('', views.map_view, name='map'),
    
    # API endpoints
    path('api/heatmap/', views.heatmap_data_api, name='heatmap_api'),
    path('api/predictions/hourly/', views.hourly_predictions_api, name='hourly_predictions_api'),
]