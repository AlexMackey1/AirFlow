from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point
from django.utils import timezone  # ← Changed this line
from datetime import timedelta
from core.models import Airport, PassengerHeatmapData
import random

class Command(BaseCommand):
    help = 'Load fake passenger flow data for Dublin Airport'

    def handle(self, *args, **kwargs):
        # Clear existing data
        PassengerHeatmapData.objects.all().delete()
        
        # Create/get Dublin Airport
        dublin, created = Airport.objects.get_or_create(
            iata_code='DUB',
            defaults={
                'name': 'Dublin Airport',
                'location': Point(-6.2701, 53.4213),  # lon, lat (order matters!)
                'city': 'Dublin',
                'country': 'Ireland'
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'✓ Created {dublin.name}'))
        else:
            self.stdout.write(self.style.SUCCESS(f'✓ Using existing {dublin.name}'))
        
        # Terminal areas (rough coordinates around Dublin Airport)
        terminal_areas = [
            # Terminal 1
            {'name': 'T1 Check-in', 'lat': 53.4220, 'lon': -6.2695, 'intensity': 180},
            {'name': 'T1 Security', 'lat': 53.4218, 'lon': -6.2688, 'intensity': 150},
            {'name': 'T1 Departures', 'lat': 53.4205, 'lon': -6.2710, 'intensity': 200},
            
            # Terminal 2
            {'name': 'T2 Check-in', 'lat': 53.4200, 'lon': -6.2660, 'intensity': 160},
            {'name': 'T2 Security', 'lat': 53.4198, 'lon': -6.2655, 'intensity': 140},
            
            # Arrivals
            {'name': 'Arrivals Hall', 'lat': 53.4210, 'lon': -6.2720, 'intensity': 120},
        ]
        
        base_time = timezone.now() - timedelta(hours=2)  # ← Changed this line
        points_created = 0
        
        # Generate fake data points
        for area in terminal_areas:
            for i in range(15):  # 15 time points per area
                PassengerHeatmapData.objects.create(
                    airport=dublin,
                    timestamp=base_time + timedelta(minutes=i*8),
                    latitude=area['lat'] + random.uniform(-0.0008, 0.0008),
                    longitude=area['lon'] + random.uniform(-0.0008, 0.0008),
                    passenger_count=area['intensity'] + random.randint(-30, 30)
                )
                points_created += 1
        
        self.stdout.write(self.style.SUCCESS(f'✓ Created {points_created} heatmap data points'))
        self.stdout.write(self.style.SUCCESS('✓ Fake data loaded successfully!'))