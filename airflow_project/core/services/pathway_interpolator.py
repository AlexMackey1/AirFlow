"""
Author: Alexander Mackey, Student ID: C22739165
Description: Pathway interpolation service for gate-driven terminal heatmap generation.

Core model — where are passengers on the path right now?
---------------------------------------------------------
For a flight departing at time D, a passenger's journey through the terminal
follows a predictable timeline:

    D - 150m to D - 90m  : check-in / landside (spine start → security)
    D - 90m  to D - 45m  : security → duty free (spine mid → pier junction)
    D - 45m  to D - 15m  : walking pier corridor (junction → gate approach)
    D - 15m  to D        : seated at gate (gate end)

When the heatmap slider is set to hour H, each flight is assessed by how many
minutes remain until its departure. Only the relevant path segment generates
points — so at hour 13 a 15:00 flight shows check-in heat, and at hour 14:30
it shows gate heat. This prevents spine accumulation swamping the pier/gate ends.
"""

import math
import logging
from typing import Optional

from .gate_coordinates import (
    T1_PATHWAYS, T2_PATHWAYS, T2_CONNECTOR,
    T1_GATES, T2_GATES,
    GATE_TO_PATHWAY, TERMINAL_FALLBACK,
    is_excluded_gate,
)

logger = logging.getLogger(__name__)

INTERPOLATION_STEP = 0.00005

# Path split fractions — where each journey segment starts/ends on the full path.
# Measured empirically from interpolated node counts (see test_pathway_fractions.py):
#   T1 spine = ~40% of full Pier 1 path, gates start at ~75%
#   T2 spine = ~47% of full Pier 4 path, gates start at ~54%
# We use conservative values that work across all pier lengths.
SPLIT_CHECKIN_END  = 0.25   # Security exit: ~25% along full path (within spine)
SPLIT_SECURITY_END = 0.45   # Pier junction: ~45% along full path (end of spine)
SPLIT_PIER_END     = 0.72   # Gate area starts: ~72% along full path (first gates)


def _haversine_degrees(p1, p2):
    dlat = p2[0] - p1[0]
    dlon = (p2[1] - p1[1]) * math.cos(math.radians((p1[0] + p2[0]) / 2))
    return math.sqrt(dlat ** 2 + dlon ** 2)


def _interpolate_segment(p1, p2, step=INTERPOLATION_STEP):
    dist = _haversine_degrees(p1, p2)
    if dist < step:
        return [p1]
    num_steps = max(1, int(dist / step))
    return [
        (p1[0] + (i / num_steps) * (p2[0] - p1[0]),
         p1[1] + (i / num_steps) * (p2[1] - p1[1]))
        for i in range(num_steps)
    ]


def _interpolate_path(nodes):
    if len(nodes) < 2:
        return list(nodes)
    result = []
    for i in range(len(nodes) - 1):
        result.extend(_interpolate_segment(nodes[i], nodes[i + 1]))
    result.append(nodes[-1])
    return result


def _build_full_path(terminal, pathway_key):
    if terminal == 'T1':
        spine = T1_PATHWAYS['spine']
        if pathway_key == 'spine':
            return list(spine)
        pier = T1_PATHWAYS.get(pathway_key, [])
        if not pier:
            return list(spine)
        return list(spine) + list(pier[1:])
    elif terminal == 'T2':
        spine = T2_PATHWAYS['spine']
        if pathway_key == 'spine':
            return list(spine)
        if pathway_key == 'pier_4':
            pier4 = T2_PATHWAYS['pier_4']
            return list(spine) + list(pier4[1:])
        if pathway_key in ('t2_connector', 't2_connector_stop'):
            connector = T2_PATHWAYS['t2_connector']
            return list(spine) + list(connector[1:])
    return []


def _build_t2_to_t1_pier3_path():
    return (
        list(T2_PATHWAYS['spine'])
        + list(T2_PATHWAYS['t2_connector'][1:])
        + list(T1_PATHWAYS['spine'][4:][1:])
        + list(T1_PATHWAYS['pier_3'][1:])
    )


def _slice_path(dense_points, frac_start, frac_end):
    n = len(dense_points)
    if n == 0:
        return []
    i_start = int(frac_start * n)
    i_end   = max(i_start + 1, int(frac_end * n))
    return dense_points[i_start:i_end]


def _get_segment_weights(minutes_to_departure):
    """
    Returns what fraction of passengers are in each terminal segment
    given how many minutes remain until departure.

    Uses overlapping trapezoid windows so transitions are smooth.
    """
    if minutes_to_departure <= 0:
        return {'checkin': 0.0, 'security': 0.0, 'pier': 0.0, 'gate': 0.0}

    m = minutes_to_departure

    def trapezoid(val, rise_start, plateau_start, plateau_end, fall_end):
        if val <= rise_start or val >= fall_end:
            return 0.0
        if val <= plateau_start:
            return (val - rise_start) / max(plateau_start - rise_start, 1)
        if val >= plateau_end:
            return 1.0 - (val - plateau_end) / max(fall_end - plateau_end, 1)
        return 1.0

    w_checkin  = trapezoid(m,  60, 100, 150, 200)
    w_security = trapezoid(m,  30,  60,  90, 120)
    w_pier     = trapezoid(m,  10,  30,  60,  75)
    w_gate     = trapezoid(m,   0,   5,  20,  35)

    total = w_checkin + w_security + w_pier + w_gate
    if total == 0:
        return {'checkin': 1.0, 'security': 0.0, 'pier': 0.0, 'gate': 0.0}

    return {
        'checkin':  w_checkin  / total,
        'security': w_security / total,
        'pier':     w_pier     / total,
        'gate':     w_gate     / total,
    }


class PathwayInterpolator:

    def get_heatmap_points(
        self,
        terminal,
        gate,
        passengers,
        departure_hour,
        departure_minute=0,
        current_hour=12,
        base_weight=1.0,
    ):
        # Normalise terminal
        terminal = (terminal or '').strip().upper().replace(' ', '')
        if terminal == '1':
            terminal = 'T1'
        elif terminal == '2':
            terminal = 'T2'
        if terminal not in ('T1', 'T2'):
            terminal = 'T1'

        # Minutes from midpoint of current hour to departure
        dep_mins     = departure_hour * 60 + departure_minute
        current_mins = current_hour * 60 + 30
        minutes_to_dep = dep_mins - current_mins

        seg_weights = _get_segment_weights(minutes_to_dep)
        if sum(seg_weights.values()) == 0:
            return []

        # Handle missing/excluded gates
        if gate is None or gate.strip() == '':
            return self._spine_only(terminal, passengers, seg_weights, base_weight)

        gate = gate.strip()
        if is_excluded_gate(gate):
            return []

        # Resolve path
        routing = GATE_TO_PATHWAY.get(gate)
        if routing is None:
            if terminal == 'T2' and gate.rstrip('A').isdigit() and 301 <= int(gate.rstrip('A')) <= 307:
                path_nodes = _build_t2_to_t1_pier3_path()
            else:
                return self._spine_only(terminal, passengers, seg_weights, base_weight)
        else:
            resolved_terminal, pathway_key = routing
            if pathway_key == 't2_connector_stop':
                path_nodes = _build_full_path('T2', 't2_connector')
            elif terminal == 'T2' and resolved_terminal == 'T1' and pathway_key == 'pier_3':
                path_nodes = _build_t2_to_t1_pier3_path()
            else:
                path_nodes = _build_full_path(resolved_terminal, pathway_key)

        if not path_nodes:
            return self._spine_only(terminal, passengers, seg_weights, base_weight)

        dense    = _interpolate_path(path_nodes)
        pax_scale = min(1.0, passengers / 180)

        segment_slices = [
            ('checkin',  0.0,               SPLIT_CHECKIN_END,  0.85),
            ('security', SPLIT_CHECKIN_END,  SPLIT_SECURITY_END, 0.85),
            ('pier',     SPLIT_SECURITY_END, SPLIT_PIER_END,     1.0),
            ('gate',     SPLIT_PIER_END,     1.0,                1.0),
        ]

        result = []
        for seg_name, frac_start, frac_end, seg_intensity in segment_slices:
            w = seg_weights[seg_name]
            if w < 0.02:
                continue

            seg_points = _slice_path(dense, frac_start, frac_end)
            if not seg_points:
                continue

            point_weight = round(min(1.0, w * pax_scale * seg_intensity * base_weight), 4)
            if point_weight < 0.02:
                continue

            for lat, lon in seg_points:
                result.append({
                    'lat':    round(lat, 7),
                    'lon':    round(lon, 7),
                    'weight': point_weight,
                })

        return result

    def _spine_only(self, terminal, passengers, seg_weights, base_weight):
        fallback = TERMINAL_FALLBACK.get(terminal)
        if not fallback:
            return []
        resolved_terminal, pathway_key = fallback
        dense     = _interpolate_path(_build_full_path(resolved_terminal, pathway_key))
        pax_scale = min(1.0, passengers / 180)
        result    = []
        checkin_w = seg_weights['checkin'] + seg_weights['security']
        airside_w = seg_weights['pier']    + seg_weights['gate']
        for i, (lat, lon) in enumerate(dense):
            t = i / max(len(dense) - 1, 1)
            w = round(max(0.02, min(1.0, ((1 - t) * checkin_w + t * airside_w) * pax_scale * base_weight)), 4)
            result.append({'lat': round(lat, 7), 'lon': round(lon, 7), 'weight': w})
        return result


def build_flight_heatmap_points(flights_data, current_hour=12):
    """
    Generate combined heatmap points for all flights at the given hour.

    Each flight dict must have:
        terminal         (str)
        gate             (str|None)
        passengers       (int)
        departure_hour   (int)
        departure_minute (int, optional)
    """
    interpolator = PathwayInterpolator()
    all_points   = []

    for flight in flights_data:
        if flight.get('passengers', 0) <= 0:
            continue
        points = interpolator.get_heatmap_points(
            terminal         = flight.get('terminal') or '',
            gate             = flight.get('gate'),
            passengers       = flight.get('passengers', 0),
            departure_hour   = flight.get('departure_hour', 12),
            departure_minute = flight.get('departure_minute', 0),
            current_hour     = current_hour,
        )
        all_points.extend(points)

    return all_points