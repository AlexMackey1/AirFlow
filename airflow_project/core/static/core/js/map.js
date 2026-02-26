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
let mapPredictions = [];  // Array of {hour, passengers, confidence, level}

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
 * intensity slider, layer checkboxes, filter buttons, refresh button.
 */
function initMapControls() {
    // Intensity slider - live update label, debounced heatmap update
    const intensitySlider = document.getElementById('intensity-slider');
    const intensityValue  = document.getElementById('intensity-value');

    if (intensitySlider && intensityValue) {
        intensitySlider.addEventListener('input', function () {
            intensityValue.textContent = `${this.value}%`;
        });

        intensitySlider.addEventListener('change', function () {
            // Only update heatmap options if layer exists (no re-fetch needed)
            if (heatLayer) {
                heatLayer.setOptions({ max: this.value / 100 });
            }
        });
    }

    // Heatmap layer toggle checkbox
    const heatmapCheckbox = document.getElementById('layer-heatmap');
    if (heatmapCheckbox) {
        heatmapCheckbox.addEventListener('change', function () {
            if (!heatLayer) return;
            if (this.checked) map.addLayer(heatLayer);
            else              map.removeLayer(heatLayer);
        });
    }

    // Gate labels / Terminal zones checkboxes (future feature placeholders)
    const gatesCheckbox     = document.getElementById('layer-gates');
    const terminalsCheckbox = document.getElementById('layer-terminals');

    if (gatesCheckbox) {
        gatesCheckbox.addEventListener('change', function () {
            showNotification('Gate labels: coming in Phase 3B.5', 'info');
        });
    }

    if (terminalsCheckbox) {
        terminalsCheckbox.addEventListener('change', function () {
            showNotification('Terminal zones: coming in Phase 3B.5', 'info');
        });
    }

    // Filter buttons (departure/arrival filter - placeholder for Phase 3C data)
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
    const airport   = document.getElementById('airport-select')?.value || 'DUB';
    const date      = document.getElementById('prediction-date')?.value || getTomorrowString();
    const runBtn    = document.getElementById('btn-run-prediction');
    const loading   = document.getElementById('loading-indicator');
    const statusEl  = document.getElementById('panel-prediction-status');
    const statusTxt = document.getElementById('panel-status-text');
    const sliderWrap = document.getElementById('panel-slider-wrap');

    runBtn.disabled = true;
    loading.classList.add('active');
    if (statusEl) statusEl.style.display = 'none';

    const startTime = performance.now();

    try {
        const response = await fetch(`/api/predictions/hourly/?airport=${airport}&date=${date}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();

        if (!data.success) throw new Error(data.error || 'Prediction failed');

        mapPredictions = data.predictions;
        const elapsed  = Math.round(performance.now() - startTime);

        // Render heatmap for the slider's current hour
        const currentHour = parseInt(document.getElementById('time-slider')?.value || 12);
        updatePanelSliderDisplay(currentHour);
        updateDynamicHeatmap(currentHour);

        // Show slider and success badge
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
 * Main visualisation function — renders heatmap blobs for key terminal zones.
 * Corridor polylines removed (Phase 3D: will revisit with real gate data).
 *
 * Performance requirement: < 0.5 seconds (purely client-side).
 *
 * @param {number} hour - Hour to visualise (0–23)
 */
function updateDynamicHeatmap(hour) {
    if (mapPredictions.length === 0) return;

    const prediction    = mapPredictions.find(p => p.hour === hour);
    const passengers    = prediction ? prediction.passengers : 0;
    const maxPassengers = Math.max(...mapPredictions.map(p => p.passengers));
    const relativeLoad  = maxPassengers > 0 ? passengers / maxPassengers : 0;

    // Clear existing heatmap layer
    clearVisualisationLayers();

    if (passengers === 0) {
        console.log(`Hour ${hour}: 0 passengers — visualisation cleared`);
        return;
    }

    // Get user intensity preference
    const intensitySlider = document.getElementById('intensity-slider');
    const userIntensity   = intensitySlider ? intensitySlider.value / 100 : 0.8;

    drawHeatmapBlobs(passengers, relativeLoad, userIntensity);

    console.log(`✓ Visualisation: hour ${hour}, ${passengers} pax, load ${(relativeLoad*100).toFixed(0)}%`);
}

function clearVisualisationLayers() {
    if (heatmapLayer) {
        heatmapLayer.setMap(null);
        heatmapLayer = null;
    }
}


/**
 * Draws heatmap blobs on key passenger zones (check-in, security, gates).
 * Uses Google Maps HeatmapLayer with traffic-style gradient.
 * Coordinates will be refined once real gate data is available (Phase 3D).
 *
 * @param {number} totalPassengers  - Passenger count for this hour
 * @param {number} relativeLoad     - 0–1 vs peak hour
 * @param {number} userIntensity    - 0–1 from intensity slider
 */
function drawHeatmapBlobs(totalPassengers, relativeLoad, userIntensity) {
    const points = generateHeatmapPoints(totalPassengers, relativeLoad);
    if (points.length === 0) return;

    heatmapLayer = new google.maps.visualization.HeatmapLayer({
        data:        points,
        map:         map,
        radius:      25,
        opacity:     0.7 * userIntensity,
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