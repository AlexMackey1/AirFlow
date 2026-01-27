"""
Author: Alexander Mackey
Student ID: C22739165
Description: Django management command to populate reference data for aircraft types and 
load factors. Creates common aircraft configurations and IATA-based load factor defaults
as specified in interim report Chapter 3.5.2 (Core Algorithm).

Run with: python manage.py load_reference_data
"""

from django.core.management.base import BaseCommand
from core.models import AircraftType, LoadFactor


class Command(BaseCommand):
    """
    Loads aircraft types and load factors into database.
    
    Aircraft Types: Based on common aircraft at Irish airports
    Load Factors: Based on IATA 2024-2025 global outlook (84% short-haul, 82% long-haul)
    """
    
    help = 'Load aircraft types and load factors reference data'

    def handle(self, *args, **kwargs):
        """Main execution method"""
        
        self.stdout.write(self.style.WARNING('Loading reference data...'))
        
        # ======================
        # AIRCRAFT TYPES
        # ======================
        
        self.stdout.write('\n📋 Creating Aircraft Types...')
        
        aircraft_data = [
            # Short-haul narrow-body aircraft (European routes)
            {
                'model': 'A320',
                'manufacturer': 'Airbus',
                'total_capacity': 180,
                'economy_capacity': 168,
                'business_capacity': 12,
                'first_class_capacity': 0
            },
            {
                'model': 'A321',
                'manufacturer': 'Airbus',
                'total_capacity': 220,
                'economy_capacity': 204,
                'business_capacity': 16,
                'first_class_capacity': 0
            },
            {
                'model': 'B737-800',
                'manufacturer': 'Boeing',
                'total_capacity': 189,
                'economy_capacity': 174,
                'business_capacity': 15,
                'first_class_capacity': 0
            },
            {
                'model': 'B737 MAX 8',
                'manufacturer': 'Boeing',
                'total_capacity': 178,
                'economy_capacity': 162,
                'business_capacity': 16,
                'first_class_capacity': 0
            },
            
            # Long-haul wide-body aircraft (Intercontinental routes)
            {
                'model': 'B777-300ER',
                'manufacturer': 'Boeing',
                'total_capacity': 350,
                'economy_capacity': 286,
                'business_capacity': 52,
                'first_class_capacity': 12
            },
            {
                'model': 'B777-200',
                'manufacturer': 'Boeing',
                'total_capacity': 300,
                'economy_capacity': 250,
                'business_capacity': 42,
                'first_class_capacity': 8
            },
            {
                'model': 'A330-300',
                'manufacturer': 'Airbus',
                'total_capacity': 330,
                'economy_capacity': 277,
                'business_capacity': 45,
                'first_class_capacity': 8
            },
            {
                'model': 'B787-9',
                'manufacturer': 'Boeing',
                'total_capacity': 296,
                'economy_capacity': 246,
                'business_capacity': 40,
                'first_class_capacity': 10
            },
            
            # Regional turboprops (Short domestic/European routes)
            {
                'model': 'ATR-72',
                'manufacturer': 'ATR',
                'total_capacity': 72,
                'economy_capacity': 72,
                'business_capacity': 0,
                'first_class_capacity': 0
            },
            {
                'model': 'ATR-42',
                'manufacturer': 'ATR',
                'total_capacity': 48,
                'economy_capacity': 48,
                'business_capacity': 0,
                'first_class_capacity': 0
            },
            
            # Additional common types
            {
                'model': 'A319',
                'manufacturer': 'Airbus',
                'total_capacity': 156,
                'economy_capacity': 144,
                'business_capacity': 12,
                'first_class_capacity': 0
            },
            {
                'model': 'E190',
                'manufacturer': 'Embraer',
                'total_capacity': 100,
                'economy_capacity': 94,
                'business_capacity': 6,
                'first_class_capacity': 0
            },
        ]
        
        created_count = 0
        updated_count = 0
        
        for data in aircraft_data:
            aircraft, created = AircraftType.objects.update_or_create(
                model=data['model'],
                defaults=data
            )
            
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'  ✓ Created: {aircraft.manufacturer} {aircraft.model} ({aircraft.total_capacity} seats)')
                )
                created_count += 1
            else:
                self.stdout.write(
                    self.style.WARNING(f'  ↻ Updated: {aircraft.manufacturer} {aircraft.model} ({aircraft.total_capacity} seats)')
                )
                updated_count += 1
        
        self.stdout.write(
            self.style.SUCCESS(f'\n✅ Aircraft Types: {created_count} created, {updated_count} updated')
        )
        
        # ======================
        # LOAD FACTORS
        # ======================
        
        self.stdout.write('\n📊 Creating Load Factors...')
        
        loadfactor_data = [
            # Default load factors based on IATA 2024-2025 global outlook
            {
                'route_type': 'short_haul',
                'season': 'all_year',
                'airline': '',  # Default for all airlines
                'percentage': 0.84,  # 84%
                'is_default': True,
                'source': 'IATA 2024-2025 Global Outlook'
            },
            {
                'route_type': 'long_haul',
                'season': 'all_year',
                'airline': '',
                'percentage': 0.82,  # 82%
                'is_default': True,
                'source': 'IATA 2024-2025 Global Outlook'
            },
            {
                'route_type': 'regional',
                'season': 'all_year',
                'airline': '',
                'percentage': 0.78,  # 78% (typically lower for small aircraft)
                'is_default': True,
                'source': 'IATA 2024-2025 Global Outlook'
            },
            
            # Seasonal variations (for future use)
            {
                'route_type': 'short_haul',
                'season': 'summer',
                'airline': '',
                'percentage': 0.87,  # Higher in summer
                'is_default': False,
                'source': 'IATA Seasonal Variations'
            },
            {
                'route_type': 'short_haul',
                'season': 'winter',
                'airline': '',
                'percentage': 0.81,  # Lower in winter
                'is_default': False,
                'source': 'IATA Seasonal Variations'
            },
            {
                'route_type': 'long_haul',
                'season': 'summer',
                'airline': '',
                'percentage': 0.85,
                'is_default': False,
                'source': 'IATA Seasonal Variations'
            },
            {
                'route_type': 'long_haul',
                'season': 'winter',
                'airline': '',
                'percentage': 0.79,
                'is_default': False,
                'source': 'IATA Seasonal Variations'
            },
            
            # Example airline-specific (can be expanded later)
            {
                'route_type': 'short_haul',
                'season': 'all_year',
                'airline': 'Ryanair',
                'percentage': 0.95,  # Ryanair typically has very high load factors
                'is_default': False,
                'source': 'Ryanair Annual Report 2024'
            },
            {
                'route_type': 'short_haul',
                'season': 'all_year',
                'airline': 'Aer Lingus',
                'percentage': 0.86,
                'is_default': False,
                'source': 'IAG Annual Report 2024'
            },
        ]
        
        lf_created = 0
        lf_updated = 0
        
        for data in loadfactor_data:
            loadfactor, created = LoadFactor.objects.update_or_create(
                route_type=data['route_type'],
                season=data['season'],
                airline=data['airline'],
                defaults={
                    'percentage': data['percentage'],
                    'is_default': data['is_default'],
                    'source': data['source']
                }
            )
            
            airline_display = data['airline'] if data['airline'] else 'All Airlines'
            default_marker = ' [DEFAULT]' if data['is_default'] else ''
            
            if created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'  ✓ Created: {data["route_type"]} / {data["season"]} / '
                        f'{airline_display} = {float(data["percentage"])*100:.1f}%{default_marker}'
                    )
                )
                lf_created += 1
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f'  ↻ Updated: {data["route_type"]} / {data["season"]} / '
                        f'{airline_display} = {float(data["percentage"])*100:.1f}%{default_marker}'
                    )
                )
                lf_updated += 1
        
        self.stdout.write(
            self.style.SUCCESS(f'\n✅ Load Factors: {lf_created} created, {lf_updated} updated')
        )
        
        # ======================
        # SUMMARY
        # ======================
        
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('✅ REFERENCE DATA LOADING COMPLETE'))
        self.stdout.write('='*60)
        self.stdout.write(f'Total Aircraft Types: {AircraftType.objects.count()}')
        self.stdout.write(f'Total Load Factors: {LoadFactor.objects.count()}')
        self.stdout.write('='*60)