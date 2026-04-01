/*
Author: Alexander Mackey
Student ID: C22739165
Description: Map page JavaScript - runs only on map.html (Live View).
Handles: Leaflet map initialisation, heatmap loading/display,
         collapsible control panel, intensity slider, layer toggles, filter buttons.

Performance requirements:
- Page load: < 3 seconds
- Heatmap refresh: < 2 seconds (airport switch)
*/

// ===================================
// MAP PAGE GLOBALS
// ===================================

let map;                  // google.maps.Map instance
let heatmapLayer;         // google.maps.visualization.HeatmapLayer instance
let airportMarker;        // google.maps.Marker instance
let infoWindow;           // google.maps.InfoWindow instance

// Phase 3C: store predictions so time slider can scrub without re-fetching
let mapPredictions  = [];  // Array of {hour, passengers, confidence, level}
let activePolylines = [];  // Track active corridor polylines for cleanup

// Phase 3D: gate-driven pathway heatmap cache — prefetched for all 24 hours
// Keys are 0–23, values are arrays of {lat, lon, weight} from /api/heatmap/dynamic/
let heatmapCache = {};     // { [hour]: [{lat, lon, weight}, ...] }

// ===================================
// INIT
// ===================================

// NOTE: initMap() is called automatically by the Google Maps script tag callback.
// (callback=initMap in the script src URL)
// Other initialisation runs inside initMap() once the API is ready.

// ===================================
// MAP INITIALIZATION
// ===================================

/**
 * Initialises the Google Maps instance centred on Dublin Airport.
 * Called automatically via the Google Maps script callback=initMap parameter.
 * Uses Hybrid map type (satellite + road labels) so terminal buildings are visible.
 *
 * Also triggers all other page initialisation that previously ran on DOMContentLoaded,
 * since we need the map API loaded before anything else runs.
 */
function initMap() {
    console.log('🗺️ Google Maps initializing...');

    const dublinAirport = { lat: 53.4213, lng: -6.2701 };

    map = new google.maps.Map(document.getElementById('map'), {
        center: dublinAirport,
        zoom: 15,
        mapTypeId: 'roadmap',    // Satellite + road/label overlay
        disableDefaultUI: false,
        zoomControl: true,
        mapTypeControl: true,          // Lets user switch Map/Satellite/Hybrid
        streetViewControl: false,
        mapTypeControlOptions: {
            position: google.maps.ControlPosition.BOTTOM_LEFT,
            style: google.maps.MapTypeControlStyle.HORIZONTAL_BAR
        },
                streetViewControl: false,      // Not useful for airport terminal view
        fullscreenControl: true,
        gestureHandling: 'greedy'      // Single finger drag on mobile
    });

    // InfoWindow reused for airport marker popup
    infoWindow = new google.maps.InfoWindow();

    // Place airport marker
    airportMarker = new google.maps.Marker({
        position: dublinAirport,
        map: map,
        title: 'Dublin Airport (DUB)',
        icon: {
            url: 'https://maps.google.com/mapfiles/ms/icons/plane.png',
            scaledSize: new google.maps.Size(36, 36),
            anchor: new google.maps.Point(18, 18)
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

    // Run remaining page initialisation now that Google Maps API is ready
    initCollapsiblePanel();
    initMapControls();
    initMapPrediction();

    updateMapStatus('success');
    console.log('✓ Google Maps ready (hybrid, Dublin Airport)');
}

// ===================================
// HEATMAP DATA (Google Maps)
// ===================================

/**
 * Stub kept for compatibility — main.js calls loadHeatmapData() when the
 * airport selector changes. On the Google Maps version the marker is already
 * placed in initMap(); we just re-centre the map and clear any existing heatmap.
 */
function loadHeatmapData() {
    const airport = document.getElementById('airport-select')?.value || 'DUB';

    // Airport coordinates — extend when Cork/Shannon added in Phase 3D
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

    // Clear all visualisation layers when airport changes — user must re-run prediction
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
    const panel      = document.getElementById('control-panel');
    const toggleBtn  = document.getElementById('panel-toggle');

    if (!panel || !toggleBtn) return;

    // Restore last state
    const wasCollapsed = localStorage.getItem('airflow_panel_collapsed') === 'true';
    if (wasCollapsed) panel.classList.add('collapsed');

    toggleBtn.addEventListener('click', function () {
        const isCollapsed = panel.classList.toggle('collapsed');
        localStorage.setItem('airflow_panel_collapsed', isCollapsed);

        // Notify Leaflet map to recalculate size after panel animation
        setTimeout(() => {
            if (map) map.invalidateSize();
        }, 260); // Slightly longer than the CSS transition (250ms)
    });

    console.log('✓ Collapsible panel initialized');
}

// ===================================
// MAP CONTROLS
// ===================================

/**
 * Wires up all control panel interactions:
 * intensity slider, opacity slider, heatmap toggle, refresh button.
 */
function initMapControls() {
    // Intensity slider — updates opacity on next heatmap render
    const intensitySlider = document.getElementById('intensity-slider');
    const intensityValue  = document.getElementById('intensity-value');

    if (intensitySlider && intensityValue) {
        intensitySlider.addEventListener('input', function () {
            intensityValue.textContent = `${this.value}%`;
        });
    }

    // Opacity slider — updates live HeatmapLayer opacity without re-fetching
    const opacitySlider = document.getElementById('opacity-slider');
    const opacityValue  = document.getElementById('opacity-value');

    if (opacitySlider && opacityValue) {
        opacitySlider.addEventListener('input', function () {
            opacityValue.textContent = `${this.value}%`;
            // Apply live to HeatmapLayer if it exists
            if (heatmapLayer) {
                heatmapLayer.set('opacity', this.value / 100);
            }
        });
    }

    // Heatmap layer toggle checkbox — show/hide heatmap without clearing cache
    const heatmapCheckbox = document.getElementById('layer-heatmap');
    if (heatmapCheckbox) {
        heatmapCheckbox.addEventListener('change', function () {
            if (!heatmapLayer) return;
            heatmapLayer.setMap(this.checked ? map : null);
        });
    }

    // Refresh button — re-centres map and clears cache so user can re-run prediction
    const refreshBtn = document.getElementById('refresh-btn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', function () {
            refreshBtn.disabled = true;
            refreshBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Refreshing...';

            loadHeatmapData();

            setTimeout(() => {
                refreshBtn.disabled = false;
                refreshBtn.innerHTML = '<i class="fas fa-rotate"></i> Refresh Data';
                showNotification('Data refreshed', 'success');
            }, 1200);
        });
    }

    console.log('✓ Map controls initialized');
}

// ===================================
// PHASE 3B.5: MAP PREDICTION + DYNAMIC HEATMAP
// ===================================

/**
 * Dublin Airport terminal zone definitions for heatmap blob placement.
 * Coordinates calibrated from Google Maps satellite + OpenStreetMap data.
 *
 * T1 (west):  check-in, security, Pier B (gates 101-119), Pier C (Ryanair)
 * T2 (east):  check-in, security, Pier D, Pier E (transatlantic)
 * Inter-terminal walkway connects both buildings centrally.
 *
 * passenger_pct: proportion of hourly passengers assigned to this zone
 * radius:        Gaussian scatter radius in degrees (~80m per 0.001 deg lat)
 */
const DUBLIN_AIRPORT_ZONES = [
    // Terminal 1
    { name: 'T1 Check-in Hall',    lat: 53.4252, lng: -6.2674, radius: 0.0008, pct: 0.12 },
    { name: 'T1 Security',         lat: 53.4258, lng: -6.2665, radius: 0.0005, pct: 0.10 },
    { name: 'T1 Departure Lounge', lat: 53.4265, lng: -6.2650, radius: 0.0007, pct: 0.08 },
    { name: 'Pier B Gates 101-119',lat: 53.4280, lng: -6.2620, radius: 0.0012, pct: 0.10 },
    { name: 'Pier C Ryanair',      lat: 53.4295, lng: -6.2580, radius: 0.0014, pct: 0.12 },
    // Terminal 2
    { name: 'T2 Check-in Hall',    lat: 53.4272, lng: -6.2440, radius: 0.0008, pct: 0.10 },
    { name: 'T2 Security',         lat: 53.4268, lng: -6.2430, radius: 0.0005, pct: 0.08 },
    { name: 'T2 Departure Lounge', lat: 53.4275, lng: -6.2415, radius: 0.0007, pct: 0.06 },
    { name: 'Pier D Gates',        lat: 53.4282, lng: -6.2390, radius: 0.0013, pct: 0.12 },
    { name: 'Pier E Transatlantic',lat: 53.4270, lng: -6.2355, radius: 0.0010, pct: 0.08 },
    // Central / shared
    { name: 'Inter-terminal Walk', lat: 53.4263, lng: -6.2555, radius: 0.0006, pct: 0.04 },
];

/**
 * Dublin Airport corridor definitions for traffic-style polylines.
 * Each corridor is a sequence of lat/lng waypoints tracing a walking route.
 * Colour is determined dynamically based on relative passenger density.
 *
 * weight: relative importance for passenger load calculation
 */
const DUBLIN_AIRPORT_CORRIDORS = [
    {
        name: 'T1 Main Corridor',
        weight: 0.25,
        path: [
            { lat: 53.4252, lng: -6.2674 },  // T1 entrance
            { lat: 53.4256, lng: -6.2668 },  // check-in
            { lat: 53.4260, lng: -6.2660 },  // security
            { lat: 53.4265, lng: -6.2650 },  // departure lounge
            { lat: 53.4272, lng: -6.2635 },  // pier junction
            { lat: 53.4280, lng: -6.2620 },  // Pier B entrance
        ]
    },
    {
        name: 'Pier B Gates 101-119',
        weight: 0.15,
        path: [
            { lat: 53.4280, lng: -6.2620 },
            { lat: 53.4285, lng: -6.2608 },
            { lat: 53.4290, lng: -6.2595 },
            { lat: 53.4295, lng: -6.2580 },  // Pier C / Ryanair gates
        ]
    },
    {
        name: 'T2 Main Corridor',
        weight: 0.22,
        path: [
            { lat: 53.4272, lng: -6.2440 },  // T2 entrance
            { lat: 53.4270, lng: -6.2432 },  // check-in
            { lat: 53.4268, lng: -6.2422 },  // security
            { lat: 53.4272, lng: -6.2412 },  // departure lounge
            { lat: 53.4278, lng: -6.2400 },  // pier junction
            { lat: 53.4282, lng: -6.2390 },  // Pier D entrance
        ]
    },
    {
        name: 'Pier D/E Gates',
        weight: 0.15,
        path: [
            { lat: 53.4282, lng: -6.2390 },
            { lat: 53.4276, lng: -6.2375 },
            { lat: 53.4270, lng: -6.2360 },
            { lat: 53.4265, lng: -6.2348 },  // Pier E end
        ]
    },
    {
        name: 'Inter-terminal Link',
        weight: 0.12,
        path: [
            { lat: 53.4263, lng: -6.2650 },  // T1 side
            { lat: 53.4263, lng: -6.2610 },
            { lat: 53.4263, lng: -6.2565 },  // midpoint
            { lat: 53.4265, lng: -6.2510 },
            { lat: 53.4268, lng: -6.2470 },
            { lat: 53.4270, lng: -6.2445 },  // T2 side
        ]
    },
    {
        name: 'Arrivals Hall T1',
        weight: 0.06,
        path: [
            { lat: 53.4245, lng: -6.2670 },
            { lat: 53.4248, lng: -6.2660 },
            { lat: 53.4250, lng: -6.2645 },
        ]
    },
    {
        name: 'Arrivals Hall T2',
        weight: 0.05,
        path: [
            { lat: 53.4265, lng: -6.2445 },
            { lat: 53.4266, lng: -6.2435 },
            { lat: 53.4266, lng: -6.2420 },
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

            // Debounce heatmap update: only fire after user stops moving for 150ms
            // Prevents hammering the API on every pixel of slider movement
            clearTimeout(slider._debounce);
            slider._debounce = setTimeout(() => {
                if (mapPredictions.length > 0) updateDynamicHeatmap(hour);
            }, 150);
        });
    }

    console.log('✓ Map prediction (Phase 3B.5) initialized');
}

/**
 * Fetches hourly predictions from the Django API and triggers the
 * initial dynamic heatmap render for the currently selected hour.
 *
 * Performance requirement: < 3 seconds.
 */
async function runMapPrediction() {
    const airport    = document.getElementById('airport-select')?.value || 'DUB';
    const date       = document.getElementById('prediction-date')?.value || getTomorrowString();
    const runBtn     = document.getElementById('btn-run-prediction');
    const loading    = document.getElementById('loading-indicator');
    const statusEl   = document.getElementById('panel-prediction-status');
    const statusTxt  = document.getElementById('panel-status-text');
    const sliderWrap = document.getElementById('panel-slider-wrap');

    runBtn.disabled = true;
    loading.classList.add('active');
    if (statusEl) statusEl.style.display = 'none';

    // Clear stale cache from any previous run
    heatmapCache = {};

    const startTime = performance.now();

    try {
        // Step 1: Fetch hourly passenger totals (used by slider display + chart)
        const response = await fetch(`/api/predictions/hourly/?airport=${airport}&date=${date}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        if (!data.success) throw new Error(data.error || 'Prediction failed');

        mapPredictions = data.predictions;

        // Step 2: Prefetch gate-driven pathway points for all 24 hours in parallel.
        // All requests fire simultaneously — total wait is roughly the slowest single call.
        // Results cached in heatmapCache so slider scrubbing is instant (client-side only).
        if (statusTxt) statusTxt.textContent = 'Loading heatmap data...';
        if (statusEl)  statusEl.style.display = 'flex';

        const hourFetches = Array.from({ length: 24 }, (_, hour) =>
            fetch(`/api/heatmap/dynamic/?airport=${airport}&date=${date}&hour=${hour}`)
                .then(r => r.json())
                .then(d => { heatmapCache[hour] = d.success ? (d.points || []) : []; })
                .catch(() => { heatmapCache[hour] = []; })
        );

        await Promise.all(hourFetches);

        const elapsed = Math.round(performance.now() - startTime);

        // Step 3: Render the current slider hour now that cache is populated
        const currentHour = parseInt(document.getElementById('time-slider')?.value || 12);
        updatePanelSliderDisplay(currentHour);
        updateDynamicHeatmap(currentHour);

        // Show slider and status badge
        if (sliderWrap) sliderWrap.style.display = 'block';
        if (statusEl && statusTxt) {
            const peak = data.summary;
            statusTxt.textContent =
                `${data.summary.total_passengers.toLocaleString()} pax — peak ${peak.peak_hour}:00 (${elapsed}ms)`;
            statusEl.style.display = 'flex';
        }

        showNotification(
            `Heatmap updated — ${data.summary.total_passengers.toLocaleString()} passengers`,
            'success'
        );
        console.log(`✓ Map prediction + heatmap cache ready in ${elapsed}ms`);

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
 * Main visualisation function — renders the gate-driven pathway heatmap
 * for the selected hour using pre-fetched cached points.
 *
 * Cache is populated by runMapPrediction() via Promise.all() across all 24 hours.
 * This function is purely client-side after that — no network calls, stays instant.
 *
 * Performance requirement: < 0.5 seconds (client-side only after cache load).
 *
 * @param {number} hour - Hour to visualise (0–23)
 */
function updateDynamicHeatmap(hour) {
    if (mapPredictions.length === 0) return;

    // Clear existing layers before rendering new ones
    clearVisualisationLayers();

    const prediction = mapPredictions.find(p => p.hour === hour);
    const passengers = prediction ? prediction.passengers : 0;

    if (passengers === 0) {
        console.log(`Hour ${hour}: 0 passengers — visualisation cleared`);
        return;
    }

    // Read pre-fetched pathway points from cache
    const cachedPoints = heatmapCache[hour] || [];

    if (cachedPoints.length === 0) {
        console.log(`Hour ${hour}: no pathway points in cache`);
        return;
    }

    // Get user intensity preference from slider
    const intensitySlider = document.getElementById('intensity-slider');
    const userIntensity   = intensitySlider ? intensitySlider.value / 100 : 0.8;

    // Convert cached {lat, lon, weight} points to Google Maps LatLng objects
    const heatmapData = cachedPoints.map(p => ({
        location: new google.maps.LatLng(p.lat, p.lon),
        weight:   p.weight,
    }));

    // DEBUG ONLY — uncomment to visualise old-style corridor polylines
    // const maxPassengers = Math.max(...mapPredictions.map(p => p.passengers));
    // const relativeLoad  = maxPassengers > 0 ? passengers / maxPassengers : 0;
    // drawCorridors(relativeLoad, userIntensity);

    // Render HeatmapLayer with gate-driven pathway points
    heatmapLayer = new google.maps.visualization.HeatmapLayer({
        data:         heatmapData,
        map:          map,
        radius:       20,
        opacity:      0.75 * userIntensity,
        dissipating:  true,
        maxIntensity: 1.0,   // Must be set — prevents auto-scaling from hiding gate points
        gradient: [
            'rgba(0, 0, 0, 0)',
            'rgba(0, 176, 80,  0.8)',   // Green   — low density
            'rgba(255, 255, 0, 0.8)',   // Yellow  — medium
            'rgba(255, 140, 0, 0.9)',   // Orange  — high
            'rgba(255, 0,   0, 0.9)',   // Red     — very high
            'rgba(139, 0,   0, 1.0)'    // Dark red — peak
        ]
    });

    console.log(`✓ Heatmap: hour ${hour}, ${passengers} pax, ${cachedPoints.length} points (cached)`);
}

function clearVisualisationLayers() {
    // Remove polylines
    activePolylines.forEach(line => line.setMap(null));
    activePolylines = [];

    // Remove heatmap layer
    if (heatmapLayer) {
        heatmapLayer.setMap(null);
        heatmapLayer = null;
    }
}

/**
 * Draws traffic-style coloured polylines along all terminal corridors.
 * Colour maps passenger load to Google Maps traffic colours:
 *   0–30%:  green  (free flowing)
 *   30–60%: yellow (light)
 *   60–80%: orange (moderate)
 *   80–100%: red   (heavy / standstill)
 *
 * Each corridor gets an independent load based on its weight and the
 * global relative passenger count for that hour.
 *
 * @param {number} relativeLoad  - 0–1, overall load vs busiest hour
 * @param {number} userIntensity - 0–1, from intensity slider
 */
function drawCorridors(relativeLoad, userIntensity) {
    DUBLIN_AIRPORT_CORRIDORS.forEach(corridor => {
        // Each corridor has its own load weighted by its passenger share
        const corridorLoad = Math.min(1.0, relativeLoad * (1 + corridor.weight));

        const strokeColor   = getTrafficColour(corridorLoad);
        const strokeWeight  = Math.max(4, Math.round(6 + corridorLoad * 6)); // 4–12px
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

        // Tooltip on hover
        polyline.addListener('mouseover', function (e) {
            const pct = (corridorLoad * 100).toFixed(0);
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
 * Matches Google's traffic layer colour scheme exactly.
 *
 * @param {number} load - 0.0 (empty) to 1.0 (maximum congestion)
 * @returns {string} Hex colour string
 */
function getTrafficColour(load) {
    if (load < 0.30) return '#00B050';  // Green    — free flowing
    if (load < 0.50) return '#92D050';  // Lt green — light
    if (load < 0.65) return '#FFFF00';  // Yellow   — moderate light
    if (load < 0.80) return '#FF8C00';  // Orange   — moderate heavy
    if (load < 0.92) return '#FF0000';  // Red      — heavy
    return '#8B0000';                   // Dark red — standstill
}

/**
 * Draws heatmap blobs on key passenger zones (check-in, security, gates).
 * Uses Google Maps HeatmapLayer with traffic-style gradient.
 * Blobs are kept subtle so polylines remain the dominant visual element.
 *
 * @param {number} totalPassengers  - Passenger count for this hour
 * @param {number} relativeLoad     - 0–1 vs peak hour
 * @param {number} userIntensity    - 0–1 from intensity slider
 */
function drawHeatmapBlobs(totalPassengers, relativeLoad, userIntensity) {
    const points    = generateHeatmapPoints(totalPassengers, relativeLoad);
    if (points.length === 0) return;

    heatmapLayer = new google.maps.visualization.HeatmapLayer({
        data:        points,
        map:         map,
        radius:      25,
        opacity:     0.55 * userIntensity,  // Kept subtle — polylines are primary
        dissipating: true,
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

/**
 * Generates weighted LatLng points for heatmap blob zones.
 * Uses Box-Muller Gaussian scatter for realistic crowd clustering.
 *
 * @param {number} totalPassengers - Passenger count for this hour
 * @param {number} relativeLoad    - 0–1 vs peak hour
 * @returns {Array} Array of {location: LatLng, weight: number}
 */
function generateHeatmapPoints(totalPassengers, relativeLoad) {
    const points    = [];
    const maxPoints = Math.min(300, Math.max(30, Math.round(totalPassengers / 20)));

    DUBLIN_AIRPORT_ZONES.forEach(zone => {
        const zoneCount  = Math.round(maxPoints * zone.pct);
        const zoneWeight = relativeLoad * zone.pct * 10;

        for (let i = 0; i < zoneCount; i++) {
            const u1       = Math.random();
            const u2       = Math.random();
            const gaussian = Math.sqrt(-2 * Math.log(u1 + 1e-10)) * Math.cos(2 * Math.PI * u2);

            const lat    = zone.lat + gaussian * zone.radius;
            const lng    = zone.lng + gaussian * zone.radius * 1.2;
            const weight = Math.min(10, Math.max(0.5, zoneWeight + (Math.random() - 0.5) * 1.5));

            points.push({
                location: new google.maps.LatLng(lat, lng),
                weight:   weight
            });
        }
    });

    return points;
}