"""
Author: Alexander Mackey
Student ID: C22739165
Description: Django management command to test the EstimationService algorithm.
Runs the 5-stage estimation for a specific airport and date, displaying detailed
output of each stage's processing.

Run with: python manage.py test_estimation
Optional: python manage.py test_estimation --airport DUB --date 2025-11-28
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, timedelta
from core.services.estimation_service import EstimationService


class Command(BaseCommand):
    """
    Test the EstimationService 5-stage algorithm.
    
    Demonstrates complete algorithm execution with verbose output
    showing each stage's processing and results.
    """
    
    help = 'Test EstimationService algorithm for passenger estimation'

    def add_arguments(self, parser):
        """Add command-line arguments"""
        parser.add_argument(
            '--airport',
            type=str,
            default='DUB',
            help='Airport IATA code (default: DUB)',
        )
        parser.add_argument(
            '--date',
            type=str,
            help='Date for estimation (YYYY-MM-DD format). Default: date with flight data',
        )
        parser.add_argument(
            '--save',
            action='store_true',
            help='Save estimates to PassengerEstimate table',
        )
        parser.add_argument(
            '--quiet',
            action='store_true',
            help='Minimal output (no verbose stage details)',
        )

    def handle(self, *args, **options):
        """Main execution method"""
        
        airport_code = options['airport']
        date_str = options['date']
        save = options['save']
        verbose = not options['quiet']
        
        # Determine date
        if date_str:
            try:
                date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                self.stdout.write(self.style.ERROR('Invalid date format. Use YYYY-MM-DD'))
                return
        else:
            # Find a date with flight data
            from core.models import Flight
            flight = Flight.objects.filter(origin__iata_code=airport_code).order_by('departure_time').first()
            if flight:
                date = flight.departure_time.date()
            else:
                self.stdout.write(self.style.ERROR(f'No flights found for airport {airport_code}'))
                return
        
        # Create service and run estimation
        try:
            service = EstimationService(airport_code=airport_code, date=date)
            predictions = service.generate_hourly_predictions(verbose=verbose)
            
            if not predictions:
                self.stdout.write(self.style.WARNING('\nNo predictions generated (no flights found)'))
                return
            
            # Save if requested
            if save:
                self.stdout.write('\n' + '='*60)
                self.stdout.write('SAVING TO DATABASE')
                self.stdout.write('='*60)
                created, updated = service.save_estimates()
                self.stdout.write(self.style.SUCCESS(f'✅ Saved: {created} created, {updated} updated'))
            
            # Summary
            if not verbose:
                self.stdout.write('\n' + '='*60)
                self.stdout.write(f'ESTIMATION SUMMARY: {airport_code} on {date}')
                self.stdout.write('='*60)
                total = sum(p['passengers'] for p in predictions)
                peak = max(predictions, key=lambda x: x['passengers'])
                self.stdout.write(f'Total passengers: {total}')
                self.stdout.write(f'Peak hour: {peak["hour"]:02d}:00 ({peak["passengers"]} passengers)')
                self.stdout.write('='*60)
            
            self.stdout.write(self.style.SUCCESS('\n✅ Estimation completed successfully!\n'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n❌ Error: {str(e)}\n'))
            import traceback
            traceback.print_exc()