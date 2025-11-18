from django.contrib.gis.db import models

class Airport(models.Model):
    """Airport model with spatial location"""
    iata_code = models.CharField(max_length=3, unique=True)
    name = models.CharField(max_length=200)
    location = models.PointField()  # PostGIS Point field
    city = models.CharField(max_length=100)
    country = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.name} ({self.iata_code})"

    class Meta:
        ordering = ['name']


class PassengerHeatmapData(models.Model):
    """Fake passenger data for heatmap visualization"""
    airport = models.ForeignKey(Airport, on_delete=models.CASCADE)
    timestamp = models.DateTimeField()
    latitude = models.FloatField()
    longitude = models.FloatField()
    passenger_count = models.IntegerField()

    def __str__(self):
        return f"{self.airport.iata_code} - {self.timestamp} - {self.passenger_count} pax"

    class Meta:
        ordering = ['-timestamp']