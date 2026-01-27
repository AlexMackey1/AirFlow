"""
Author: Alexander Mackey
Student ID: C22739165
Description: Database models for AirFlow application. Implements complete data model from 
interim report including Airport, AircraftType, LoadFactor, Flight, PassengerEstimate, and 
PassengerHeatmapData entities. Uses PostGIS for spatial operations and follows ERD design 
from Chapter 4.4.1.
"""

from django.contrib.gis.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone


class Airport(models.Model):
    """
    Airport entity with spatial location and timezone support.
    
    Uses IATA three-letter codes as primary key for meaningful identifiers.
    PostGIS geography type maintains accuracy for distance calculations using
    spherical earth model (SRID 4326).
    """
    iata_code = models.CharField(
        max_length=3, 
        primary_key=True,
        help_text="IATA three-letter airport code (e.g., DUB, ORK, SNN)"
    )
    name = models.CharField(max_length=200)
    city = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    timezone = models.CharField(
        max_length=50,
        default='Europe/Dublin',
        help_text="Timezone for local time conversions (e.g., Europe/Dublin)"
    )
    location = models.PointField(
        geography=True,
        srid=4326,
        help_text="Geographic coordinates (longitude, latitude)"
    )

    def __str__(self):
        return f"{self.name} ({self.iata_code})"

    class Meta:
        ordering = ['name']
        verbose_name = "Airport"
        verbose_name_plural = "Airports"


class AircraftType(models.Model):
    """
    Aircraft type entity with capacity breakdown by cabin class.
    
    Normalizes aircraft data to avoid duplication across flight records.
    Capacity varies from 50-seat turboprops (ATR-72) to 400-seat wide-bodies (B777).
    Separate class fields support future sophistication when detailed data becomes available.
    """
    model = models.CharField(
        max_length=50, 
        unique=True,
        help_text="Aircraft model designation (e.g., A320, B777, ATR-72)"
    )
    manufacturer = models.CharField(
        max_length=100,
        help_text="Aircraft manufacturer (e.g., Airbus, Boeing, ATR)"
    )
    total_capacity = models.IntegerField(
        validators=[MinValueValidator(1)],
        help_text="Total passenger capacity"
    )
    economy_capacity = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Economy class seats (for future use)"
    )
    business_capacity = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Business class seats (for future use)"
    )
    first_class_capacity = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="First class seats (for future use)"
    )

    def __str__(self):
        return f"{self.manufacturer} {self.model} ({self.total_capacity} seats)"

    class Meta:
        ordering = ['manufacturer', 'model']
        verbose_name = "Aircraft Type"
        verbose_name_plural = "Aircraft Types"


class LoadFactor(models.Model):
    """
    Load factor entity with configurable defaults by route type, season, and airline.
    
    Load factors vary by route type (short-haul vs long-haul), season, and airline.
    Default flag identifies fallback values when specific combinations lack entries.
    For example: if no "short_haul, summer, Ryanair" entry exists, system uses
    the default short-haul value.
    
    Based on IATA 2024-2025 global outlook: 84% short-haul, 82% long-haul.
    """
    ROUTE_TYPE_CHOICES = [
        ('short_haul', 'Short Haul'),
        ('long_haul', 'Long Haul'),
        ('regional', 'Regional'),
    ]
    
    SEASON_CHOICES = [
        ('all_year', 'All Year'),
        ('summer', 'Summer'),
        ('winter', 'Winter'),
    ]

    route_type = models.CharField(
        max_length=20,
        choices=ROUTE_TYPE_CHOICES,
        help_text="Type of route (short_haul, long_haul, regional)"
    )
    season = models.CharField(
        max_length=20,
        choices=SEASON_CHOICES,
        default='all_year',
        help_text="Season for this load factor"
    )
    airline = models.CharField(
        max_length=100,
        blank=True,
        default='',
        help_text="Specific airline (blank for default)"
    )
    percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Load factor as decimal (e.g., 0.84 for 84%)"
    )
    is_default = models.BooleanField(
        default=False,
        help_text="Flag indicating this is a fallback default value"
    )
    source = models.CharField(
        max_length=200,
        help_text="Data source (e.g., 'IATA 2024-2025')"
    )

    def __str__(self):
        airline_str = f" - {self.airline}" if self.airline else ""
        default_str = " [DEFAULT]" if self.is_default else ""
        return f"{self.route_type} ({self.percentage}){airline_str}{default_str}"

    class Meta:
        ordering = ['route_type', 'season', 'airline']
        verbose_name = "Load Factor"
        verbose_name_plural = "Load Factors"
        # Ensure unique combinations
        unique_together = [['route_type', 'season', 'airline']]


class Flight(models.Model):
    """
    Flight entity with origin, destination, aircraft type, and computed estimates.
    
    Timestamps use local airport time without timezone for simplified display,
    matching how passengers think (locally). Timezone conversions happen when
    comparing across airports using the Airport.timezone field.
    
    Estimated passengers and confidence scores are computed by EstimationService
    and cached here for performance.
    """
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('cancelled', 'Cancelled'),
        ('delayed', 'Delayed'),
        ('departed', 'Departed'),
        ('arrived', 'Arrived'),
    ]

    flight_number = models.CharField(
        max_length=10,
        help_text="Flight number (e.g., EI101, BA832)"
    )
    origin = models.ForeignKey(
        Airport,
        on_delete=models.CASCADE,
        related_name='departures',
        help_text="Departure airport"
    )
    destination = models.ForeignKey(
        Airport,
        on_delete=models.CASCADE,
        related_name='arrivals',
        help_text="Arrival airport"
    )
    departure_time = models.DateTimeField(
        help_text="Scheduled departure time (local airport time)"
    )
    arrival_time = models.DateTimeField(
        help_text="Scheduled arrival time (local airport time)"
    )
    aircraft_type = models.ForeignKey(
        AircraftType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Aircraft type (null triggers intelligent defaults)"
    )
    airline = models.CharField(
        max_length=100,
        help_text="Operating airline"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='scheduled',
        help_text="Current flight status"
    )
    
    # Computed fields (populated by EstimationService)
    estimated_passengers = models.IntegerField(
        null=True,
        blank=True,
        help_text="Estimated passenger count (computed by algorithm)"
    )
    confidence_score = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Confidence score 0.0-1.0 (computed by algorithm)"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.flight_number} {self.origin.iata_code}→{self.destination.iata_code} @ {self.departure_time.strftime('%H:%M')}"

    @property
    def route_type(self):
        """
        Determine route type for load factor lookup.
        Simple heuristic based on distance or destination region.
        """
        # For now, simplified logic:
        # If destination is in Europe (common European countries), it's short-haul
        # Otherwise long-haul
        # This can be refined with actual distance calculations later
        european_countries = ['Ireland', 'United Kingdom', 'France', 'Germany', 'Spain', 
                             'Italy', 'Netherlands', 'Belgium', 'Portugal', 'Greece']
        
        if self.destination.country in european_countries:
            return 'short_haul'
        else:
            return 'long_haul'

    class Meta:
        ordering = ['departure_time']
        verbose_name = "Flight"
        verbose_name_plural = "Flights"
        indexes = [
            models.Index(fields=['origin', 'departure_time']),
            models.Index(fields=['destination', 'arrival_time']),
            models.Index(fields=['status']),
        ]


class PassengerEstimate(models.Model):
    """
    Pre-computed hourly passenger aggregations for performance optimization.
    
    Stores results from EstimationService to avoid recalculating on every request.
    Hourly resolution balances detail with usability, matching how people naturally
    plan arrival times.
    
    Confidence scores reflect weighted data quality assessment from Stage 5 of algorithm.
    """
    airport = models.ForeignKey(
        Airport,
        on_delete=models.CASCADE,
        help_text="Airport for this estimate"
    )
    date = models.DateField(
        help_text="Date of estimate"
    )
    hour = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(23)],
        help_text="Hour of day (0-23)"
    )
    passenger_count = models.IntegerField(
        validators=[MinValueValidator(0)],
        help_text="Estimated passenger count for this hour"
    )
    confidence_score = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Average confidence score for this hour (0.0-1.0)"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this estimate was computed"
    )

    def __str__(self):
        return f"{self.airport.iata_code} {self.date} {self.hour:02d}:00 - {self.passenger_count} pax (conf: {self.confidence_score:.2f})"

    @property
    def confidence_level(self):
        """Return human-readable confidence level"""
        if self.confidence_score >= 0.8:
            return 'High'
        elif self.confidence_score >= 0.5:
            return 'Medium'
        else:
            return 'Low'

    class Meta:
        ordering = ['airport', 'date', 'hour']
        verbose_name = "Passenger Estimate"
        verbose_name_plural = "Passenger Estimates"
        unique_together = [['airport', 'date', 'hour']]
        indexes = [
            models.Index(fields=['airport', 'date']),
        ]


class PassengerHeatmapData(models.Model):
    """
    Passenger density points for heatmap visualization.
    
    Generated from PassengerEstimate aggregations and temporal distribution model.
    Each point represents estimated passenger presence at specific location and time.
    Used by Leaflet.heat for rendering blue-to-red density gradient.
    """
    airport = models.ForeignKey(
        Airport,
        on_delete=models.CASCADE,
        help_text="Associated airport"
    )
    timestamp = models.DateTimeField(
        help_text="Timestamp of this data point"
    )
    latitude = models.FloatField(
        help_text="Latitude coordinate"
    )
    longitude = models.FloatField(
        help_text="Longitude coordinate"
    )
    passenger_count = models.IntegerField(
        validators=[MinValueValidator(0)],
        help_text="Passenger count at this location/time"
    )

    def __str__(self):
        return f"{self.airport.iata_code} - {self.timestamp} - {self.passenger_count} pax"

    class Meta:
        ordering = ['-timestamp']
        verbose_name = "Passenger Heatmap Data"
        verbose_name_plural = "Passenger Heatmap Data"
        indexes = [
            models.Index(fields=['airport', 'timestamp']),
        ]