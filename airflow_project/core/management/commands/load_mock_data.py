from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point
from django.utils import timezone
from datetime import timedelta
from core.models import Airport, PassengerHeatmapData
import random


class Command(BaseCommand):
    help = 'Load T1 data - MAXIMUM COLOR VARIETY across full spectrum'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING('🧹 Clearing existing data...'))
        PassengerHeatmapData.objects.all().delete()
        
        dublin, created = Airport.objects.get_or_create(
            iata_code='DUB',
            defaults={
                'name': 'Dublin Airport',
                'location': Point(-6.2701, 53.4213, srid=4326),
                'city': 'Dublin',
                'country': 'Ireland'
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'✓ Created {dublin.name}'))
        else:
            self.stdout.write(self.style.SUCCESS(f'✓ Using existing {dublin.name}'))
        
        # TERMINAL 1 - WIDE INTENSITY VARIATION (40-200 range)
        terminal_hotspots = [
            # === SECURITY (Low-Medium - blue/green/yellow) ===
            {
                'name': 'T1 Security Entrance',
                'lat': 53.42680848824327,
                'lon': -6.243421529894776,
                'base_intensity': 80,  # Green/yellow
                'spread_lat': 0.00001,
                'spread_lon': 0.00005,
                'points': 30
            },
            {
                'name': 'T1 Security Exit',
                'lat': 53.42644593488568,
                'lon': -6.243911878984689,
                'base_intensity': 60,  # Green
                'spread_lat': 0.00001,
                'spread_lon': 0.00005,
                'points': 25
            },
            
            # === CHECK-IN (High - orange/red) ===
            {
                'name': 'T1 Check In West',
                'lat': 53.42754383538095,
                'lon': -6.244651909621402,
                'base_intensity': 170,  # Orange/red
                'spread_lat': 0.00002,
                'spread_lon': 0.00010,
                'points': 35
            },
            {
                'name': 'T1 Check In East',
                'lat': 53.42702164466883,
                'lon': -6.243743060262516,
                'base_intensity': 160,  # Orange
                'spread_lat': 0.00002,
                'spread_lon': 0.00010,
                'points': 32
            },
            
            # === RETAIL (Very Low - blue/cyan) ===
            {
                'name': 'T1 Duty Free West',
                'lat': 53.426974072315154,
                'lon': -6.244578723713256,
                'base_intensity': 45,  # Blue/cyan
                'spread_lat': 0.00002,
                'spread_lon': 0.00005,
                'points': 25
            },
            {
                'name': 'T1 Duty Free East',
                'lat': 53.42732344790114,
                'lon': -6.245203317879837,
                'base_intensity': 50,  # Cyan/green
                'spread_lat': 0.00002,
                'spread_lon': 0.00005,
                'points': 22
            },
            
            # === FOOD (Medium - yellow) ===
            {
                'name': 'T1 FoodHall (Starbucks etc)',
                'lat': 53.42802374541869,
                'lon': -6.24568116836029,
                'base_intensity': 100,  # Yellow
                'spread_lat': 0.00003,
                'spread_lon': 0.00006,
                'points': 28
            },
            
            # === GATES 300 (Medium-Low - green/yellow) ===
            {
                'name': 'Gates 301-307 East',
                'lat': 53.426274128513555,
                'lon': -6.245718703065823,
                'base_intensity': 90,  # Green/yellow
                'spread_lat': 0.00003,
                'spread_lon': 0.00005,
                'points': 30
            },
            {
                'name': 'Gates 301-307 West',
                'lat': 53.42612810625835,
                'lon': -6.246139226505242,
                'base_intensity': 85,  # Green
                'spread_lat': 0.00003,
                'spread_lon': 0.00005,
                'points': 28
            },
            {
                'name': 'Gates 301-307 Walkway',
                'lat': 53.42665899009382,
                'lon': -6.245176024957214,
                'base_intensity': 40,  # Blue
                'spread_lat': 0.00004,
                'spread_lon': 0.00002,
                'points': 18
            },
            
            # === GATES 200 (High - orange/red) ===
            {
                'name': 'Gates 201-216 East',
                'lat': 53.42855701477172,
                'lon': -6.246827744495224,
                'base_intensity': 180,  # Red/orange
                'spread_lat': 0.00004,
                'spread_lon': 0.00006,
                'points': 35
            },
            {
                'name': 'Gates 201-216 Central',
                'lat': 53.428411805342485,
                'lon': -6.247185659255368,
                'base_intensity': 195,  # Red (busiest!)
                'spread_lat': 0.00004,
                'spread_lon': 0.00006,
                'points': 38
            },
            {
                'name': 'Gates 201-216 West',
                'lat': 53.42802202897417,
                'lon': -6.247940167155616,
                'base_intensity': 140,  # Yellow/orange
                'spread_lat': 0.00004,
                'spread_lon': 0.00006,
                'points': 32
            },
            {
                'name': 'Gates 217-220',
                'lat': 53.42927503966373,
                'lon': -6.246226471021615,
                'base_intensity': 110,  # Yellow
                'spread_lat': 0.00002,
                'spread_lon': 0.00004,
                'points': 24
            },
            
            # === GATES 100 (Medium-High - yellow/orange/red mix) ===
            {
                'name': 'Gates 102-105',
                'lat': 53.43049107334048,
                'lon': -6.2474374322065644,
                'base_intensity': 150,  # Orange
                'spread_lat': 0.00003,
                'spread_lon': 0.00005,
                'points': 32
            },
            {
                'name': 'Gates 106-109',
                'lat': 53.43054823093274,
                'lon': -6.248903012307744,
                'base_intensity': 130,  # Yellow/orange
                'spread_lat': 0.00003,
                'spread_lon': 0.00005,
                'points': 30
            },
            {
                'name': 'Gates 110-119',
                'lat': 53.43065822299713,
                'lon': -6.250207347795571,
                'base_intensity': 120,  # Yellow
                'spread_lat': 0.00004,
                'spread_lon': 0.00012,  # Wide west spread
                'points': 40
            },
            
        ]
        
        # CONNECTIONS - Varied intensities too
        connections = [
            {
                'name': 'Connection: Check-in West to East',
                'start': [53.42754383538095, -6.244651909621402],
                'end': [53.42702164466883, -6.243743060262516],
                'base_intensity': 175,  # Red/orange (busy flow)
                'spread_lat': 0.00001,
                'spread_lon': 0.00002,
                'points': 40
            },
            {
                'name': 'Connection: Security Entrance to Exit',
                'start': [53.42680848824327, -6.243421529894776],
                'end': [53.42644593488568, -6.243911878984689],
                'base_intensity': 70,  # Green (controlled flow)
                'spread_lat': 0.00001,
                'spread_lon': 0.00002,
                'points': 45
            },
            {
                'name': 'Connection: Duty Free East to Food Hall',
                'start': [53.42732344790114, -6.245203317879837],
                'end': [53.42802374541869, -6.24568116836029],
                'base_intensity': 95,  # Yellow (shopping flow)
                'spread_lat': 0.00002,
                'spread_lon': 0.00002,
                'points': 35
            },
            {
                'name': 'Connection: Gates 300 Walkway to East',
                'start': [53.42665899009382, -6.245176024957214],
                'end': [53.426274128513555, -6.245718703065823],
                'base_intensity': 105,  # Yellow
                'spread_lat': 0.00002,
                'spread_lon': 0.00002,
                'points': 30
            },
            {
                'name': 'Connection: Gates 300 Walkway to West',
                'start': [53.42665899009382, -6.245176024957214],
                'end': [53.42612810625835, -6.246139226505242],
                'base_intensity': 100,  # Yellow
                'spread_lat': 0.00002,
                'spread_lon': 0.00002,
                'points': 30
            },
            {
                'name': 'Connection: Gates 201-216 East to Central',
                'start': [53.42855701477172, -6.246827744495224],
                'end': [53.428411805342485, -6.247185659255368],
                'base_intensity': 190,  # Red (very busy!)
                'spread_lat': 0.00002,
                'spread_lon': 0.00002,
                'points': 35
            },
            {
                'name': 'Connection: Gates 201-216 Central to West',
                'start': [53.428411805342485, -6.247185659255368],
                'end': [53.42802202897417, -6.247940167155616],
                'base_intensity': 165,  # Orange (busy)
                'spread_lat': 0.00002,
                'spread_lon': 0.00002,
                'points': 35
            },
            {
                'name': 'Connection: Gates 102-105 to 106-109',
                'start': [53.43049107334048, -6.2474374322065644],
                'end': [53.43054823093274, -6.248903012307744],
                'base_intensity': 140,  # Orange
                'spread_lat': 0.00002,
                'spread_lon': 0.00002,
                'points': 30
            },
            {
                'name': 'Connection: Gates 106-109 to 110-119',
                'start': [53.43054823093274, -6.248903012307744],
                'end': [53.43065822299713, -6.250207347795571],
                'base_intensity': 125,  # Yellow
                'spread_lat': 0.00002,
                'spread_lon': 0.00002,
                'points': 30
            },
        ]
        
        base_time = timezone.now() - timedelta(hours=2)
        total_points = 0
        
        self.stdout.write(self.style.WARNING('📍 Generating hotspots with WIDE color variety...'))
        
        for hotspot in terminal_hotspots:
            self.stdout.write(f'  → {hotspot["name"]}...')
            
            for i in range(hotspot['points']):
                lat_offset = random.gauss(0, hotspot['spread_lat'])
                lon_offset = random.gauss(0, hotspot['spread_lon'])
                
                time_offset = random.randint(0, 120)
                # Larger variation for more color diversity
                passenger_variation = random.randint(-25, 40)
                passenger_count = max(10, hotspot['base_intensity'] + passenger_variation)
                
                PassengerHeatmapData.objects.create(
                    airport=dublin,
                    timestamp=base_time + timedelta(minutes=time_offset),
                    latitude=hotspot['lat'] + lat_offset,
                    longitude=hotspot['lon'] + lon_offset,
                    passenger_count=passenger_count
                )
                total_points += 1
        
        self.stdout.write(self.style.WARNING('\n🔗 Generating connections with varied colors...'))
        
        for connection in connections:
            self.stdout.write(f'  → {connection["name"]}...')
            
            start_lat, start_lon = connection['start']
            end_lat, end_lon = connection['end']
            num_points = connection['points']
            
            for i in range(num_points):
                progress = i / (num_points - 1) if num_points > 1 else 0.5
                
                lat = start_lat + (end_lat - start_lat) * progress
                lon = start_lon + (end_lon - start_lon) * progress
                
                lat_offset = random.gauss(0, connection['spread_lat'])
                lon_offset = random.gauss(0, connection['spread_lon'])
                
                time_offset = random.randint(0, 120)
                passenger_variation = random.randint(-20, 30)
                passenger_count = max(10, connection['base_intensity'] + passenger_variation)
                
                PassengerHeatmapData.objects.create(
                    airport=dublin,
                    timestamp=base_time + timedelta(minutes=time_offset),
                    latitude=lat + lat_offset,
                    longitude=lon + lon_offset,
                    passenger_count=passenger_count
                )
                total_points += 1
        
        self.stdout.write(self.style.SUCCESS(f'\n✓ Created {total_points} total data points'))
        self.stdout.write(self.style.SUCCESS(f'✓ Main hotspots: {len(terminal_hotspots)} areas'))
        self.stdout.write(self.style.SUCCESS(f'✓ Connections: {len(connections)} paths'))
        self.stdout.write(self.style.SUCCESS('\n🎨 FULL COLOR SPECTRUM:'))
        self.stdout.write(self.style.SUCCESS('     🔵 Blue (35-50): Walkways, Gates 300 Walkway'))
        self.stdout.write(self.style.SUCCESS('     🟦 Cyan (50-70): Duty Free, Security Exit'))
        self.stdout.write(self.style.SUCCESS('     🟢 Green (70-95): Security, Gates 300'))
        self.stdout.write(self.style.SUCCESS('     🟡 Yellow (100-130): Food Hall, Gates 100, some connections'))
        self.stdout.write(self.style.SUCCESS('     🟠 Orange (140-170): Check-in, Gates 200 West, Gates 102-105'))
        self.stdout.write(self.style.SUCCESS('     🔴 Red (175-195): Check-in connection, Gates 200 Central+East'))
        self.stdout.write(self.style.WARNING('\n💡 Total: ~890 points with MAXIMUM color variety!'))
        self.stdout.write(self.style.WARNING('💡 Range: 35-195 (full spectrum coverage!)'))