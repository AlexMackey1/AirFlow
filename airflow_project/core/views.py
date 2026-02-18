"""
Author: Alexander Mackey
Student ID: C22739165
Description: Django views for AirFlow application. Handles HTTP requests by rendering the 
main map page and providing API endpoints for heatmap data and hourly predictions in JSON format.
"""

from django.shortcuts import render
from django.http import JsonResponse
from .models import Airport, PassengerHeatmapData
from core.services.estimation_service import EstimationService
from datetime import datetime, date, timedelta
import logging

# Initialize logger for tracking application events and errors
logger = logging.getLogger(__name__)


def map_view(request):
    """
    Renders the main map visualization page.
    
    Retrieves all airports from database for future multi-airport support and
    passes them to the template along with default airport selection.
    
    Args:
        request: HTTP request object from Django
        
    Returns:
        HttpResponse with rendered map.html template
    """
    # Get all airports from database (currently only Dublin exists)
    airports = Airport.objects.all()
    
    # Context dictionary passed to template
    context = {
        'airports': airports,        # List of airport objects
        'default_airport': 'DUB'     # Default selected airport code
    }
    
    return render(request, 'core/map.html', context)


def heatmap_data_api(request):
    """
    API endpoint that returns passenger heatmap data in JSON format.
    
    Processes GET request with optional airport parameter, queries database for
    passenger data points, normalizes intensity values (0-1 scale), and returns
    formatted JSON for Leaflet.heat library consumption.
    
    Args:
        request: HTTP request object containing GET parameters
        
    Returns:
        JsonResponse with success status, airport info, and heatmap point array
    """
    # Extract airport code from URL parameters (defaults to DUB if not provided)
    airport_code = request.GET.get('airport', 'DUB')
    
    try:
        # Attempt to retrieve airport from database by IATA code
        airport = Airport.objects.get(iata_code=airport_code)
        
        # Query all passenger data points for this airport, ordered by most recent
        data_points = PassengerHeatmapData.objects.filter(airport=airport).order_by('-timestamp')
        
        # Log the number of data points found for debugging
        logger.info(f"Found {data_points.count()} data points for {airport_code}")
        
        # Format data for Leaflet heatmap: [latitude, longitude, intensity]
        # Each point becomes a three-element array in the format Leaflet.heat expects
        heatmap_points = []
        
        for point in data_points:
            # Normalize passenger count to 0-1 scale for color mapping
            # Dividing by 200 assumes max ~200 passengers per cluster
            # min() ensures we cap at 1.0 even if count exceeds 200
            intensity = min(point.passenger_count / 200.0, 1.0)
            
            # Append formatted point: [lat, lon, intensity]
            heatmap_points.append([
                point.latitude,   # North-south coordinate
                point.longitude,  # East-west coordinate
                intensity         # 0.0 = blue (low), 1.0 = red (high)
            ])
        
        # Build successful response dictionary
        response_data = {
            'success': True,
            'airport': {
                'code': airport.iata_code,
                'name': airport.name,
                'city': airport.city,
                'country': airport.country,
                # PostGIS Point stores as (longitude, latitude), so .y is lat, .x is lon
                'lat': airport.location.y,
                'lon': airport.location.x
            },
            'point_count': len(heatmap_points),
            'points': heatmap_points,
            # Get timestamp from most recent data point, format as ISO string
            'timestamp': data_points.first().timestamp.isoformat() if data_points.exists() else None
        }
        
        # Log successful response
        logger.info(f"Returning {len(heatmap_points)} heatmap points")
        
        # Return JSON response with formatted data
        return JsonResponse(response_data)
    
    except Airport.DoesNotExist:
        # Airport code not found in database
        logger.error(f"Airport {airport_code} not found")
        
        # Return error response with 404 status and list of valid airports
        return JsonResponse({
            'success': False,
            'error': f'Airport {airport_code} not found',
            'available_airports': list(Airport.objects.values_list('iata_code', flat=True))
        }, status=404)
    
    except Exception as e:
        # Catch any other unexpected errors
        logger.exception(f"Error fetching heatmap data: {e}")
        
        # Return generic error response with 500 status
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


def hourly_predictions_api(request):
    """
    API endpoint for hourly passenger flow predictions using EstimationService.
    
    Implements Phase 3A requirements from interim report:
    - Executes 5-stage estimation algorithm
    - Returns 24-hour predictions with confidence scores
    - Provides summary statistics (total passengers, peak hour, etc.)
    
    Query Parameters:
        airport (str): IATA airport code (default: 'DUB')
        date (str): Date for prediction in YYYY-MM-DD format (default: tomorrow)
    
    Returns:
        JsonResponse with format:
        {
            'success': True,
            'airport': {...},           # Airport details
            'date': '2026-02-06',
            'predictions': [            # 24-hour array
                {
                    'hour': 0,
                    'passengers': 0,
                    'confidence': 0.0,
                    'level': 'Low'
                },
                ...
            ],
            'summary': {
                'total_passengers': 5448,
                'peak_hour': 12,
                'peak_passengers': 608,
                'flights_processed': 32,
                'avg_confidence': 0.92
            }
        }
    
    Args:
        request: HTTP GET request with optional query parameters
        
    Returns:
        JsonResponse with predictions or error message
    """
    # Extract parameters
    airport_code = request.GET.get('airport', 'DUB')
    date_str = request.GET.get('date')
    
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
        # Default to tomorrow
        prediction_date = date.today() + timedelta(days=1)
    
    try:
        # Verify airport exists
        airport = Airport.objects.get(iata_code=airport_code)
        
        # Initialize EstimationService (Phase 2)
        logger.info(f"Running estimation for {airport_code} on {prediction_date}")
        service = EstimationService(airport_code, prediction_date)
        
        # Execute 5-stage algorithm
        predictions = service.generate_hourly_predictions(verbose=False)
        
        # Calculate summary statistics
        total_passengers = sum(p['passengers'] for p in predictions)
        
        # Find peak hour
        if predictions:
            peak = max(predictions, key=lambda x: x['passengers'])
            peak_hour = peak['hour']
            peak_passengers = peak['passengers']
            
            # Calculate average confidence
            confidence_scores = [p['confidence'] for p in predictions if p['passengers'] > 0]
            avg_confidence = round(sum(confidence_scores) / len(confidence_scores), 2) if confidence_scores else 0.0
        else:
            peak_hour = 0
            peak_passengers = 0
            avg_confidence = 0.0
        
        # Count flights processed
        flights_processed = len(service.flights)
        
        # Build response
        response_data = {
            'success': True,
            'airport': {
                'code': airport.iata_code,
                'name': airport.name,
                'city': airport.city,
                'country': airport.country,
                'lat': airport.location.y,
                'lon': airport.location.x
            },
            'date': str(prediction_date),
            'predictions': predictions,  # 24-hour array from algorithm
            'summary': {
                'total_passengers': total_passengers,
                'peak_hour': peak_hour,
                'peak_passengers': peak_passengers,
                'flights_processed': flights_processed,
                'avg_confidence': avg_confidence
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
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)