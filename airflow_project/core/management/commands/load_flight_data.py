"""
Author: Alexander Mackey
Student ID: C22739165
Description: Django management command to generate realistic fake flight schedules for 
testing the EstimationService algorithm. Creates a full day of flights departing from 
Dublin Airport with varied destinations, aircraft types, and times.

Run with: python manage.py load_flight_data
Optional: python manage.py load_flight_data --date 2025-11-28
"""

from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point
from django.utils import timezone
from datetime import datetime, timedelta
from core.models import Airport, AircraftType, Flight
import random


class Command(BaseCommand):
    """
    Generates realistic fake flight schedules for Dublin Airport.
    
    Creates flights across the day with:
    - Mix of short-haul and long-haul destinations
    - Varied aircraft types
    - Realistic departure time distribution
    - Some flights with missing aircraft types (to test defaults)
    """
    
    help = 'Load fake flight data for testing EstimationService'

    def add_arguments(self, parser):
        """Add command-line arguments"""
        parser.add_argument(
            '--date',
            type=str,
            help='Date for flights (YYYY-MM-DD format). Default: tomorrow',
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing flights before creating new ones',
        )

    def handle(self, *args, **options):
        """Main execution method"""
        
        # Parse date argument
        if options['date']:
            try:
                flight_date = datetime.strptime(options['date'], '%Y-%m-%d').date()
            except ValueError:
                self.stdout.write(self.style.ERROR('Invalid date format. Use YYYY-MM-DD'))
                return
        else:
            # Default to tomorrow
            flight_date = (timezone.now() + timedelta(days=1)).date()
        
        self.stdout.write(self.style.WARNING(f'Creating flights for: {flight_date}'))
        
        # Clear existing flights if requested
        if options['clear']:
            count = Flight.objects.filter(departure_time__date=flight_date).count()
            if count > 0:
                Flight.objects.filter(departure_time__date=flight_date).delete()
                self.stdout.write(self.style.WARNING(f'Cleared {count} existing flights'))
        
        # Ensure Dublin Airport exists
        dublin, created = Airport.objects.get_or_create(
            iata_code='DUB',
            defaults={
                'name': 'Dublin Airport',
                'city': 'Dublin',
                'country': 'Ireland',
                'timezone': 'Europe/Dublin',
                'location': Point(-6.2701, 53.4213, srid=4326)
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'✓ Created {dublin.name}'))
        
        # Create destination airports if they don't exist
        self._ensure_airports_exist()
        
        # Get aircraft types
        aircraft_types = list(AircraftType.objects.all())
        
        if not aircraft_types:
            self.stdout.write(
                self.style.ERROR(
                    'No aircraft types found! Please run: python manage.py load_reference_data'
                )
            )
            return
        
        # Define flight schedule template
        flight_templates = self._get_flight_templates()
        
        # Generate flights
        self.stdout.write('\n✈️  Creating Flights...\n')
        created_count = 0
        
        for template in flight_templates:
            # Build departure time
            departure_time = datetime.combine(
                flight_date, 
                datetime.strptime(template['departure_time'], '%H:%M').time()
            )
            departure_time = timezone.make_aware(departure_time)
            
            # Calculate arrival time (simplified)
            arrival_time = departure_time + timedelta(hours=template['duration_hours'])
            
            # Get destination airport
            destination = Airport.objects.get(iata_code=template['destination'])
            
            # Get aircraft type (sometimes None to test defaults)
            if template.get('aircraft_model') and random.random() > 0.1:  # 90% have aircraft assigned
                try:
                    aircraft_type = AircraftType.objects.get(model=template['aircraft_model'])
                except AircraftType.DoesNotExist:
                    aircraft_type = None
            else:
                aircraft_type = None  # 10% missing for testing defaults
            
            # Create flight
            flight = Flight.objects.create(
                flight_number=template['flight_number'],
                origin=dublin,
                destination=destination,
                departure_time=departure_time,
                arrival_time=arrival_time,
                aircraft_type=aircraft_type,
                airline=template['airline'],
                status='scheduled'
            )
            
            aircraft_display = aircraft_type.model if aircraft_type else '❓ (will use default)'
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'  ✓ {flight.flight_number:8s} → {destination.iata_code:3s} '
                    f'@ {departure_time.strftime("%H:%M")} | '
                    f'{aircraft_display:15s} | {template["airline"]}'
                )
            )
            created_count += 1
        
        # Summary
        self.stdout.write('\n' + '='*80)
        self.stdout.write(self.style.SUCCESS(f'✅ FLIGHT DATA LOADING COMPLETE'))
        self.stdout.write('='*80)
        self.stdout.write(f'Date: {flight_date}')
        self.stdout.write(f'Flights Created: {created_count}')
        self.stdout.write(f'Total Flights in DB: {Flight.objects.count()}')
        self.stdout.write('='*80)
    
    def _ensure_airports_exist(self):
        """Create common European and international destination airports"""
        
        airports = [
            # UK
            {'iata_code': 'LHR', 'name': 'London Heathrow', 'city': 'London', 'country': 'United Kingdom', 'lat': 51.4700, 'lon': -0.4543},
            {'iata_code': 'LGW', 'name': 'London Gatwick', 'city': 'London', 'country': 'United Kingdom', 'lat': 51.1537, 'lon': -0.1821},
            {'iata_code': 'MAN', 'name': 'Manchester Airport', 'city': 'Manchester', 'country': 'United Kingdom', 'lat': 53.3537, 'lon': -2.2750},
            
            # Spain
            {'iata_code': 'AGP', 'name': 'Málaga Airport', 'city': 'Málaga', 'country': 'Spain', 'lat': 36.6749, 'lon': -4.4991},
            {'iata_code': 'BCN', 'name': 'Barcelona Airport', 'city': 'Barcelona', 'country': 'Spain', 'lat': 41.2974, 'lon': 2.0833},
            {'iata_code': 'PMI', 'name': 'Palma Airport', 'city': 'Palma', 'country': 'Spain', 'lat': 39.5517, 'lon': 2.7388},
            
            # France
            {'iata_code': 'CDG', 'name': 'Paris Charles de Gaulle', 'city': 'Paris', 'country': 'France', 'lat': 49.0097, 'lon': 2.5479},
            
            # Germany
            {'iata_code': 'FRA', 'name': 'Frankfurt Airport', 'city': 'Frankfurt', 'country': 'Germany', 'lat': 50.0379, 'lon': 8.5622},
            
            # Netherlands
            {'iata_code': 'AMS', 'name': 'Amsterdam Schiphol', 'city': 'Amsterdam', 'country': 'Netherlands', 'lat': 52.3105, 'lon': 4.7683},
            
            # USA (Long-haul)
            {'iata_code': 'JFK', 'name': 'John F. Kennedy International', 'city': 'New York', 'country': 'United States', 'lat': 40.6413, 'lon': -73.7781},
            {'iata_code': 'BOS', 'name': 'Boston Logan International', 'city': 'Boston', 'country': 'United States', 'lat': 42.3656, 'lon': -71.0096},
            
            # Middle East (Long-haul)
            {'iata_code': 'DXB', 'name': 'Dubai International', 'city': 'Dubai', 'country': 'United Arab Emirates', 'lat': 25.2532, 'lon': 55.3657},
        ]
        
        for data in airports:
            Airport.objects.get_or_create(
                iata_code=data['iata_code'],
                defaults={
                    'name': data['name'],
                    'city': data['city'],
                    'country': data['country'],
                    'timezone': 'UTC',  # Simplified for now
                    'location': Point(data['lon'], data['lat'], srid=4326)
                }
            )
    
    def _get_flight_templates(self):
        """
        Define realistic flight schedule templates.
        
        Returns mix of:
        - Short-haul European flights (common narrow-body aircraft)
        - Long-haul intercontinental flights (wide-body aircraft)
        - Regional flights (turboprops)
        
        Times spread across day to test temporal distribution.
        """
        return [
            # Early Morning Departures (06:00 - 08:00)
            {'flight_number': 'EI101', 'destination': 'LHR', 'departure_time': '06:30', 'duration_hours': 1.25, 'aircraft_model': 'A320', 'airline': 'Aer Lingus'},
            {'flight_number': 'FR201', 'destination': 'AGP', 'departure_time': '06:45', 'duration_hours': 3.0, 'aircraft_model': 'B737-800', 'airline': 'Ryanair'},
            {'flight_number': 'EI105', 'destination': 'CDG', 'departure_time': '07:15', 'duration_hours': 1.75, 'aircraft_model': 'A320', 'airline': 'Aer Lingus'},
            {'flight_number': 'BA831', 'destination': 'LGW', 'departure_time': '07:40', 'duration_hours': 1.25, 'aircraft_model': 'A319', 'airline': 'British Airways'},
            
            # Morning Rush (08:00 - 10:00)
            {'flight_number': 'EI109', 'destination': 'AMS', 'departure_time': '08:10', 'duration_hours': 1.5, 'aircraft_model': 'A321', 'airline': 'Aer Lingus'},
            {'flight_number': 'FR305', 'destination': 'BCN', 'departure_time': '08:30', 'duration_hours': 2.5, 'aircraft_model': 'B737-800', 'airline': 'Ryanair'},
            {'flight_number': 'EI103', 'destination': 'LHR', 'departure_time': '08:50', 'duration_hours': 1.25, 'aircraft_model': 'A320', 'airline': 'Aer Lingus'},
            {'flight_number': 'LH977', 'destination': 'FRA', 'departure_time': '09:15', 'duration_hours': 2.0, 'aircraft_model': 'A321', 'airline': 'Lufthansa'},
            {'flight_number': 'FR401', 'destination': 'PMI', 'departure_time': '09:45', 'duration_hours': 2.75, 'aircraft_model': 'B737-800', 'airline': 'Ryanair'},
            
            # Mid-Morning (10:00 - 12:00)
            {'flight_number': 'EI107', 'destination': 'MAN', 'departure_time': '10:20', 'duration_hours': 1.0, 'aircraft_model': 'ATR-72', 'airline': 'Aer Lingus'},
            {'flight_number': 'BA835', 'destination': 'LHR', 'departure_time': '10:45', 'duration_hours': 1.25, 'aircraft_model': 'A320', 'airline': 'British Airways'},
            {'flight_number': 'EI111', 'destination': 'JFK', 'departure_time': '11:00', 'duration_hours': 8.0, 'aircraft_model': 'A330-300', 'airline': 'Aer Lingus'},
            {'flight_number': 'FR501', 'destination': 'AGP', 'departure_time': '11:30', 'duration_hours': 3.0, 'aircraft_model': 'B737-800', 'airline': 'Ryanair'},
            
            # Midday (12:00 - 14:00)
            {'flight_number': 'EI113', 'destination': 'CDG', 'departure_time': '12:15', 'duration_hours': 1.75, 'aircraft_model': 'A320', 'airline': 'Aer Lingus'},
            {'flight_number': 'EI115', 'destination': 'BOS', 'departure_time': '12:45', 'duration_hours': 7.5, 'aircraft_model': 'A330-300', 'airline': 'Aer Lingus'},
            {'flight_number': 'FR601', 'destination': 'BCN', 'departure_time': '13:10', 'duration_hours': 2.5, 'aircraft_model': 'B737-800', 'airline': 'Ryanair'},
            {'flight_number': 'BA839', 'destination': 'LGW', 'departure_time': '13:35', 'duration_hours': 1.25, 'aircraft_model': 'A319', 'airline': 'British Airways'},
            
            # Afternoon (14:00 - 16:00)
            {'flight_number': 'EI117', 'destination': 'AMS', 'departure_time': '14:00', 'duration_hours': 1.5, 'aircraft_model': 'A321', 'airline': 'Aer Lingus'},
            {'flight_number': 'FR701', 'destination': 'PMI', 'departure_time': '14:30', 'duration_hours': 2.75, 'aircraft_model': 'B737-800', 'airline': 'Ryanair'},
            {'flight_number': 'EI119', 'destination': 'LHR', 'departure_time': '15:00', 'duration_hours': 1.25, 'aircraft_model': 'A320', 'airline': 'Aer Lingus'},
            {'flight_number': 'EK161', 'destination': 'DXB', 'departure_time': '15:30', 'duration_hours': 7.0, 'aircraft_model': 'B777-300ER', 'airline': 'Emirates'},
            
            # Evening (16:00 - 18:00)
            {'flight_number': 'FR801', 'destination': 'AGP', 'departure_time': '16:15', 'duration_hours': 3.0, 'aircraft_model': 'B737-800', 'airline': 'Ryanair'},
            {'flight_number': 'EI121', 'destination': 'FRA', 'departure_time': '16:45', 'duration_hours': 2.0, 'aircraft_model': 'A321', 'airline': 'Aer Lingus'},
            {'flight_number': 'BA843', 'destination': 'LHR', 'departure_time': '17:10', 'duration_hours': 1.25, 'aircraft_model': 'A320', 'airline': 'British Airways'},
            {'flight_number': 'FR901', 'destination': 'BCN', 'departure_time': '17:40', 'duration_hours': 2.5, 'aircraft_model': 'B737-800', 'airline': 'Ryanair'},
            
            # Late Evening (18:00 - 20:00)
            {'flight_number': 'EI123', 'destination': 'CDG', 'departure_time': '18:15', 'duration_hours': 1.75, 'aircraft_model': 'A320', 'airline': 'Aer Lingus'},
            {'flight_number': 'EI125', 'destination': 'MAN', 'departure_time': '18:45', 'duration_hours': 1.0, 'aircraft_model': 'ATR-72', 'airline': 'Aer Lingus'},
            {'flight_number': 'FR1001', 'destination': 'PMI', 'departure_time': '19:10', 'duration_hours': 2.75, 'aircraft_model': 'B737-800', 'airline': 'Ryanair'},
            {'flight_number': 'EI127', 'destination': 'LHR', 'departure_time': '19:45', 'duration_hours': 1.25, 'aircraft_model': 'A320', 'airline': 'Aer Lingus'},
            
            # Night (20:00 - 22:00)
            {'flight_number': 'BA847', 'destination': 'LGW', 'departure_time': '20:15', 'duration_hours': 1.25, 'aircraft_model': 'A319', 'airline': 'British Airways'},
            {'flight_number': 'FR1101', 'destination': 'AGP', 'departure_time': '20:45', 'duration_hours': 3.0, 'aircraft_model': 'B737-800', 'airline': 'Ryanair'},
            {'flight_number': 'EI129', 'destination': 'AMS', 'departure_time': '21:10', 'duration_hours': 1.5, 'aircraft_model': 'A321', 'airline': 'Aer Lingus'},
        ]