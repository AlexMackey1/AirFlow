"""
Author: Alexander Mackey, Student ID: C22739165
Description: Django views for AirFlow application. Handles HTTP requests by rendering
page templates and providing JSON API endpoints.

Pages:
    map_view()       → '/'           Live map view (map.html)
    analytics_view() → '/analytics/' Predictions & chart page (analytics.html)

API Endpoints:
    heatmap_data_api()        → /api/heatmap/
    hourly_predictions_api()  → /api/predictions/hourly/
    flight_search_api()       → /api/flights/search/
    dynamic_heatmap_api()     → /api/heatmap/dynamic/
    debug_pathways_api()      → /api/debug/pathways/
"""

from django.shortcuts import render
from django.http import JsonResponse
from django.conf import settings
from .models import Airport, PassengerHeatmapData, Flight
from core.services.estimation_service import EstimationService
from core.services.pathway_interpolator import build_flight_heatmap_points
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
        'airports':            airports,
        'default_airport':     'DUB',
        'active_page':         'map',
        # Google Maps API key — read from environment variable, never hardcoded
        'google_maps_api_key': settings.GOOGLE_MAPS_API_KEY,
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
            flight_number__iexact=flight_number,
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
            'status':               flight.status,
            'terminal':             flight.terminal or '—',
            'gate':                 flight.gate or '—',
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


def dynamic_heatmap_api(request):
    """
    PHASE 3D: Gate-driven pathway heatmap.

    Runs EstimationService to get hourly predictions, then queries flights departing
    in the requested hour and routes each flight's passengers along their actual
    terminal walking pathway using PathwayInterpolator.

    Falls back to terminal spine distribution if no flights exist in DB for that hour
    (e.g. future dates not yet scraped).

    Query Parameters:
        airport (str): IATA code (default: 'DUB')
        date (str):    YYYY-MM-DD (default: tomorrow)
        hour (int):    0-23 (default: 12)

    Returns:
        JsonResponse:
        {
            'success': True,
            'airport': 'DUB',
            'date': 'YYYY-MM-DD',
            'hour': 12,
            'passengers': 608,
            'max_passengers': 800,
            'relative_intensity': 0.76,
            'point_count': 412,
            'points': [{'lat': float, 'lon': float, 'weight': float}, ...]
        }

    Performance: target < 0.5s (pathway interpolation is pure Python, no extra DB
    queries beyond the initial flight fetch).
    """
    airport_code = request.GET.get('airport', 'DUB')
    date_str     = request.GET.get('date')
    hour_str     = request.GET.get('hour', '12')

    # Validate hour
    try:
        hour = int(hour_str)
        if not 0 <= hour <= 23:
            raise ValueError
    except ValueError:
        return JsonResponse({'success': False, 'error': 'hour must be 0–23'}, status=400)

    # Parse date
    if date_str:
        try:
            prediction_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({'success': False, 'error': 'Invalid date format. Use YYYY-MM-DD'}, status=400)
    else:
        prediction_date = date.today() + timedelta(days=1)

    try:
        airport = Airport.objects.get(iata_code=airport_code)

        # Run EstimationService to get 24-hour predictions
        service        = EstimationService(airport_code, prediction_date)
        predictions    = service.generate_hourly_predictions(verbose=False)

        hour_data          = next((p for p in predictions if p['hour'] == hour), {'passengers': 0, 'confidence': 0.0})
        passengers         = hour_data['passengers']
        max_passengers     = max((p['passengers'] for p in predictions), default=1)
        relative_intensity = passengers / max_passengers if max_passengers > 0 else 0.0

        # Use service.flight_estimates (in-memory) to get per-flight passenger counts
        # alongside terminal/gate data. Avoids a redundant DB query and ensures the
        # same estimates that produced hourly totals are used for pathway routing.
        # Include flights whose passengers are plausibly in the terminal at
        # current_hour. Passengers start arriving ~2.5 hours before departure
        # and are gone once the flight departs. So include flights departing
        # between (current_hour - 0) and (current_hour + 3).
        flights_data = []
        for fe in service.flight_estimates:
            flight   = fe['flight']
            dep_hour = flight.departure_time.hour
            dep_mins = dep_hour * 60 + flight.departure_time.minute
            cur_mins = hour * 60 + 30   # midpoint of current hour
            mins_to_dep = dep_mins - cur_mins
            # Only include if passengers are plausibly in terminal:
            # arriving up to 180 mins before departure, gone up to 60 mins after departure
            # -60 lookback ensures flights that departed earlier in the same hour still show heat
            if not (-60 <= mins_to_dep <= 180):
                continue
            flights_data.append({
                'terminal':         flight.terminal or '',
                'gate':             flight.gate,
                'passengers':       fe['estimated_passengers'],
                'departure_hour':   flight.departure_time.hour,
                'departure_minute': flight.departure_time.minute,
            })

        # Count how many active flights share each gate.
        # Used by PathwayInterpolator to scale down pax_scale per flight
        # so a gate with 10 Ryanair flights doesn't dominate the heatmap
        # over a gate with 1 transatlantic flight.
        gate_counts = {}
        for fd in flights_data:
            g = fd['gate'] or '__no_gate__'
            gate_counts[g] = gate_counts.get(g, 0) + 1

        for fd in flights_data:
            g = fd['gate'] or '__no_gate__'
            fd['gate_flight_count'] = gate_counts[g]

        # Generate pathway points — interpolator uses current_hour vs departure
        # time to light up the correct terminal segment per flight.
        points = build_flight_heatmap_points(flights_data, current_hour=hour)

        # Fallback if nothing generated
        if not points and passengers > 0:
            fallback_data = [
                {'terminal': 'T1', 'gate': None, 'passengers': int(passengers * 0.60),
                 'departure_hour': hour + 2, 'departure_minute': 0},
                {'terminal': 'T2', 'gate': None, 'passengers': int(passengers * 0.40),
                 'departure_hour': hour + 2, 'departure_minute': 0},
            ]
            points = build_flight_heatmap_points(fallback_data, current_hour=hour)

        # Aggregate nearby points into ~10m grid cells.
        # Use per-cell AVERAGE (not sum) so gate cells (few gate-phase flights)
        # are not drowned by spine cells (all flights pass through the spine).
        # Summing then normalising by max-sum was tried and kept gates invisible
        # because spine sum >> gate sum after normalisation.
        if points:
            GRID_SIZE = 0.0001   # ~10m grid cells
            grid = {}
            for p in points:
                key = (round(p['lat'] / GRID_SIZE), round(p['lon'] / GRID_SIZE))
                if key in grid:
                    grid[key]['weight'] += p['weight']
                    grid[key]['count']  += 1
                else:
                    grid[key] = {'lat': p['lat'], 'lon': p['lon'],
                                 'weight': p['weight'], 'count': 1}

            # Average weight per cell, then normalise dynamically:
            #
            # Problem with max normalisation: one mega-busy cell (e.g. T1 gate 13
            # with 20 Ryanair flights) sets the ceiling, making everything else
            # comparatively invisible — the heatmap becomes either red or empty.
            #
            # Fix: use the 95th percentile as the normalisation ceiling.
            # This means the top 5% of cells saturate to red, but the remaining
            # 95% spread across the full colour gradient — green through orange.
            #
            # Minimum weight: 25% of the mean average weight for this hour.
            # Ensures quiet areas (e.g. T2 Pier 4 with one transatlantic flight)
            # remain visible rather than dropping below the HeatmapLayer threshold.
            # Both values are derived from the actual data — nothing is hardcoded.
            avg_weights = {k: v['weight'] / v['count'] for k, v in grid.items()}

            if avg_weights:
                sorted_weights = sorted(avg_weights.values())
                n = len(sorted_weights)

                # 95th percentile ceiling — stops a single dominant cell washing out the rest
                p95_index  = max(0, int(n * 0.95) - 1)
                ceiling    = sorted_weights[p95_index]
                if ceiling == 0:
                    ceiling = sorted_weights[-1]  # fallback to max if p95 is 0

                # Dynamic minimum: 25% of mean — keeps quiet areas faintly visible
                mean_weight = sum(sorted_weights) / n
                min_weight  = mean_weight * 0.25

                points = [
                    {'lat': grid[k]['lat'], 'lon': grid[k]['lon'],
                     'weight': round(min(1.0, max(min_weight, avg_weights[k]) / ceiling), 4)}
                    for k in grid
                ]

        logger.info(
            f"Dynamic heatmap (3D): {airport_code} {prediction_date} "
            f"hour={hour} pax={passengers} flights={len(flights_data)} points={len(points)}"
        )

        return JsonResponse({
            'success':            True,
            'airport':            airport_code,
            'date':               str(prediction_date),
            'hour':               hour,
            'passengers':         passengers,
            'max_passengers':     max_passengers,
            'relative_intensity': round(relative_intensity, 3),
            'point_count':        len(points),
            'points':             points,
        })

    except Airport.DoesNotExist:
        return JsonResponse({'success': False, 'error': f'Airport {airport_code} not found'}, status=404)

    except Exception as e:
        logger.exception(f"Error generating dynamic heatmap: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


def debug_pathways_api(request):
    """
    DEBUG ONLY — Phase 3D coordinate verification.

    Returns T1 and T2 pathway skeleton points as equal-weight heatmap points so the
    full terminal layout can be visually verified against the map before going live.

    Query Parameters:
        terminal (str): 'T1', 'T2', or 'all' (default: 'all')
        pier (str):     optional sub-filter e.g. 'pier_1', 'pier_4', 't2_connector', 'spine'

    Returns:
        JsonResponse:
        {
            'success': True,
            'points': [[lat, lon, intensity], ...],
            'counts': {'T1_spine': N, 'T1_pier_1': N, ...},
            'total': N
        }

    Usage:
        /api/debug/pathways/
        /api/debug/pathways/?terminal=T2
        /api/debug/pathways/?terminal=T1&pier=pier_1
    """
    from core.services.gate_coordinates import (
        T1_PATHWAYS, T2_PATHWAYS,
        T1_GATES, T2_GATES,
    )

    terminal_filter = request.GET.get('terminal', 'all').upper()
    pier_filter     = request.GET.get('pier', 'all')

    # Distinct intensity per pathway so piers are visually distinguishable on the map
    intensity_map = {
        'T1_spine':        0.3,
        'T1_pier_1':       1.0,
        'T1_pier_2':       0.7,
        'T1_pier_3':       0.5,
        'T2_spine':        0.3,
        'T2_pier_4':       0.9,
        'T2_t2_connector': 0.6,
    }

    points = []
    counts = {}

    def add_pathway(label, pathway, intensity):
        for lat, lon in pathway:
            points.append([round(lat, 7), round(lon, 7), intensity])
        counts[label] = len(pathway)

    # T1 pathways
    if terminal_filter in ('T1', 'ALL'):
        for pier_name, pathway in T1_PATHWAYS.items():
            label = f'T1_{pier_name}'
            if pier_filter != 'all' and pier_filter != pier_name:
                continue
            add_pathway(label, pathway, intensity_map.get(label, 0.5))

    # T2 pathways
    if terminal_filter in ('T2', 'ALL'):
        for pier_name, pathway in T2_PATHWAYS.items():
            label = f'T2_{pier_name}'
            if pier_filter != 'all' and pier_filter != pier_name:
                continue
            add_pathway(label, pathway, intensity_map.get(label, 0.5))

    # Gate markers at full intensity so individual gate positions are visible
    if pier_filter == 'all':
        if terminal_filter in ('T1', 'ALL'):
            for gate_num, (lat, lon) in T1_GATES.items():
                points.append([round(lat, 7), round(lon, 7), 1.0])
            counts['T1_gates'] = len(T1_GATES)

        if terminal_filter in ('T2', 'ALL'):
            for gate_num, (lat, lon) in T2_GATES.items():
                points.append([round(lat, 7), round(lon, 7), 1.0])
            counts['T2_gates'] = len(T2_GATES)

    return JsonResponse({
        'success':  True,
        'terminal': terminal_filter,
        'pier':     pier_filter,
        'points':   points,
        'counts':   counts,
        'total':    len(points),
        'note':     'DEBUG endpoint — remove before production',
    })