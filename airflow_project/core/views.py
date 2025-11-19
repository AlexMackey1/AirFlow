from django.shortcuts import render
from django.http import JsonResponse
from .models import Airport, PassengerHeatmapData

def map_view(request):
    """Main map page"""
    return render(request, 'core/map.html')

def heatmap_data_api(request):
    """API endpoint for heatmap data"""
    airport_code = request.GET.get('airport', 'DUB')
    
    try:
        airport = Airport.objects.get(iata_code=airport_code)
        data = PassengerHeatmapData.objects.filter(airport=airport)
        
        # Format data for Leaflet heatmap: [lat, lon, intensity]
        heatmap_points = [
            [point.latitude, point.longitude, point.passenger_count / 10.0]
            for point in data
        ]
        
        return JsonResponse({
            'success': True,
            'airport': airport.name,
            'point_count': len(heatmap_points),
            'points': heatmap_points
        })
    
    except Airport.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Airport not found'
        }, status=404)