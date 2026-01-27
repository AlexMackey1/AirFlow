"""
Author: Alexander Mackey
Student ID: C22739165
Description: Django admin configuration for AirFlow models. Registers all models including
Airport, AircraftType, LoadFactor, Flight, PassengerEstimate, and PassengerHeatmapData with 
custom admin interfaces for efficient data management and visualization.
"""

from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin
from .models import (
    Airport, 
    AircraftType, 
    LoadFactor, 
    Flight, 
    PassengerEstimate, 
    PassengerHeatmapData
)


@admin.register(Airport)
class AirportAdmin(GISModelAdmin):
    """
    Admin configuration for Airport model with geographic map widget.
    
    Uses GISModelAdmin to enable interactive map display for the PostGIS Point field.
    Allows admins to visually select airport locations on a map interface.
    """
    list_display = ('iata_code', 'name', 'city', 'country', 'timezone')
    search_fields = ('iata_code', 'name', 'city')
    list_filter = ('country',)
    
    # Configure the map widget for location field
    gis_widget_kwargs = {
        'attrs': {
            'default_zoom': 12,
            'default_lon': -6.2701,  # Dublin Airport
            'default_lat': 53.4213,
        }
    }


@admin.register(AircraftType)
class AircraftTypeAdmin(admin.ModelAdmin):
    """
    Admin configuration for AircraftType model.
    
    Displays capacity breakdown and enables searching by model/manufacturer.
    """
    list_display = (
        'model', 
        'manufacturer', 
        'total_capacity', 
        'economy_capacity', 
        'business_capacity', 
        'first_class_capacity'
    )
    search_fields = ('model', 'manufacturer')
    list_filter = ('manufacturer',)
    ordering = ('manufacturer', 'model')


@admin.register(LoadFactor)
class LoadFactorAdmin(admin.ModelAdmin):
    """
    Admin configuration for LoadFactor model.
    
    Displays load factors with route type, season, airline filters.
    Highlights default values for easy identification.
    """
    list_display = (
        'route_type', 
        'season', 
        'airline', 
        'percentage_display', 
        'is_default', 
        'source'
    )
    list_filter = ('route_type', 'season', 'is_default')
    search_fields = ('airline', 'source')
    ordering = ('route_type', 'season', 'airline')
    
    def percentage_display(self, obj):
        """Display percentage as readable format (e.g., 84%)"""
        return f"{float(obj.percentage) * 100:.1f}%"
    percentage_display.short_description = 'Load Factor'


@admin.register(Flight)
class FlightAdmin(admin.ModelAdmin):
    """
    Admin configuration for Flight model.
    
    Comprehensive interface for managing flight schedules with filtering,
    searching, and bulk actions. Optimizes queries with select_related.
    """
    list_display = (
        'flight_number',
        'origin',
        'destination',
        'departure_time',
        'aircraft_type',
        'airline',
        'status',
        'estimated_passengers',
        'confidence_display'
    )
    list_filter = ('status', 'airline', 'origin', 'destination')
    search_fields = ('flight_number', 'airline')
    date_hierarchy = 'departure_time'
    ordering = ('-departure_time',)
    
    # Optimize queries
    def get_queryset(self, request):
        """Fetch related Airport and AircraftType data efficiently"""
        return super().get_queryset(request).select_related(
            'origin', 
            'destination', 
            'aircraft_type'
        )
    
    def confidence_display(self, obj):
        """Display confidence score as percentage with color coding"""
        if obj.confidence_score is None:
            return '—'
        score = float(obj.confidence_score)
        percentage = f"{score * 100:.0f}%"
        
        # Color coding
        if score >= 0.8:
            return f'✓ {percentage}'  # High confidence
        elif score >= 0.5:
            return f'~ {percentage}'  # Medium confidence
        else:
            return f'⚠ {percentage}'  # Low confidence
    
    confidence_display.short_description = 'Confidence'
    
    # Fieldset organization for add/edit form
    fieldsets = (
        ('Flight Information', {
            'fields': ('flight_number', 'airline', 'status')
        }),
        ('Schedule', {
            'fields': ('origin', 'destination', 'departure_time', 'arrival_time')
        }),
        ('Aircraft', {
            'fields': ('aircraft_type',)
        }),
        ('Computed Estimates', {
            'fields': ('estimated_passengers', 'confidence_score'),
            'description': 'These fields are automatically computed by EstimationService'
        }),
    )


@admin.register(PassengerEstimate)
class PassengerEstimateAdmin(admin.ModelAdmin):
    """
    Admin configuration for PassengerEstimate model.
    
    Displays pre-computed hourly aggregations with confidence levels.
    Provides date-based filtering for temporal analysis.
    """
    list_display = (
        'airport',
        'date',
        'hour_display',
        'passenger_count',
        'confidence_level_display',
        'created_at'
    )
    list_filter = ('airport', 'date', 'created_at')
    search_fields = ('airport__iata_code', 'airport__name')
    date_hierarchy = 'date'
    ordering = ('-date', 'hour')
    
    def get_queryset(self, request):
        """Optimize query with select_related"""
        return super().get_queryset(request).select_related('airport')
    
    def hour_display(self, obj):
        """Display hour in HH:00 format"""
        return f"{obj.hour:02d}:00"
    hour_display.short_description = 'Hour'
    
    def confidence_level_display(self, obj):
        """Display confidence level with emoji indicators"""
        level = obj.confidence_level
        score = f"{obj.confidence_score:.2f}"
        
        if level == 'High':
            return f'🟢 {level} ({score})'
        elif level == 'Medium':
            return f'🟡 {level} ({score})'
        else:
            return f'🔴 {level} ({score})'
    
    confidence_level_display.short_description = 'Confidence'


@admin.register(PassengerHeatmapData)
class PassengerHeatmapDataAdmin(admin.ModelAdmin):
    """
    Admin configuration for PassengerHeatmapData model.
    
    Provides filtered, searchable interface for viewing passenger density points.
    Optimizes database queries using select_related.
    """
    list_display = (
        'airport', 
        'timestamp', 
        'latitude', 
        'longitude', 
        'passenger_count'
    )
    list_filter = ('airport', 'timestamp')
    search_fields = ('airport__iata_code', 'airport__name')
    date_hierarchy = 'timestamp'
    ordering = ('-timestamp',)
    
    def get_queryset(self, request):
        """Optimize query with select_related"""
        return super().get_queryset(request).select_related('airport')