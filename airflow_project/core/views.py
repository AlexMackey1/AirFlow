from django.shortcuts import render
from django.http import JsonResponse
from .models import Airport, PassengerHeatmapData
import logging

logger = logging.getLogger(__name__)


def map_view(request):
    """Main map page"""
    # Get available airports for future multi-airport support
    airports = Airport.objects.all()
    context = {
        'airports': airports,
        'default_airport': 'DUB'
    }
    return render(request, 'core/map.html', context)


def heatmap_data_api(request):
    """API endpoint for heatmap data"""
    airport_code = request.GET.get('airport', 'DUB')
    
    try:
        airport = Airport.objects.get(iata_code=airport_code)
        data_points = PassengerHeatmapData.objects.filter(airport=airport).order_by('-timestamp')
        
        logger.info(f"Found {data_points.count()} data points for {airport_code}")
        
        # Format data for Leaflet heatmap: [lat, lon, intensity]
        # Normalize intensity based on passenger count (0.0 to 1.0 scale)
        heatmap_points = []
        for point in data_points:
            # Normalize passenger count to 0-1 scale (assuming max ~200 passengers)
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
                'lat': airport.location.y,  # PostGIS Point (lon, lat)
                'lon': airport.location.x
            },
            'point_count': len(heatmap_points),
            'points': heatmap_points,
            'timestamp': data_points.first().timestamp.isoformat() if data_points.exists() else None
        }
        
        logger.info(f"Returning {len(heatmap_points)} heatmap points")
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
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)