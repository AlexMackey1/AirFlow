/*
 * Author: Alexander Mackey
 * Student ID: C22739165
 * Description: Map page JavaScript - runs only on map.html (Live View).
 * Handles: Google Maps initialisation, gate-driven pathway heatmap (Phase 3D),
 *          traffic-style corridor polylines, collapsible panel, time slider.
 *
 * Performance requirements:
 * - Page load:        < 3 seconds
 * - Heatmap refresh:  < 0.5 seconds (slider scrub uses cached predictions)
 * - Airport switch:   < 2 seconds
 *
 * Phase 3D change: updateDynamicHeatmap() now fetches from /api/heatmap/dynamic/
 * which returns gate-driven pathway points ({lat, lon, weight}) from
 * PathwayInterpolator. Client-side blob generation (generateHeatmapPoints) removed.
 *
 * Note: Google Maps HeatmapLayer deprecated May 2025, removed May 2026.
 * Works fine for April 2026 deadline. Flag as known limitation in report.
 */

// ===================================
// MAP PAGE GLOBALS
// ===================================

let map;                  // google.maps.Map instance
let heatmapLayer;         // google.maps.visualization.HeatmapLayer instance
let airportMarker;        // google.maps.Marker instance
let infoWindow;           // google.maps.InfoWindow instance

// Store predictions so the time slider can scrub without re-running the algorithm
let mapPredictions  = [];  // Array of {hour, passengers, confidence, level}
let activePolylines = [];  // Track active corridor polylines for cleanup

// ===================================
// MAP INITIALIZATION
// ===================================

/**
 * Initialises the Google Maps instance centred on Dublin Airport.
 * Called automatically via the Google Maps script callback=initMap parameter.
 * Uses roadmap type — shows terminal floor plans at high zoom.
 *
 * All other page initialisation runs inside here since the Maps API must be
 * loaded before any google.maps.* calls are valid.
 */
function initMap() {
    console.log('🗺️ Google Maps initializing...');

    const dublinAirport = { lat: 53.4213, lng: -6.2701 };

    map = new google.maps.Map(document.getElementById('map'), {
        center:     dublinAirport,
        zoom:       16,
        mapTypeId:  'roadmap',
        disableDefaultUI:    false,
        zoomControl:         true,
        mapTypeControl:      true,
        streetViewControl:   false,
        fullscreenControl:   true,
        gestureHandling:     'greedy',
        mapTypeControlOptions: {
            position: google.maps.ControlPosition.BOTTOM_LEFT,
            style:    google.maps.MapTypeControlStyle.HORIZONTAL_BAR
        },
    });

    infoWindow = new google.maps.InfoWindow();

    // Airport marker
    airportMarker = new google.maps.Marker({
        position: dublinAirport,
        map:      map,
        title:    'Dublin Airport (DUB)',
        icon: {
            url:        'https://maps.google.com/mapfiles/ms/icons/plane.png',
            scaledSize: new google.maps.Size(36, 36),
            anchor:     new google.maps.Point(18, 18)
        }
    });

    airportMarker.addListener('click', () => {
        infoWindow.setContent(`
            <div style="font-family:inherit;padding:4px 2px;">
                <strong style="font-size:15px;">Dublin Airport</strong><br>
                <span style="color:#666;font-size:13px;">DUB — Dublin, Ireland</span><br>
                <em style="font-size:11px;color:#999;">Real-time Passenger Flow</em>
            </div>
        `);
        infoWindow.open(map, airportMarker);
    });

    initCollapsiblePanel();
    initMapControls();
    initMapPrediction();

    updateMapStatus('success');
    console.log('✓ Google Maps ready (roadmap, Dublin Airport)');
}

// ===================================
// HEATMAP DATA
// ===================================

/**
 * Called by main.js when the airport selector changes.
 * Re-centres the map and clears all visualisation layers so the user
 * must re-run prediction for the new airport.
 */
function loadHeatmapData() {
    const airport = document.getElementById('airport-select')?.value || 'DUB';

    const AIRPORT_COORDS = {
        DUB: { lat: 53.4213, lng: -6.2701, name: 'Dublin Airport' },
        ORK: { lat: 51.8413, lng: -8.4912, name: 'Cork Airport' },
        SNN: { lat: 52.7020, lng: -8.9248, name: 'Shannon Airport' }
    };

    const coords = AIRPORT_COORDS[airport] || AIRPORT_COORDS.DUB;

    if (map) {
        map.setCenter(coords);
        map.setZoom(15);
    }

    clearVisualisationLayers();
    mapPredictions = [];

    const sliderWrap = document.getElementById('panel-slider-wrap');
    const statusEl   = document.getElementById('panel-prediction-status');
    if (sliderWrap) sliderWrap.style.display = 'none';
    if (statusEl)   statusEl.style.display   = 'none';

    updateMapStatus('success');
    showNotification(`Switched to ${coords.name}`, 'info');
    console.log(`✓ Map centred on ${coords.name}`);
}

/**
 * Updates the status bar connection/data indicators.
 * @param {'loading'|'success'|'error'} status
 */
function updateMapStatus(status) {
    const connectionStatus = document.getElementById('connection-status');
    const dataStatus       = document.getElementById('data-status');

    if (!connectionStatus || !dataStatus) return;

    switch (status) {
        case 'loading':
            connectionStatus.textContent = 'Loading...';
            dataStatus.textContent       = 'Fetching Data';
            break;
        case 'success':
            connectionStatus.textContent = 'Connected';
            dataStatus.textContent       = 'Data Loaded';
            break;
        case 'error':
            connectionStatus.textContent = 'Error';
            dataStatus.textContent       = 'Failed';
            break;
    }
}

// ===================================
// COLLAPSIBLE PANEL
// ===================================

/**
 * Initialises the collapse/expand toggle for the left control panel.
 * Stores state in localStorage so it persists across page refreshes.
 */
function initCollapsiblePanel() {
    const panel     = document.getElementById('control-panel');
    const toggleBtn = document.getElementById('panel-toggle');

    if (!panel || !toggleBtn) return;

    const wasCollapsed = localStorage.getItem('airflow_panel_collapsed') === 'true';
    if (wasCollapsed) panel.classList.add('collapsed');

    toggleBtn.addEventListener('click', function () {
        const isCollapsed = panel.classList.toggle('collapsed');
        localStorage.setItem('airflow_panel_collapsed', isCollapsed);

        // Google Maps needs a nudge after the panel animation completes
        setTimeout(() => { if (map) google.maps.event.trigger(map, 'resize'); }, 260);
    });

    console.log('✓ Collapsible panel initialized');
}

// ===================================
// MAP CONTROLS
// ===================================

/**
 * Wires up all control panel interactions:
 * intensity slider, layer checkboxes, filter buttons, refresh button.
 */
function initMapControls() {
    // Intensity slider — live label update; updates heatmap opacity if active
    const intensitySlider = document.getElementById('intensity-slider');
    const intensityValue  = document.getElementById('intensity-value');

    if (intensitySlider && intensityValue) {
        intensitySlider.addEventListener('input', function () {
            intensityValue.textContent = `${this.value}%`;
        });

        intensitySlider.addEventListener('change', function () {
            // Update opacity on the live heatmap layer without re-fetching
            if (heatmapLayer) {
                heatmapLayer.setOptions({ opacity: 0.55 * (this.value / 100) });
            }
        });
    }

    // Heatmap layer toggle checkbox
    const heatmapCheckbox = document.getElementById('layer-heatmap');
    if (heatmapCheckbox) {
        heatmapCheckbox.addEventListener('change', function () {
            if (!heatmapLayer) return;
            heatmapLayer.setMap(this.checked ? map : null);
        });
    }

    // Gate labels / Terminal zones — placeholders for future phases
    const gatesCheckbox     = document.getElementById('layer-gates');
    const terminalsCheckbox = document.getElementById('layer-terminals');

    if (gatesCheckbox) {
        gatesCheckbox.addEventListener('change', function () {
            showNotification('Gate labels: coming soon', 'info');
        });
    }

    if (terminalsCheckbox) {
        terminalsCheckbox.addEventListener('change', function () {
            showNotification('Terminal zones: coming soon', 'info');
        });
    }

    // Filter buttons (departure/arrival)
    const filterButtons = document.querySelectorAll('.filter-btn');
    filterButtons.forEach(btn => {
        btn.addEventListener('click', function () {
            filterButtons.forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            showNotification(`Filter: ${this.dataset.filter}`, 'info');
        });
    });

    // Refresh button
    const refreshBtn = document.getElementById('refresh-btn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', function () {
            refreshBtn.disabled  = true;
            refreshBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Refreshing...';

            loadHeatmapData();

            setTimeout(() => {
                refreshBtn.disabled  = false;
                refreshBtn.innerHTML = '<i class="fas fa-rotate"></i> Refresh Data';
                showNotification('Data refreshed', 'success');
            }, 1200);
        });
    }

    console.log('✓ Map controls initialized');
}

// ===================================
// PHASE 3D: GATE-DRIVEN PATHWAY HEATMAP
// ===================================

/**
 * Dublin Airport corridor definitions for traffic-style polylines.
 * Each corridor is a sequence of lat/lng waypoints tracing a walking route.
 * Colour is determined dynamically by relative passenger density.
 *
 * These are separate from the gate-driven pathway heatmap — the polylines
 * give a quick at-a-glance traffic-style summary while the HeatmapLayer
 * shows the precise passenger density along real terminal paths.
 *
 * weight: relative importance for passenger load calculation (higher = busier corridor)
 */
const DUBLIN_AIRPORT_CORRIDORS = [
    {
        name:   'T1 Main Corridor',
        weight: 0.25,
        path: [
            { lat: 53.4276, lng: -6.2442 },   // T1 check-in entrance
            { lat: 53.4273, lng: -6.2441 },   // T1 check-in middle
            { lat: 53.4269, lng: -6.2435 },   // T1 security entrance
            { lat: 53.4266, lng: -6.2437 },   // T1 security middle
            { lat: 53.4265, lng: -6.2439 },   // T1 security exit
            { lat: 53.4268, lng: -6.2444 },   // T1 duty free entrance
            { lat: 53.4270, lng: -6.2447 },   // Pier 3 junction
            { lat: 53.4272, lng: -6.2450 },   // Duty free mid
            { lat: 53.4283, lng: -6.2457 },   // Duty free end / Pier 1+2 junction
        ]
    },
    {
        name:   'T1 Pier 1 (Ryanair)',
        weight: 0.20,
        path: [
            { lat: 53.4283, lng: -6.2457 },   // Junction
            { lat: 53.4290, lng: -6.2449 },
            { lat: 53.4297, lng: -6.2443 },   // Pier 1 bend
            { lat: 53.4305, lng: -6.2453 },
            { lat: 53.4306, lng: -6.2465 },   // Gate 102
            { lat: 53.4307, lng: -6.2488 },   // Gate 107
            { lat: 53.4307, lng: -6.2506 },   // Gate 110-113
        ]
    },
    {
        name:   'T1 Pier 2',
        weight: 0.12,
        path: [
            { lat: 53.4283, lng: -6.2457 },   // Junction
            { lat: 53.4287, lng: -6.2462 },
            { lat: 53.4285, lng: -6.2469 },
            { lat: 53.4283, lng: -6.2474 },
            { lat: 53.4280, lng: -6.2480 },   // Pier 2 end
        ]
    },
    {
        name:   'T1 Pier 3',
        weight: 0.10,
        path: [
            { lat: 53.4270, lng: -6.2447 },   // Pier 3 junction
            { lat: 53.4269, lng: -6.2448 },
            { lat: 53.4266, lng: -6.2453 },
            { lat: 53.4264, lng: -6.2456 },
            { lat: 53.4262, lng: -6.2459 },   // Rotunda
        ]
    },
    {
        name:   'T2 Main Corridor',
        weight: 0.22,
        path: [
            { lat: 53.4265, lng: -6.2398 },   // T2 check-in entrance
            { lat: 53.4263, lng: -6.2399 },   // T2 check-in
            { lat: 53.4260, lng: -6.2402 },   // T2 security
            { lat: 53.4256, lng: -6.2405 },   // T2 security exit
            { lat: 53.4256, lng: -6.2405 },   // Duty free entrance
            { lat: 53.4255, lng: -6.2406 },   // Duty free middle
            { lat: 53.4256, lng: -6.2412 },   // Duty free left (branch point)
            { lat: 53.4253, lng: -6.2408 },   // Pier entrance
        ]
    },
    {
        name:   'T2 Pier 4',
        weight: 0.15,
        path: [
            { lat: 53.4256, lng: -6.2412 },   // Duty free left branch
            { lat: 53.4251, lng: -6.2412 },
            { lat: 53.4247, lng: -6.2411 },   // Gate 407
            { lat: 53.4242, lng: -6.2426 },   // Gate 401/411
            { lat: 53.4237, lng: -6.2435 },   // Gate 403/415
            { lat: 53.4232, lng: -6.2444 },   // Gate 405/419
            { lat: 53.4227, lng: -6.2451 },   // Gate 423-426
        ]
    },
    {
        name:   'T2 Connector',
        weight: 0.08,
        path: [
            { lat: 53.4256, lng: -6.2412 },   // Duty free left
            { lat: 53.4255, lng: -6.2414 },   // Gate 336/337
            { lat: 53.4258, lng: -6.2425 },   // Gate 335/334
            { lat: 53.4259, lng: -6.2430 },   // Gate 332
            { lat: 53.4260, lng: -6.2431 },   // Connector start
            { lat: 53.4262, lng: -6.2434 },   // Connector end
            { lat: 53.4264, lng: -6.2437 },   // Rejoin T1 security
        ]
    },
];

/**
 * Initialises the Run Prediction button and time slider in the panel.
 * Sets the date picker to tomorrow by default.
 */
function initMapPrediction() {
    const dateInput = document.getElementById('prediction-date');
    if (dateInput) dateInput.value = getTomorrowString();

    const runBtn = document.getElementById('btn-run-prediction');
    if (runBtn) runBtn.addEventListener('click', runMapPrediction);

    const slider = document.getElementById('time-slider');
    if (slider) {
        slider.addEventListener('input', function () {
            const hour = parseInt(this.value);
            updatePanelSliderDisplay(hour);

            // Debounce: only fire API call after user stops moving slider for 200ms.
            // Prevents hammering the endpoint on every pixel of movement.
            clearTimeout(slider._debounce);
            slider._debounce = setTimeout(() => {
                if (mapPredictions.length > 0) updateDynamicHeatmap(hour);
            }, 200);
        });
    }

    console.log('✓ Map prediction (Phase 3D) initialized');
}

/**
 * Fetches hourly predictions from the Django API and triggers the
 * initial dynamic heatmap render for the currently selected hour.
 *
 * Performance requirement: < 3 seconds total including algorithm run.
 */
async function runMapPrediction() {
    const airport    = document.getElementById('airport-select')?.value || 'DUB';
    const date       = document.getElementById('prediction-date')?.value || getTomorrowString();
    const runBtn     = document.getElementById('btn-run-prediction');
    const loading    = document.getElementById('loading-indicator');
    const statusEl   = document.getElementById('panel-prediction-status');
    const statusTxt  = document.getElementById('panel-status-text');
    const sliderWrap = document.getElementById('panel-slider-wrap');

    runBtn.disabled  = true;
    loading.classList.add('active');
    if (statusEl) statusEl.style.display = 'none';

    const startTime = performance.now();

    try {
        const response = await fetch(`/api/predictions/hourly/?airport=${airport}&date=${date}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();

        if (!data.success) throw new Error(data.error || 'Prediction failed');

        mapPredictions  = data.predictions;
        const elapsed   = Math.round(performance.now() - startTime);

        // Render heatmap for whatever hour the slider is currently on
        const currentHour = parseInt(document.getElementById('time-slider')?.value || 12);
        updatePanelSliderDisplay(currentHour);
        await updateDynamicHeatmap(currentHour);

        if (sliderWrap) sliderWrap.style.display = 'block';
        if (statusEl && statusTxt) {
            const peak = data.summary;
            statusTxt.textContent =
                `${peak.total_passengers.toLocaleString()} pax — peak ${peak.peak_hour}:00 (${elapsed}ms)`;
            statusEl.style.display = 'flex';
        }

        showNotification(
            `Heatmap updated — ${data.summary.total_passengers.toLocaleString()} passengers`,
            'success'
        );
        console.log(`✓ Map prediction done in ${elapsed}ms`);

    } catch (error) {
        console.error('Map prediction error:', error);
        showNotification('Prediction failed. Check server.', 'error');
    } finally {
        runBtn.disabled = false;
        loading.classList.remove('active');
    }
}

/**
 * Updates the hour label and passenger count in the panel slider header.
 *
 * @param {number} hour - Selected hour (0–23)
 */
function updatePanelSliderDisplay(hour) {
    const hourEl = document.getElementById('panel-hour-display');
    const paxEl  = document.getElementById('panel-pax-display');

    if (hourEl) hourEl.textContent = `${hour.toString().padStart(2, '0')}:00`;

    if (paxEl) {
        const prediction = mapPredictions.find(p => p.hour === hour);
        paxEl.textContent = prediction
            ? `${prediction.passengers.toLocaleString()} pax`
            : '0 pax';
    }
}

/**
 * Main visualisation function for Phase 3D.
 *
 * Fetches gate-driven pathway heatmap points from /api/heatmap/dynamic/ for
 * the selected hour, then renders:
 *   1. Traffic-style polyline corridors (colour = passenger load)
 *   2. HeatmapLayer using the interpolated pathway points from the server
 *
 * The server returns points as {lat, lon, weight} dicts — we convert these
 * to google.maps.LatLng objects here before passing to HeatmapLayer.
 *
 * Performance: the API call is the bottleneck (algorithm + DB query).
 * Target < 0.5s. Slider is debounced at 200ms to avoid over-calling.
 *
 * @param {number} hour - Hour to visualise (0–23)
 */
async function updateDynamicHeatmap(hour) {
    if (mapPredictions.length === 0) return;

    const prediction    = mapPredictions.find(p => p.hour === hour);
    const passengers    = prediction ? prediction.passengers : 0;
    const maxPassengers = Math.max(...mapPredictions.map(p => p.passengers));
    const relativeLoad  = maxPassengers > 0 ? passengers / maxPassengers : 0;

    // Clear existing layers before drawing new ones
    clearVisualisationLayers();

    if (passengers === 0) {
        console.log(`Hour ${hour}: 0 passengers — visualisation cleared`);
        return;
    }

    const airport = document.getElementById('airport-select')?.value || 'DUB';
    const date    = document.getElementById('prediction-date')?.value || getTomorrowString();

    const intensitySlider = document.getElementById('intensity-slider');
    const userIntensity   = intensitySlider ? intensitySlider.value / 100 : 0.8;

    // 1. Draw traffic-style corridor polylines (purely client-side, no fetch)
    drawCorridors(relativeLoad, userIntensity);

    // 2. Fetch gate-driven pathway points from server and draw HeatmapLayer
    try {
        const response = await fetch(
            `/api/heatmap/dynamic/?airport=${airport}&date=${date}&hour=${hour}`
        );
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();

        if (!data.success) throw new Error(data.error || 'Heatmap fetch failed');

        // Convert server {lat, lon, weight} dicts to HeatmapLayer-compatible objects.
        // HeatmapLayer requires {location: google.maps.LatLng, weight: number}.
        const heatmapData = data.points.map(p => ({
            location: new google.maps.LatLng(p.lat, p.lon),
            weight:   p.weight        // Weights are pre-scaled by interpolator per segment
        }));

        if (heatmapData.length > 0) {
            heatmapLayer = new google.maps.visualization.HeatmapLayer({
                data:         heatmapData,
                map:          map,
                radius:       15,
                opacity:      0.7 * userIntensity,
                dissipating:  true,
                maxIntensity: 1.0,
                gradient: [
                    'rgba(0, 0, 0, 0)',
                    'rgba(0, 176, 80,  0.8)',   // Green
                    'rgba(255, 255, 0, 0.8)',   // Yellow
                    'rgba(255, 140, 0, 0.9)',   // Orange
                    'rgba(255, 0,   0, 0.9)',   // Red
                    'rgba(139, 0,   0, 1.0)'    // Dark red
                ]
            });
        }

        console.log(
            `✓ Heatmap (3D): hour ${hour}, ${passengers} pax, ` +
            `${data.point_count} pathway points, load ${(relativeLoad * 100).toFixed(0)}%`
        );

    } catch (error) {
        console.error('Dynamic heatmap fetch error:', error);
        showNotification('Heatmap update failed. Check server.', 'error');
    }
}

/**
 * Removes all active polylines and the heatmap layer from the map.
 */
function clearVisualisationLayers() {
    activePolylines.forEach(line => line.setMap(null));
    activePolylines = [];

    if (heatmapLayer) {
        heatmapLayer.setMap(null);
        heatmapLayer = null;
    }
}

/**
 * Draws traffic-style coloured polylines along all terminal corridors.
 * Colour maps passenger load to Google Maps traffic colours:
 *   0–30%:  green  (free flowing)
 *   30–50%: light green
 *   50–65%: yellow (moderate)
 *   65–80%: orange (heavy)
 *   80–92%: red
 *   92%+:   dark red (standstill)
 *
 * @param {number} relativeLoad  - 0–1, overall load vs busiest hour
 * @param {number} userIntensity - 0–1, from intensity slider
 */
function drawCorridors(relativeLoad, userIntensity) {
    DUBLIN_AIRPORT_CORRIDORS.forEach(corridor => {
        const corridorLoad  = Math.min(1.0, relativeLoad * (1 + corridor.weight));
        const strokeColor   = getTrafficColour(corridorLoad);
        const strokeWeight  = Math.max(4, Math.round(6 + corridorLoad * 6));   // 4–12px
        const strokeOpacity = Math.min(1.0, 0.75 * userIntensity + corridorLoad * 0.25);

        const polyline = new google.maps.Polyline({
            path:          corridor.path,
            geodesic:      true,
            strokeColor:   strokeColor,
            strokeOpacity: strokeOpacity,
            strokeWeight:  strokeWeight,
            map:           map,
            zIndex:        10
        });

        polyline.addListener('mouseover', function (e) {
            const pct   = (corridorLoad * 100).toFixed(0);
            const label = corridorLoad < 0.3 ? 'Free flowing' :
                          corridorLoad < 0.6 ? 'Light congestion' :
                          corridorLoad < 0.8 ? 'Moderate congestion' : 'Heavy congestion';

            infoWindow.setContent(`
                <div style="font-family:inherit;padding:4px 2px;min-width:160px;">
                    <strong style="font-size:13px;">${corridor.name}</strong><br>
                    <span style="color:${strokeColor};font-weight:600;">${label}</span><br>
                    <span style="color:#666;font-size:12px;">Load: ${pct}% of peak capacity</span>
                </div>
            `);
            infoWindow.setPosition(e.latLng);
            infoWindow.open(map);
        });

        polyline.addListener('mouseout', () => infoWindow.close());
        activePolylines.push(polyline);
    });
}

/**
 * Returns a Google Maps traffic-style hex colour for a given load value.
 *
 * @param {number} load - 0.0 (empty) to 1.0 (maximum congestion)
 * @returns {string} Hex colour string
 */
function getTrafficColour(load) {
    if (load < 0.30) return '#00B050';   // Green     — free flowing
    if (load < 0.50) return '#92D050';   // Lt green  — light
    if (load < 0.65) return '#FFFF00';   // Yellow    — moderate
    if (load < 0.80) return '#FF8C00';   // Orange    — moderate heavy
    if (load < 0.92) return '#FF0000';   // Red       — heavy
    return '#8B0000';                    // Dark red  — standstill
}