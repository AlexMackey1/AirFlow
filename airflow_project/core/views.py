"""
Author: Alexander Mackey
Student ID: C22739165
Description: Django views for AirFlow application. Handles HTTP requests by rendering the 
main map page and providing API endpoint for heatmap data in JSON format for frontend consumption.
"""

from django.shortcuts import render
from django.http import JsonResponse
from .models import Airport, PassengerHeatmapData
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