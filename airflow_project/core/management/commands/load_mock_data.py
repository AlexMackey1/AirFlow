from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point
from django.utils import timezone
from datetime import timedelta
from core.models import Airport, PassengerHeatmapData
import random


class Command(BaseCommand):
    help = 'Load realistic fake passenger flow data for Dublin Airport demo - PRECISE COORDINATES'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING('🧹 Clearing existing data...'))
        PassengerHeatmapData.objects.all().delete()
        
        # Dublin Airport coordinates: 53.4213°N, 6.2701°W
        # Create/get Dublin Airport with correct Point(lon, lat) order
        dublin, created = Airport.objects.get_or_create(
            iata_code='DUB',
            defaults={
                'name': 'Dublin Airport',
                'location': Point(-6.2701, 53.4213, srid=4326),  # PostGIS: (longitude, latitude)
                'city': 'Dublin',
                'country': 'Ireland'
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'✓ Created {dublin.name}'))
        else:
            self.stdout.write(self.style.SUCCESS(f'✓ Using existing {dublin.name}'))
        
        # Define terminal hotspots with PRECISE Dublin Airport coordinates
      
        terminal_hotspots = [
            # ===== TERMINAL 1 (Upper/Northern Terminal) =====
                {
        'name': 'T1 Security',
        'lat': 53.42677021722075,
        'lon': -6.243525121892628,
        'base_intensity': 160,
        'spread': 0.00025,
        'points': 15
    },
    {
        'name': 'T1 Check In West',
        'lat': 53.42754383538095,
        'lon': -6.244651909621402,
        'base_intensity': 180,
        'spread': 0.00035,
        'points': 18
    },
    {
        'name': 'T1 Check In East',
        'lat': 53.42702164466883,
        'lon': -6.243743060262516,
        'base_intensity': 170,
        'spread': 0.00035,
        'points': 16
    },
    {
        'name': 'T1 Duty Free',
        'lat': 53.42697972500428,
        'lon': -6.244685941649552,
        'base_intensity': 150,
        'spread': 0.00030,
        'points': 14
    },
    {
        'name': 'Gates 300',
        'lat': 53.426274128513555,
        'lon': -6.245718703065823,
        'base_intensity': 190,
        'spread': 0.00040,
        'points': 20
    },
    {
        'name': 'Gates 200',
        'lat': 53.42855701477172,
        'lon': -6.246827744495224,
        'base_intensity': 195,
        'spread': 0.00040,
        'points': 20
    },
    {
        'name': 'Gates 100',
        'lat': 53.4305190707979,
        'lon': -6.248046447360785,
        'base_intensity': 200,
        'spread': 0.00040,
        'points': 20
    },
    {
        'name': 'Walk to 100 Gates',
        'lat': 53.429199467511765,
        'lon': -6.244280483613672,
        'base_intensity': 100,
        'spread': 0.00025,
        'points': 10
    },
        ]
        
        base_time = timezone.now() - timedelta(hours=2)
        total_points = 0
        
        self.stdout.write(self.style.WARNING('📍 Generating heatmap data points with precise coordinates...'))
        
        # Generate realistic data points for each hotspot
        for hotspot in terminal_hotspots:
            self.stdout.write(f'  → {hotspot["name"]}...')
            
            for i in range(hotspot['points']):
                # Use Gaussian distribution for realistic clustering within buildings
                lat_offset = random.gauss(0, hotspot['spread'])
                lon_offset = random.gauss(0, hotspot['spread'])
                
                # Time variation (simulate different times throughout the period)
                time_offset = random.randint(0, 120)
                
                # Passenger count with some randomness
                passenger_variation = random.randint(-40, 40)
                passenger_count = max(10, hotspot['base_intensity'] + passenger_variation)
                
                # Create data point with lat/lon (PassengerHeatmapData stores as regular floats)
                PassengerHeatmapData.objects.create(
                    airport=dublin,
                    timestamp=base_time + timedelta(minutes=time_offset),
                    latitude=hotspot['lat'] + lat_offset,
                    longitude=hotspot['lon'] + lon_offset,
                    passenger_count=passenger_count
                )
                total_points += 1
        
        # Add some "in-transit" passengers walking between terminals
        self.stdout.write('  → Adding passenger movement between terminals...')
        for i in range(12):
            # Random points along the path between T1 and T2
            PassengerHeatmapData.objects.create(
                airport=dublin,
                timestamp=base_time + timedelta(minutes=random.randint(0, 120)),
                latitude=53.42450 + random.uniform(-0.00150, 0.00150),
                longitude=-6.24650 + random.uniform(-0.00150, 0.00150),
                passenger_count=random.randint(30, 70)
            )
            total_points += 1
        
        self.stdout.write(self.style.SUCCESS(f'\n✓ Created {total_points} heatmap data points'))
        self.stdout.write(self.style.SUCCESS(f'✓ Data spans {len(terminal_hotspots)} terminal hotspots'))
        self.stdout.write(self.style.SUCCESS(f'✓ Terminal 1: 7 hotspots (upper terminal)'))
        self.stdout.write(self.style.SUCCESS(f'✓ Terminal 2: 5 hotspots (lower terminal)'))
        self.stdout.write(self.style.SUCCESS(f'✓ Shared areas: 3 hotspots'))
        self.stdout.write(self.style.SUCCESS('✓ All points confined within terminal buildings!'))
        self.stdout.write(self.style.WARNING('\n💡 Run the server and visit http://localhost:8000 to see the demo'))