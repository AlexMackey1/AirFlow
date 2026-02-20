"""
Author: Alexander Mackey
Student ID: C22739165
Description: URL routing configuration for core app. Maps URL patterns to view functions.

Pages:
    /            → map_view()       Live map view
    /analytics/  → analytics_view() Predictions & chart

API Endpoints:
    /api/heatmap/              → heatmap_data_api()
    /api/predictions/hourly/   → hourly_predictions_api()
    /api/flights/search/       → flight_search_api()
"""

from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    # ─── Pages ────────────────────────────────────────────────────────
    path('', views.map_view, name='map'),
    path('analytics/', views.analytics_view, name='analytics'),

    # ─── API Endpoints ────────────────────────────────────────────────
    path('api/heatmap/',              views.heatmap_data_api,       name='heatmap_api'),
    path('api/predictions/hourly/',   views.hourly_predictions_api, name='hourly_predictions_api'),
    path('api/flights/search/',       views.flight_search_api,      name='flight_search_api'),
]