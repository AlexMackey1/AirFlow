"""
Author: Alexander Mackey
Student ID: C22739165
Description: Django views for AirFlow application. Handles HTTP requests by rendering
page templates and providing JSON API endpoints.

Pages:
    map_view()       → '/'           Live map view (map.html)
    analytics_view() → '/analytics/' Predictions & chart page (analytics.html)

API Endpoints:
    heatmap_data_api()        → /api/heatmap/
    hourly_predictions_api()  → /api/predictions/hourly/
    flight_search_api()       → /api/flights/search/
"""

from django.shortcuts import render
from django.http import JsonResponse
from .models import Airport, PassengerHeatmapData, Flight
from core.services.estimation_service import EstimationService
from datetime import datetime, date, timedelta
import logging

# Initialize logger for tracking application events and errors
logger = logging.getLogger(__name__)


def map_view(request):
    """
    Renders the Live View page (map-first layout).

    The map page focuses on the Leaflet heatmap visualization. Predictions
    and chart are on the Analytics page (/analytics/).

    Args:
        request: HTTP request object from Django

    Returns:
        HttpResponse with rendered core/map.html template
    """
    airports = Airport.objects.all()

    context = {
        'airports': airports,
        'default_airport': 'DUB',
        'active_page': 'map'
    }

    return render(request, 'core/map.html', context)


def analytics_view(request):
    """
    Renders the Analytics page — hourly predictions, Chart.js, time slider.

    Separated from map_view so each page gets full screen space:
    - Map page: map dominates
    - Analytics page: chart and data dominate

    Args:
        request: HTTP request object from Django

    Returns:
        HttpResponse with rendered core/analytics.html template
    """
    airports = Airport.objects.all()

    context = {
        'airports': airports,
        'default_airport': 'DUB',
        'active_page': 'analytics'
    }

    return render(request, 'core/analytics.html', context)


def heatmap_data_api(request):
    """
    API endpoint that returns passenger heatmap data in JSON format.

    Processes GET request with optional airport parameter, queries database for
    passenger data points, normalizes intensity values (0-1 scale), and returns
    formatted JSON for Leaflet.heat library consumption.

    Args:
        request: HTTP request object containing GET parameters

    Returns:
        JsonResponse with success status, airport info, and heatmap point array:
        {
            'success': True,
            'airport': {'code', 'name', 'city', 'country', 'lat', 'lon'},
            'point_count': int,
            'points': [[lat, lon, intensity], ...],
            'timestamp': str or None
        }
    """
    # Extract airport code from URL parameters (defaults to DUB if not provided)
    airport_code = request.GET.get('airport', 'DUB')

    try:
        airport = Airport.objects.get(iata_code=airport_code)

        # Query all passenger data points for this airport, ordered by most recent
        data_points = PassengerHeatmapData.objects.filter(airport=airport).order_by('-timestamp')

        logger.info(f"Found {data_points.count()} data points for {airport_code}")

        # Format data for Leaflet heatmap: [latitude, longitude, intensity]
        heatmap_points = []
        for point in data_points:
            # Normalize passenger count to 0-1 scale (max ~200 passengers per cluster)
            intensity = min(point.passenger_count / 200.0, 1.0)
            heatmap_points.append([
                point.latitude,
                point.longitude,
                intensity
            ])

        response_data = {
            'success': True,
            'airport': {
                'code': airport.iata_code,
                'name': airport.name,
                'city': airport.city,
                'country': airport.country,
                # PostGIS Point stores as (longitude, latitude): .y is lat, .x is lon
                'lat': airport.location.y,
                'lon': airport.location.x
            },
            'point_count': len(heatmap_points),
            'points': heatmap_points,
            'timestamp': data_points.first().timestamp.isoformat() if data_points.exists() else None
        }

        logger.info(f"Returning {len(heatmap_points)} heatmap points for {airport_code}")
        return JsonResponse(response_data)

    except Airport.DoesNotExist:
        logger.error(f"Airport {airport_code} not found")
        return JsonResponse({
            'success': False,
            'error': f'Airport {airport_code} not found',
            'available_airports': list(Airport.objects.values_list('iata_code', flat=True))
        }, status=404)

    except Exception as e:
        logger.exception(f"Error fetching heatmap data: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


def hourly_predictions_api(request):
    """
    API endpoint for hourly passenger flow predictions using EstimationService.

    Implements Phase 3A requirements from interim report:
    - Executes 5-stage estimation algorithm
    - Returns 24-hour predictions with confidence scores
    - Provides summary statistics (total passengers, peak hour, etc.)

    Query Parameters:
        airport (str): IATA airport code (default: 'DUB')
        date (str):    Date for prediction in YYYY-MM-DD format (default: tomorrow)

    Returns:
        JsonResponse:
        {
            'success': True,
            'airport': {...},
            'date': 'YYYY-MM-DD',
            'predictions': [{'hour', 'passengers', 'confidence', 'level'}, ...],
            'summary': {
                'total_passengers', 'peak_hour', 'peak_passengers',
                'flights_processed', 'avg_confidence'
            }
        }
    """
    airport_code = request.GET.get('airport', 'DUB')
    date_str     = request.GET.get('date')

    # Parse date parameter
    if date_str:
        try:
            prediction_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid date format. Use YYYY-MM-DD'
            }, status=400)
    else:
        prediction_date = date.today() + timedelta(days=1)

    try:
        airport = Airport.objects.get(iata_code=airport_code)

        logger.info(f"Running estimation for {airport_code} on {prediction_date}")
        service     = EstimationService(airport_code, prediction_date)
        predictions = service.generate_hourly_predictions(verbose=False)

        # Calculate summary statistics
        total_passengers = sum(p['passengers'] for p in predictions)

        if predictions:
            peak            = max(predictions, key=lambda x: x['passengers'])
            peak_hour       = peak['hour']
            peak_passengers = peak['passengers']
            confidence_scores = [p['confidence'] for p in predictions if p['passengers'] > 0]
            avg_confidence  = round(
                sum(confidence_scores) / len(confidence_scores), 2
            ) if confidence_scores else 0.0
        else:
            peak_hour       = 0
            peak_passengers = 0
            avg_confidence  = 0.0

        flights_processed = len(service.flights)

        response_data = {
            'success': True,
            'airport': {
                'code':    airport.iata_code,
                'name':    airport.name,
                'city':    airport.city,
                'country': airport.country,
                'lat':     airport.location.y,
                'lon':     airport.location.x
            },
            'date':        str(prediction_date),
            'predictions': predictions,
            'summary': {
                'total_passengers': total_passengers,
                'peak_hour':        peak_hour,
                'peak_passengers':  peak_passengers,
                'flights_processed': flights_processed,
                'avg_confidence':   avg_confidence
            }
        }

        logger.info(f"Prediction successful: {total_passengers} passengers, peak at {peak_hour}:00")
        return JsonResponse(response_data)

    except Airport.DoesNotExist:
        logger.error(f"Airport {airport_code} not found")
        return JsonResponse({
            'success': False,
            'error': f'Airport {airport_code} not found',
            'available_airports': list(Airport.objects.values_list('iata_code', flat=True))
        }, status=404)

    except Exception as e:
        logger.exception(f"Error generating predictions: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


def flight_search_api(request):
    """
    PHASE 3B: API endpoint for flight search and personalized arrival recommendations.

    Implements Use Case 3 from interim report:
    - Search flights by flight number
    - Display flight details (destination, time, aircraft, airline)
    - Provide personalized arrival recommendation based on route type and congestion

    Query Parameters:
        flight_number (str): e.g. "EI101", "FR201"
        airport (str):       IATA code (default: 'DUB')
        date (str):          YYYY-MM-DD (default: tomorrow)

    Returns:
        JsonResponse:
        {
            'success': True,
            'flight': {
                'flight_number', 'airline', 'origin', 'destination',
                'destination_name', 'departure_time', 'arrival_time',
                'aircraft', 'capacity', 'estimated_passengers',
                'route_type', 'status'
            },
            'recommendation': {
                'optimal_arrival', 'optimal_arrival_hour',
                'peak_congestion_time', 'peak_passengers',
                'congestion_at_your_time', 'comparison',
                'time_savings', 'route_type_note'
            }
        }

    Performance requirement: < 1 second response time
    """
    flight_number = request.GET.get('flight_number', '').strip().upper()
    airport_code  = request.GET.get('airport', 'DUB')
    date_str      = request.GET.get('date')

    if not flight_number:
        return JsonResponse({'success': False, 'error': 'Flight number is required'}, status=400)

    if date_str:
        try:
            search_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid date format. Use YYYY-MM-DD'
            }, status=400)
    else:
        search_date = date.today() + timedelta(days=1)

    try:
        airport = Airport.objects.get(iata_code=airport_code)

        # Search for matching flight on the given date
        start_datetime = datetime.combine(search_date, datetime.min.time())
        end_datetime   = datetime.combine(search_date, datetime.max.time())

        flight = Flight.objects.filter(
            origin=airport,
            flight_number=flight_number,
            departure_time__range=(start_datetime, end_datetime)
        ).select_related('aircraft_type', 'origin', 'destination').first()

        if not flight:
            return JsonResponse({
                'success': False,
                'error': f'Flight {flight_number} not found for {search_date}',
                'suggestion': 'Try EI101, FR201, or check the date'
            }, status=404)

        # Build flight data dict
        flight_data = {
            'flight_number':        flight.flight_number,
            'airline':              flight.airline,
            'origin':               flight.origin.iata_code,
            'destination':          flight.destination.iata_code,
            'destination_name':     flight.destination.name,
            'departure_time':       flight.departure_time.strftime('%H:%M'),
            'arrival_time':         flight.arrival_time.strftime('%H:%M') if flight.arrival_time else None,
            'aircraft':             flight.aircraft_type.model if flight.aircraft_type else 'Unknown',
            'capacity':             flight.aircraft_type.total_capacity if flight.aircraft_type else None,
            'estimated_passengers': flight.estimated_passengers,
            'route_type':           flight.route_type,
            'status':               flight.status
        }

        # Run estimation to get hourly congestion for recommendation
        service     = EstimationService(airport_code, search_date)
        predictions = service.generate_hourly_predictions(verbose=False)

        # Calculate recommended arrival window by route type
        route_minutes = {
            'short_haul': 105,   # 1h 45m
            'long_haul':  165,   # 2h 45m
            'regional':   75     # 1h 15m
        }
        recommended_arrival_minutes = route_minutes.get(flight.route_type, 105)

        from datetime import timedelta as td
        optimal_arrival_dt   = flight.departure_time - td(minutes=recommended_arrival_minutes)
        optimal_arrival_hour = optimal_arrival_dt.hour
        optimal_arrival_time = optimal_arrival_dt.strftime('%H:%M')

        congestion_at_arrival = next(
            (p['passengers'] for p in predictions if p['hour'] == optimal_arrival_hour), 0
        )
        peak = max(predictions, key=lambda x: x['passengers']) if predictions else {'hour': 0, 'passengers': 0}

        # Generate contextual comparison message
        if congestion_at_arrival < peak['passengers'] * 0.7:
            comparison = (
                f"Good timing! Arriving at {optimal_arrival_time} avoids peak congestion "
                f"({peak['passengers']} passengers at {peak['hour']:02d}:00)"
            )
            time_savings = "10–15 minutes faster processing"
        elif congestion_at_arrival < peak['passengers'] * 0.9:
            comparison = (
                f"Moderate congestion. Arriving at {optimal_arrival_time} has "
                f"{congestion_at_arrival} passengers (peak: {peak['passengers']} at {peak['hour']:02d}:00)"
            )
            time_savings = "5–10 minutes faster than peak"
        else:
            comparison = (
                f"Peak time! Arriving at {optimal_arrival_time} coincides with "
                f"{congestion_at_arrival} passengers. Consider arriving 30 mins earlier."
            )
            time_savings = "Peak congestion — expect delays"

        route_label = flight.route_type.replace('_', ' ').title()
        h = recommended_arrival_minutes // 60
        m = recommended_arrival_minutes % 60

        recommendation = {
            'optimal_arrival':        optimal_arrival_time,
            'optimal_arrival_hour':   optimal_arrival_hour,
            'peak_congestion_time':   f"{peak['hour']:02d}:00",
            'peak_passengers':        peak['passengers'],
            'congestion_at_your_time': congestion_at_arrival,
            'comparison':             comparison,
            'time_savings':           time_savings,
            'route_type_note':        f"{route_label} flight — recommend arriving {h}h {m}m before departure"
        }

        response_data = {
            'success':        True,
            'flight':         flight_data,
            'recommendation': recommendation,
            'date':           str(search_date)
        }

        logger.info(f"Flight search: {flight_number} on {search_date}")
        return JsonResponse(response_data)

    except Airport.DoesNotExist:
        logger.error(f"Airport {airport_code} not found")
        return JsonResponse({'success': False, 'error': f'Airport {airport_code} not found'}, status=404)

    except Exception as e:
        logger.exception(f"Error searching flight: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)