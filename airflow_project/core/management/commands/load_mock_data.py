"""
Author: Alexander Mackey
Student ID: C22739165
Description: Django management command that generates simulated passenger data for Terminal 1. 
Creates 890 realistic data points across 21 hotspots and 9 connection paths using Normal 
distribution to model passenger density for heatmap visualization.
"""

from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point
from django.utils import timezone
from datetime import timedelta
from core.models import Airport, PassengerHeatmapData
import random


class Command(BaseCommand):
    """
    Management command to populate database with simulated Terminal 1 passenger data.
    
    Run with: python manage.py load_mock_data
    
    Generates approximately 890 data points distributed across:
    - 17 terminal hotspots (check-in, security, gates, food, retail)
    - 9 connection pathways between hotspots
    
    Uses Normal distribution to create realistic clustering around locations.
    """
    
    help = 'Load T1 data'

    def handle(self, *args, **kwargs):
        """
        Main execution method called when command is run.
        
        Steps:
        1. Clear existing passenger data
        2. Get or create Dublin Airport
        3. Generate hotspot data points
        4. Generate connection pathway data points
        5. Display summary statistics
        """
        
        # Delete all existing passenger data to start fresh
        self.stdout.write(self.style.WARNING('Clearing existing data...'))
        PassengerHeatmapData.objects.all().delete()
        
        # Get or create Dublin Airport in database
        # get_or_create returns (object, created) tuple
        dublin, created = Airport.objects.get_or_create(
            iata_code='DUB',
            defaults={
                'name': 'Dublin Airport',
                # Point takes (longitude, latitude)
                'location': Point(-6.2701, 53.4213, srid=4326),
                'city': 'Dublin',
                'country': 'Ireland'
            }
        )
        
        # Display appropriate message based on whether airport was created or already existed
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created {dublin.name}'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Using existing {dublin.name}'))
        
        # Define Terminal 1 hotspot locations with metadata
        # Each hotspot will generate multiple data points around its center using Normal distribution
        terminal_hotspots = [
            # SECURITY AREAS 
            {
                'name': 'T1 Security Entrance',
                'lat': 53.42680848824327,       # Center latitude coordinate
                'lon': -6.243421529894776,      # Center longitude coordinate
                'base_intensity': 80,           # Base passenger count for this area
                'spread_lat': 0.00001,          # Vertical scatter (smaller = tighter)
                'spread_lon': 0.00005,          # Horizontal scatter (larger = wider)
                'points': 30                    # Number of data points to generate
            },
            {
                'name': 'T1 Security Exit',
                'lat': 53.42644593488568,
                'lon': -6.243911878984689,
                'base_intensity': 60,
                'spread_lat': 0.00001,
                'spread_lon': 0.00005,
                'points': 25
            },
            
            # CHECK-IN AREAS 
            {
                'name': 'T1 Check In West',
                'lat': 53.42754383538095,
                'lon': -6.244651909621402,
                'base_intensity': 170,          
                'spread_lat': 0.00002,
                'spread_lon': 0.00010,          
                'points': 35
            },
            {
                'name': 'T1 Check In East',
                'lat': 53.42702164466883,
                'lon': -6.243743060262516,
                'base_intensity': 160,
                'spread_lat': 0.00002,
                'spread_lon': 0.00010,
                'points': 32
            },
            
            # RETAIL AREAS
            {
                'name': 'T1 Duty Free West',
                'lat': 53.426974072315154,
                'lon': -6.244578723713256,
                'base_intensity': 45,
                'spread_lat': 0.00002,
                'spread_lon': 0.00005,
                'points': 25
            },
            {
                'name': 'T1 Duty Free East',
                'lat': 53.42732344790114,
                'lon': -6.245203317879837,
                'base_intensity': 50,
                'spread_lat': 0.00002,
                'spread_lon': 0.00005,
                'points': 22
            },
            
            # FOOD COURT 
            {
                'name': 'T1 FoodHall (Starbucks etc)',
                'lat': 53.42802374541869,
                'lon': -6.24568116836029,
                'base_intensity': 100,
                'spread_lat': 0.00003,
                'spread_lon': 0.00006,
                'points': 28
            },
            
            # GATES 300 SERIES
            {
                'name': 'Gates 301-307 East',
                'lat': 53.426274128513555,
                'lon': -6.245718703065823,
                'base_intensity': 90,
                'spread_lat': 0.00003,
                'spread_lon': 0.00005,
                'points': 30
            },
            {
                'name': 'Gates 301-307 West',
                'lat': 53.42612810625835,
                'lon': -6.246139226505242,
                'base_intensity': 85,
                'spread_lat': 0.00003,
                'spread_lon': 0.00005,
                'points': 28
            },
            {
                'name': 'Gates 301-307 Walkway',
                'lat': 53.42665899009382,
                'lon': -6.245176024957214,
                'base_intensity': 40,
                'spread_lat': 0.00004,
                'spread_lon': 0.00002,       
                'points': 18
            },
            
            # GATES 200 SERIES
            {
                'name': 'Gates 201-216 East',
                'lat': 53.42855701477172,
                'lon': -6.246827744495224,
                'base_intensity': 180,
                'spread_lat': 0.00004,
                'spread_lon': 0.00006,
                'points': 35
            },
            {
                'name': 'Gates 201-216 Central',
                'lat': 53.428411805342485,
                'lon': -6.247185659255368,
                'base_intensity': 195,          
                'spread_lat': 0.00004,
                'spread_lon': 0.00006,
                'points': 38
            },
            {
                'name': 'Gates 201-216 West',
                'lat': 53.42802202897417,
                'lon': -6.247940167155616,
                'base_intensity': 140,
                'spread_lat': 0.00004,
                'spread_lon': 0.00006,
                'points': 32
            },
            {
                'name': 'Gates 217-220',
                'lat': 53.42927503966373,
                'lon': -6.246226471021615,
                'base_intensity': 110,
                'spread_lat': 0.00002,
                'spread_lon': 0.00004,
                'points': 24
            },
            
            # GATES 100 SERIES - Medium-high passenger counts
            {
                'name': 'Gates 102-105',
                'lat': 53.43049107334048,
                'lon': -6.2474374322065644,
                'base_intensity': 150,
                'spread_lat': 0.00003,
                'spread_lon': 0.00005,
                'points': 32
            },
            {
                'name': 'Gates 106-109',
                'lat': 53.43054823093274,
                'lon': -6.248903012307744,
                'base_intensity': 130,
                'spread_lat': 0.00003,
                'spread_lon': 0.00005,
                'points': 30
            },
            {
                'name': 'Gates 110-119',
                'lat': 53.43065822299713,
                'lon': -6.250207347795571,
                'base_intensity': 120,
                'spread_lat': 0.00004,
                'spread_lon': 0.00012,          # Wide west spread for long gate corridor
                'points': 40
            },
        ]
        
        # Define connection pathways between hotspots
        # These represent passenger flow corridors connecting different areas
        connections = [
            {
                'name': 'Connection: Check-in West to East',
                'start': [53.42754383538095, -6.244651909621402],    # Starting coordinates
                'end': [53.42702164466883, -6.243743060262516],      # Ending coordinates
                'base_intensity': 175,                               # High flow = busy corridor
                'spread_lat': 0.00001,
                'spread_lon': 0.00002,
                'points': 40                              
            },
            {
                'name': 'Connection: Security Entrance to Exit',
                'start': [53.42680848824327, -6.243421529894776],
                'end': [53.42644593488568, -6.243911878984689],
                'base_intensity': 70,                           
                'spread_lat': 0.00001,
                'spread_lon': 0.00002,
                'points': 45
            },
            {
                'name': 'Connection: Duty Free East to Food Hall',
                'start': [53.42732344790114, -6.245203317879837],
                'end': [53.42802374541869, -6.24568116836029],
                'base_intensity': 95,
                'spread_lat': 0.00002,
                'spread_lon': 0.00002,
                'points': 35
            },
            {
                'name': 'Connection: Gates 300 Walkway to East',
                'start': [53.42665899009382, -6.245176024957214],
                'end': [53.426274128513555, -6.245718703065823],
                'base_intensity': 105,
                'spread_lat': 0.00002,
                'spread_lon': 0.00002,
                'points': 30
            },
            {
                'name': 'Connection: Gates 300 Walkway to West',
                'start': [53.42665899009382, -6.245176024957214],
                'end': [53.42612810625835, -6.246139226505242],
                'base_intensity': 100,
                'spread_lat': 0.00002,
                'spread_lon': 0.00002,
                'points': 30
            },
            {
                'name': 'Connection: Gates 201-216 East to Central',
                'start': [53.42855701477172, -6.246827744495224],
                'end': [53.428411805342485, -6.247185659255368],
                'base_intensity': 190,                               
                'spread_lat': 0.00002,
                'spread_lon': 0.00002,
                'points': 35
            },
            {
                'name': 'Connection: Gates 201-216 Central to West',
                'start': [53.428411805342485, -6.247185659255368],
                'end': [53.42802202897417, -6.247940167155616],
                'base_intensity': 165,
                'spread_lat': 0.00002,
                'spread_lon': 0.00002,
                'points': 35
            },
            {
                'name': 'Connection: Gates 102-105 to 106-109',
                'start': [53.43049107334048, -6.2474374322065644],
                'end': [53.43054823093274, -6.248903012307744],
                'base_intensity': 140,
                'spread_lat': 0.00002,
                'spread_lon': 0.00002,
                'points': 30
            },
            {
                'name': 'Connection: Gates 106-109 to 110-119',
                'start': [53.43054823093274, -6.248903012307744],
                'end': [53.43065822299713, -6.250207347795571],
                'base_intensity': 125,
                'spread_lat': 0.00002,
                'spread_lon': 0.00002,
                'points': 30
            },
        ]
        
        # Base timestamp for all data points (2 hours ago)
        base_time = timezone.now() - timedelta(hours=2)
        total_points = 0
        
        # Generate data points for each hotspot
        for hotspot in terminal_hotspots:
            self.stdout.write(f'  -> {hotspot["name"]}...')
            
            # Create specified number of points for this hotspot
            for i in range(hotspot['points']):
                # Add Gaussian-distributed random offset to create realistic scatter
                # random.gauss(mean=0, std_dev=spread) creates bell curve distribution
                # 68% of points within +/- spread, 95% within +/- 2*spread
                lat_offset = random.gauss(0, hotspot['spread_lat'])
                lon_offset = random.gauss(0, hotspot['spread_lon'])
                
                # Random time variation (0-120 minutes from base time)
                time_offset = random.randint(0, 120)
                
                # Add random variation to passenger count for color diversity
                # Larger variation (-25 to +40) creates more color variety
                passenger_variation = random.randint(-25, 40)
                # Ensure passenger count never goes below 10
                passenger_count = max(10, hotspot['base_intensity'] + passenger_variation)
                
                # Create database record for this data point
                PassengerHeatmapData.objects.create(
                    airport=dublin,
                    timestamp=base_time + timedelta(minutes=time_offset),
                    latitude=hotspot['lat'] + lat_offset,
                    longitude=hotspot['lon'] + lon_offset,
                    passenger_count=passenger_count
                )
                total_points += 1
        
        # Generate data points along connection pathways
        for connection in connections:
            self.stdout.write(f'  -> {connection["name"]}...')
            
            # Extract start and end coordinates
            start_lat, start_lon = connection['start']
            end_lat, end_lon = connection['end']
            num_points = connection['points']
            
            # Create points distributed evenly along the line from start to end
            for i in range(num_points):
                # Calculate progress along the path (0.0 to 1.0)
                # i=0 gives 0.0 (start), i=num_points-1 gives 1.0 (end)
                progress = i / (num_points - 1) if num_points > 1 else 0.5
                
                # Linear interpolation between start and end coordinates
                # At progress=0.5, this gives the midpoint
                lat = start_lat + (end_lat - start_lat) * progress
                lon = start_lon + (end_lon - start_lon) * progress
                
                # Add small random offset for natural appearance
                lat_offset = random.gauss(0, connection['spread_lat'])
                lon_offset = random.gauss(0, connection['spread_lon'])
                
                # Time and passenger count variations
                time_offset = random.randint(0, 120)
                passenger_variation = random.randint(-20, 30)
                passenger_count = max(10, connection['base_intensity'] + passenger_variation)
                
                # Create database record for this connection point
                PassengerHeatmapData.objects.create(
                    airport=dublin,
                    timestamp=base_time + timedelta(minutes=time_offset),
                    latitude=lat + lat_offset,
                    longitude=lon + lon_offset,
                    passenger_count=passenger_count
                )
                total_points += 1
        
        # Display summary statistics
        self.stdout.write(self.style.SUCCESS(f'\nCreated {total_points} total data points'))
   