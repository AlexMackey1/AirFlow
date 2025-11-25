from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin
from .models import Airport, PassengerHeatmapData


@admin.register(Airport)
class AirportAdmin(GISModelAdmin):
    """Admin for Airport model with map widget"""
    list_display = ('iata_code', 'name', 'city', 'country')
    search_fields = ('iata_code', 'name', 'city')
    gis_widget_kwargs = {
        'attrs': {
            'default_zoom': 12,
            'default_lon': -6.2701,
            'default_lat': 53.4213,
        }
    }


@admin.register(PassengerHeatmapData)
class PassengerHeatmapDataAdmin(admin.ModelAdmin):
    """Admin for PassengerHeatmapData"""
    list_display = ('airport', 'timestamp', 'latitude', 'longitude', 'passenger_count')
    list_filter = ('airport', 'timestamp')
    search_fields = ('airport__iata_code', 'airport__name')
    date_hierarchy = 'timestamp'
    
    def get_queryset(self, request):
        """Optimize queries"""
        return super().get_queryset(request).select_related('airport')