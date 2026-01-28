"""
Author: Alexander Mackey
Student ID: C22739165
Description: EstimationService implements the 5-stage passenger estimation algorithm 
as specified in interim report Chapter 3.5.2. Transforms flight schedules into hourly 
passenger volume predictions with confidence scores.

Algorithm Stages:
1. Data Preparation - Retrieve flights and apply intelligent defaults
2. Capacity Estimation - Calculate passengers (Aircraft Capacity × Load Factor)
3. Temporal Distribution - Model passenger arrival times before flights
4. Aggregation - Sum hourly passenger volumes
5. Confidence Calculation - Weighted scoring based on data quality

Based on: IATA 2024-2025 global outlook (84% short-haul, 82% long-haul load factors)
"""

from datetime import datetime, timedelta
from collections import defaultdict
from decimal import Decimal
import math

from django.utils import timezone
from core.models import Airport, Flight, AircraftType, LoadFactor, PassengerEstimate


class EstimationService:
    """
    Service layer implementing passenger flow estimation algorithm.
    
    Encapsulates 5-stage algorithm with no dependencies on Django views/HTTP.
    Fully testable in isolation using Template Method pattern.
    
    Usage:
        service = EstimationService(airport_code='DUB', date='2025-11-28')
        hourly_predictions = service.generate_hourly_predictions()
    """
    
    # Default aircraft capacities for intelligent defaults (Stage 1)
    DEFAULT_CAPACITIES = {
        'short_haul': 180,   # Typical A320
        'long_haul': 350,    # Typical B777
        'regional': 80,      # Typical ATR-72
    }
    
    # Default load factors (fallback if database lookup fails)
    DEFAULT_LOAD_FACTORS = {
        'short_haul': 0.84,
        'long_haul': 0.82,
        'regional': 0.78,
    }
    
    # Temporal distribution parameters (Stage 3)
    ARRIVAL_WINDOWS = {
        'short_haul': {'min_minutes': 90, 'max_minutes': 120},   # 1.5-2 hours before
        'long_haul': {'min_minutes': 150, 'max_minutes': 180},   # 2.5-3 hours before
        'regional': {'min_minutes': 60, 'max_minutes': 90},      # 1-1.5 hours before
    }
    
    # Confidence scoring weights (Stage 5)
    CONFIDENCE_WEIGHTS = {
        'has_aircraft_type': 0.5,      # Highest weight - capacity varies by hundreds
        'has_specific_load_factor': 0.3,  # Medium weight - percentages vary by single digits
        'flight_status_confirmed': 0.2,   # Lower weight - status is usually known
    }
    
    def __init__(self, airport_code, date):
        """
        Initialize EstimationService for specific airport and date.
        
        Args:
            airport_code (str): IATA airport code (e.g., 'DUB')
            date (date or str): Date for estimation (YYYY-MM-DD or date object)
        """
        # Convert string date to date object if needed
        if isinstance(date, str):
            date = datetime.strptime(date, '%Y-%m-%d').date()
        
        self.airport = Airport.objects.get(iata_code=airport_code)
        self.date = date
        self.flights = []
        self.flight_estimates = []  # List of dicts with flight-level estimates
        
    # =========================================================================
    # STAGE 1: DATA PREPARATION
    # =========================================================================
    
    def prepare_flight_data(self):
        """
        Stage 1: Retrieve scheduled flights and apply intelligent defaults.
        
        From interim report Section 3.5.2:
        - Retrieve all scheduled flights for selected airport and date
        - Filter out cancelled flights
        - Apply intelligent defaults when aircraft types are missing:
          * Short-haul routes → 180 seats (A320)
          * Long-haul routes → 350 seats (B777)
          * Regional routes → 80 seats (ATR-72)
        
        Modifies:
            self.flights: List of Flight objects for this airport/date
        """
        # Get all departing flights for this airport on this date
        # Filter to only scheduled (exclude cancelled)
        self.flights = Flight.objects.filter(
            origin=self.airport,
            departure_time__date=self.date,
            status='scheduled'
        ).select_related('aircraft_type', 'destination').order_by('departure_time')
        
        # Log data preparation results
        total_flights = self.flights.count()
        flights_with_aircraft = self.flights.filter(aircraft_type__isnull=False).count()
        flights_missing_aircraft = total_flights - flights_with_aircraft
        
        print(f"\n{'='*60}")
        print(f"STAGE 1: DATA PREPARATION")
        print(f"{'='*60}")
        print(f"Airport: {self.airport.name} ({self.airport.iata_code})")
        print(f"Date: {self.date}")
        print(f"Total flights retrieved: {total_flights}")
        print(f"Flights with aircraft type: {flights_with_aircraft}")
        print(f"Flights needing defaults: {flights_missing_aircraft}")
        print(f"{'='*60}\n")
    
    def _get_default_capacity(self, flight):
        """
        Get default aircraft capacity based on route type.
        
        Helper method for Stage 1 when aircraft_type is missing.
        
        Args:
            flight (Flight): Flight object
            
        Returns:
            int: Default capacity based on route type
        """
        route_type = flight.route_type
        return self.DEFAULT_CAPACITIES.get(route_type, 180)  # Default to short-haul if unknown
    
    # =========================================================================
    # STAGE 2: CAPACITY ESTIMATION
    # =========================================================================
    
    def estimate_capacity(self, flight):
        """
        Stage 2: Apply capacity estimation formula.
        
        From interim report Section 3.5.2:
        Formula: Estimated Passengers = Aircraft Capacity × Load Factor
        
        Uses IATA 2024-2025 data:
        - Short-haul European: 84% load factor
        - Long-haul international: 82% load factor
        
        Args:
            flight (Flight): Flight object
            
        Returns:
            tuple: (estimated_passengers, capacity_used, load_factor_used, used_default_aircraft, used_default_lf)
        """
        # Determine route type
        route_type = flight.route_type
        
        # Get aircraft capacity (or use intelligent default)
        if flight.aircraft_type:
            capacity = flight.aircraft_type.total_capacity
            used_default_aircraft = False
        else:
            capacity = self._get_default_capacity(flight)
            used_default_aircraft = True
        
        # Get load factor (with fallback hierarchy)
        load_factor, used_default_lf = self._get_load_factor(flight, route_type)
        
        # Calculate estimated passengers
        estimated_passengers = int(capacity * float(load_factor))
        
        return (
            estimated_passengers,
            capacity,
            float(load_factor),
            used_default_aircraft,
            used_default_lf
        )
    
    def _get_load_factor(self, flight, route_type):
        """
        Get load factor with hierarchical fallback.
        
        Lookup hierarchy (from specific to general):
        1. Airline + Season + Route Type
        2. Airline + Route Type (all_year)
        3. Season + Route Type (all airlines)
        4. Route Type only (all_year, all airlines) - DEFAULT
        5. Hardcoded fallback
        
        Args:
            flight (Flight): Flight object
            route_type (str): Route type ('short_haul', 'long_haul', 'regional')
            
        Returns:
            tuple: (load_factor, used_default)
        """
        # Determine season (simplified)
        month = self.date.month
        if 5 <= month <= 9:
            season = 'summer'
        elif 11 <= month or month <= 2:
            season = 'winter'
        else:
            season = 'all_year'
        
        # Try lookup hierarchy
        # 1. Try airline + season + route_type
        try:
            lf = LoadFactor.objects.get(
                airline=flight.airline,
                season=season,
                route_type=route_type
            )
            return (lf.percentage, False)
        except LoadFactor.DoesNotExist:
            pass
        
        # 2. Try airline + all_year + route_type
        try:
            lf = LoadFactor.objects.get(
                airline=flight.airline,
                season='all_year',
                route_type=route_type
            )
            return (lf.percentage, False)
        except LoadFactor.DoesNotExist:
            pass
        
        # 3. Try default for season + route_type
        try:
            lf = LoadFactor.objects.get(
                airline='',
                season=season,
                route_type=route_type,
                is_default=False
            )
            return (lf.percentage, False)
        except LoadFactor.DoesNotExist:
            pass
        
        # 4. Try default for route_type (all_year, all airlines)
        try:
            lf = LoadFactor.objects.get(
                airline='',
                season='all_year',
                route_type=route_type,
                is_default=True
            )
            return (lf.percentage, True)
        except LoadFactor.DoesNotExist:
            pass
        
        # 5. Hardcoded fallback (shouldn't happen if reference data loaded)
        return (Decimal(str(self.DEFAULT_LOAD_FACTORS.get(route_type, 0.84))), True)
    
    # =========================================================================
    # STAGE 3: TEMPORAL DISTRIBUTION
    # =========================================================================
    
    def distribute_temporally(self, flight, estimated_passengers):
        """
        Stage 3: Model when passengers arrive at terminal.
        
        From interim report Section 3.5.2:
        - Short-haul: Distributed across 90-120 minutes before departure
        - Long-haul: Distributed across 150-180 minutes before departure
        - Uses probability distribution (not uniform) where most passengers
          arrive in middle of recommended window
        
        Args:
            flight (Flight): Flight object
            estimated_passengers (int): Number of passengers to distribute
            
        Returns:
            list: List of tuples [(datetime, passenger_count), ...]
        """
        route_type = flight.route_type
        window = self.ARRIVAL_WINDOWS.get(route_type, self.ARRIVAL_WINDOWS['short_haul'])
        
        min_minutes = window['min_minutes']
        max_minutes = window['max_minutes']
        
        # Create time slots (15-minute intervals within arrival window)
        departure_time = flight.departure_time
        slots = []
        
        # Generate 15-minute slots within the window
        num_slots = (max_minutes - min_minutes) // 15 + 1
        
        for i in range(num_slots):
            minutes_before = max_minutes - (i * 15)
            slot_time = departure_time - timedelta(minutes=minutes_before)
            slots.append(slot_time)
        
        # Apply normal distribution (bell curve)
        # Most passengers arrive in middle of window, fewer at extremes
        slot_weights = self._generate_normal_distribution(len(slots))
        
        # Distribute passengers across slots according to weights
        distribution = []
        remaining_passengers = estimated_passengers
        
        for i, (slot_time, weight) in enumerate(zip(slots, slot_weights)):
            if i == len(slots) - 1:
                # Last slot gets remaining passengers (avoid rounding errors)
                slot_passengers = remaining_passengers
            else:
                slot_passengers = int(estimated_passengers * weight)
                remaining_passengers -= slot_passengers
            
            if slot_passengers > 0:
                distribution.append((slot_time, slot_passengers))
        
        return distribution
    
    def _generate_normal_distribution(self, num_slots):
        """
        Generate weights following normal distribution.
        
        Creates bell curve where middle slots have higher weights.
        
        Args:
            num_slots (int): Number of time slots
            
        Returns:
            list: Normalized weights summing to 1.0
        """
        if num_slots == 1:
            return [1.0]
        
        # Generate normal distribution centered at middle
        mean = (num_slots - 1) / 2.0
        std_dev = num_slots / 6.0  # 99.7% within range
        
        weights = []
        for i in range(num_slots):
            # Calculate normal distribution probability
            exponent = -((i - mean) ** 2) / (2 * std_dev ** 2)
            weight = math.exp(exponent)
            weights.append(weight)
        
        # Normalize weights to sum to 1.0
        total = sum(weights)
        normalized = [w / total for w in weights]
        
        return normalized
    
    # =========================================================================
    # STAGE 4: AGGREGATION
    # =========================================================================
    
    def aggregate_hourly(self):
        """
        Stage 4: Sum passenger contributions for each hour.
        
        From interim report Section 3.5.2:
        - Sum up all passenger contributions for each hour of the day
        - Produces time series showing estimated passenger volume per hour
        - Hourly resolution balances detail with usability
        
        Returns:
            dict: {hour (0-23): {'passengers': int, 'confidence_scores': [floats]}}
        """
        hourly_data = defaultdict(lambda: {'passengers': 0, 'confidence_scores': []})
        
        # Process each flight's temporal distribution
        for flight_est in self.flight_estimates:
            distribution = flight_est['temporal_distribution']
            confidence = flight_est['confidence_score']
            
            # Add passengers to appropriate hours
            for slot_time, passenger_count in distribution:
                hour = slot_time.hour
                hourly_data[hour]['passengers'] += passenger_count
                hourly_data[hour]['confidence_scores'].append(confidence)
        
        return hourly_data
    
    # =========================================================================
    # STAGE 5: CONFIDENCE CALCULATION
    # =========================================================================
    
    def calculate_confidence(self, flight, used_default_aircraft, used_default_lf):
        """
        Stage 5: Calculate confidence score based on data quality.
        
        From interim report Section 3.5.2:
        - High confidence (0.8-1.0): Actual aircraft data available
        - Medium confidence (0.5-0.7): Some defaults applied
        - Low confidence (0.0-0.4): Significant missing data
        
        Weighted scoring:
        - Aircraft type data available: +0.5 (highest weight)
        - Specific load factor (not default): +0.3
        - Flight status confirmed: +0.2
        
        Args:
            flight (Flight): Flight object
            used_default_aircraft (bool): Whether default capacity was used
            used_default_lf (bool): Whether default load factor was used
            
        Returns:
            float: Confidence score (0.0 to 1.0)
        """
        score = 0.0
        
        # Check aircraft type data (highest weight)
        if not used_default_aircraft:
            score += self.CONFIDENCE_WEIGHTS['has_aircraft_type']
        
        # Check load factor specificity (medium weight)
        if not used_default_lf:
            score += self.CONFIDENCE_WEIGHTS['has_specific_load_factor']
        
        # Check flight status (lower weight)
        if flight.status == 'scheduled':
            score += self.CONFIDENCE_WEIGHTS['flight_status_confirmed']
        
        return round(score, 2)
    
    def _get_confidence_level(self, score):
        """
        Get human-readable confidence level.
        
        Args:
            score (float): Confidence score (0.0-1.0)
            
        Returns:
            str: 'High', 'Medium', or 'Low'
        """
        if score >= 0.8:
            return 'High'
        elif score >= 0.5:
            return 'Medium'
        else:
            return 'Low'
    
    # =========================================================================
    # MAIN ORCHESTRATION METHOD (Template Method Pattern)
    # =========================================================================
    
    def generate_hourly_predictions(self, verbose=True):
        """
        Execute complete 5-stage estimation algorithm.
        
        Template Method pattern: defines skeleton, stages implement specifics.
        
        Args:
            verbose (bool): Print progress information
            
        Returns:
            list: Hourly predictions with format:
                [
                    {
                        'hour': 8,
                        'passengers': 450,
                        'confidence': 0.85,
                        'confidence_level': 'High'
                    },
                    ...
                ]
        """
        if verbose:
            print(f"\n{'='*60}")
            print(f"AIRFLOW ESTIMATION SERVICE")
            print(f"{'='*60}")
            print(f"Generating predictions for {self.airport.name} on {self.date}")
            print(f"{'='*60}\n")
        
        # STAGE 1: Data Preparation
        self.prepare_flight_data()
        
        if self.flights.count() == 0:
            if verbose:
                print("⚠️  No flights found for this date/airport")
            return []
        
        # STAGES 2-5: Process each flight
        if verbose:
            print(f"{'='*60}")
            print(f"STAGES 2-5: PROCESSING FLIGHTS")
            print(f"{'='*60}\n")
        
        for i, flight in enumerate(self.flights, 1):
            # STAGE 2: Capacity Estimation
            (
                estimated_pax,
                capacity,
                load_factor,
                used_default_aircraft,
                used_default_lf
            ) = self.estimate_capacity(flight)
            
            # STAGE 3: Temporal Distribution
            temporal_dist = self.distribute_temporally(flight, estimated_pax)
            
            # STAGE 5: Confidence Calculation
            confidence = self.calculate_confidence(flight, used_default_aircraft, used_default_lf)
            
            # Store flight-level estimate
            flight_estimate = {
                'flight': flight,
                'estimated_passengers': estimated_pax,
                'capacity': capacity,
                'load_factor': load_factor,
                'temporal_distribution': temporal_dist,
                'confidence_score': confidence,
                'used_defaults': {
                    'aircraft': used_default_aircraft,
                    'load_factor': used_default_lf
                }
            }
            self.flight_estimates.append(flight_estimate)
            
            # Print progress
            if verbose:
                aircraft_str = flight.aircraft_type.model if flight.aircraft_type else f"DEFAULT({capacity})"
                defaults_marker = " ⚠️" if (used_default_aircraft or used_default_lf) else " ✓"
                print(f"[{i:2d}/{self.flights.count()}] {flight.flight_number:8s} "
                      f"{flight.destination.iata_code:3s} @ {flight.departure_time.strftime('%H:%M')} | "
                      f"{aircraft_str:15s} | {estimated_pax:3d} pax | "
                      f"LF: {load_factor*100:5.1f}% | Conf: {confidence:.2f}{defaults_marker}")
        
        # STAGE 4: Aggregation
        if verbose:
            print(f"\n{'='*60}")
            print(f"STAGE 4: AGGREGATION")
            print(f"{'='*60}\n")
        
        hourly_data = self.aggregate_hourly()
        
        # Format final predictions
        predictions = []
        for hour in range(24):
            if hour in hourly_data:
                data = hourly_data[hour]
                # Average confidence scores for this hour
                avg_confidence = sum(data['confidence_scores']) / len(data['confidence_scores'])
                avg_confidence = round(avg_confidence, 2)
                
                predictions.append({
                    'hour': hour,
                    'passengers': data['passengers'],
                    'confidence': avg_confidence,
                    'confidence_level': self._get_confidence_level(avg_confidence)
                })
            else:
                # No flights in this hour
                predictions.append({
                    'hour': hour,
                    'passengers': 0,
                    'confidence': 0.0,
                    'confidence_level': 'Low'
                })
        
        if verbose:
            print("Hourly Predictions:")
            print(f"{'Hour':<6} {'Passengers':<12} {'Confidence':<12} {'Level':<10}")
            print("-" * 45)
            for pred in predictions:
                if pred['passengers'] > 0:
                    emoji = '🟢' if pred['confidence'] >= 0.8 else '🟡' if pred['confidence'] >= 0.5 else '🔴'
                    print(f"{pred['hour']:02d}:00  {pred['passengers']:<12} "
                          f"{pred['confidence']:<12.2f} {emoji} {pred['confidence_level']}")
        
        if verbose:
            print(f"\n{'='*60}")
            print(f"ESTIMATION COMPLETE")
            print(f"{'='*60}")
            total_pax = sum(p['passengers'] for p in predictions)
            print(f"Total estimated passengers: {total_pax}")
            print(f"Peak hour: {max(predictions, key=lambda x: x['passengers'])['hour']:02d}:00")
            print(f"{'='*60}\n")
        
        return predictions
    
    # =========================================================================
    # PERSISTENCE METHODS
    # =========================================================================
    
    def save_estimates(self):
        """
        Save hourly predictions to PassengerEstimate table.
        
        Stores pre-computed results for performance optimization.
        Updates existing records if they exist.
        """
        predictions = self.generate_hourly_predictions(verbose=False)
        
        created_count = 0
        updated_count = 0
        
        for prediction in predictions:
            estimate, created = PassengerEstimate.objects.update_or_create(
                airport=self.airport,
                date=self.date,
                hour=prediction['hour'],
                defaults={
                    'passenger_count': prediction['passengers'],
                    'confidence_score': prediction['confidence']
                }
            )
            
            if created:
                created_count += 1
            else:
                updated_count += 1
        
        print(f"✅ Saved hourly estimates: {created_count} created, {updated_count} updated")
        
        return created_count, updated_count