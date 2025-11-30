"""
Author: Alexander Mackey
Student ID: C22739165
Description: Django admin configuration for AirFlow models. Registers Airport and 
PassengerHeatmapData models with the admin interface, providing custom displays and 
geographic map widgets for spatial data management.
"""

from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin
from .models import Airport, PassengerHeatmapData


@admin.register(Airport)
class AirportAdmin(GISModelAdmin):
    """
    Admin configuration for Airport model with geographic map widget.
    
    Uses GISModelAdmin to enable interactive map display for the PostGIS Point field.
    Allows admins to visually select airport locations on a map interface.
    """
    
    # Display these fields in the admin list view
    list_display = ('iata_code', 'name', 'city', 'country')
    
    # Enable search functionality on these fields
    search_fields = ('iata_code', 'name', 'city')
    
    # Configure the map widget that appears when editing location field
    gis_widget_kwargs = {
        'attrs': {
            'default_zoom': 12,           # Initial zoom level for the map
            'default_lon': -6.2701,       # Default longitude (Dublin Airport)
            'default_lat': 53.4213,       # Default latitude (Dublin Airport)
        }
    }


@admin.register(PassengerHeatmapData)
class PassengerHeatmapDataAdmin(admin.ModelAdmin):
    """
    Admin configuration for PassengerHeatmapData model.
    
    Provides filtered, searchable interface for viewing passenger data points.
    Optimizes database queries using select_related to reduce query count.
    """
    
    # Display these fields in the admin list view
    list_display = ('airport', 'timestamp', 'latitude', 'longitude', 'passenger_count')
    
    # Add filter sidebar for these fields
    list_filter = ('airport', 'timestamp')
    
    # Enable search on airport code and name (using double underscore for related field)
    search_fields = ('airport__iata_code', 'airport__name')
    
    # Add date-based drill-down navigation by timestamp
    date_hierarchy = 'timestamp'
    
    def get_queryset(self, request):
        """
        Override queryset to optimize database queries.
        
        Uses select_related to fetch related Airport data in a single query
        instead of making separate queries for each row (N+1 problem prevention).
        
        Args:
            request: The HTTP request object
            
        Returns:
            Optimized QuerySet with airport data pre-fetched
        """
        return super().get_queryset(request).select_related('airport')