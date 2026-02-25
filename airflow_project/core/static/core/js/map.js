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

let map;
let heatLayer;
let airportMarker;

// Phase 3B.5: store predictions so the time slider can scrub without re-fetching
let mapPredictions = [];  // Array of {hour, passengers, confidence, level}

// ===================================
// INIT
// ===================================

document.addEventListener('DOMContentLoaded', function () {
    console.log('🗺️ Map page initializing...');
    initMap();
    loadHeatmapData();
    initCollapsiblePanel();
    initMapControls();
    initMapPrediction();   // Phase 3B.5
    console.log('✓ Map page ready');
});

// ===================================
// MAP INITIALIZATION
// ===================================

/**
 * Initialises the Leaflet map centred on Dublin Airport.
 * Uses OpenStreetMap tiles, sets zoom limits appropriate for airport-level view.
 */
function initMap() {
    map = L.map('map', {
        center: [53.4213, -6.2701],
        zoom: 15,
        zoomControl: true,
        preferCanvas: true
    });

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 19,
        minZoom: 10
    }).addTo(map);

    // Move zoom control away from the panel area
    map.zoomControl.setPosition('topright');

    console.log('✓ Map initialized (Dublin Airport 53.4213, -6.2701)');
}

// ===================================
// HEATMAP DATA
// ===================================

/**
 * Fetches heatmap data from the API and renders it on the map.
 * Called on page load and when the airport selector changes.
 * Performance requirement: < 2 seconds for airport switch.
 */
function loadHeatmapData() {
    updateMapStatus('loading');

    const airport = document.getElementById('airport-select')?.value || 'DUB';
    const startTime = performance.now();

    fetch(`/api/heatmap/?airport=${airport}`)
        .then(response => {
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return response.json();
        })
        .then(data => {
            const elapsed = Math.round(performance.now() - startTime);
            console.log(`Heatmap loaded in ${elapsed}ms`);

            if (data.success) {
                displayHeatmap(data);
                updateMapStatus('success');
                // Centre map on the airport
                if (data.airport) {
                    map.setView([data.airport.lat, data.airport.lon], 15);
                }
            } else {
                throw new Error(data.error || 'Unknown error');
            }
        })
        .catch(error => {
            console.error('Error loading heatmap:', error);
            updateMapStatus('error');
            showNotification('Failed to load heatmap data', 'error');
        });
}

/**
 * Renders airport marker and heatmap layer on the Leaflet map.
 *
 * @param {Object} data - API response with airport info and heatmap points
 */
function displayHeatmap(data) {
    // Remove existing layers
    if (heatLayer)     map.removeLayer(heatLayer);
    if (airportMarker) map.removeLayer(airportMarker);

    // Airport marker
    airportMarker = L.marker([data.airport.lat, data.airport.lon], {
        title: data.airport.name,
        icon: L.divIcon({
            className: 'airport-icon',
            html: '<span style="font-size:28px;filter:drop-shadow(0 2px 4px rgba(0,0,0,0.3))">✈️</span>',
            iconSize: [32, 32],
            iconAnchor: [16, 16]
        })
    }).addTo(map);

    airportMarker.bindPopup(`
        <div style="text-align:center;padding:4px;">
            <strong style="font-size:15px;">${data.airport.name}</strong><br>
            <span style="color:#666;font-size:13px;">${data.airport.code} — ${data.airport.city}</span><br>
            <em style="font-size:11px;color:#999;">Real-time Passenger Flow</em>
        </div>
    `);

    // Heatmap layer
    if (data.points && data.points.length > 0) {
        const intensitySlider = document.getElementById('intensity-slider');
        const intensity = intensitySlider ? intensitySlider.value / 100 : 0.8;

        heatLayer = L.heatLayer(data.points, {
            radius: 15,
            blur: 10,
            maxZoom: 17,
            max: 1.0 * intensity,
            gradient: {
                0.0: '#0000FF',
                0.2: '#00FFFF',
                0.4: '#00FF00',
                0.6: '#FFFF00',
                0.8: '#FF8800',
                1.0: '#FF0000'
            }
        }).addTo(map);

        console.log(`✓ Heatmap rendered: ${data.point_count} points`);
    } else {
        console.log('No heatmap points returned (database may be empty)');
    }
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
 * Dublin Airport terminal area definitions for distributing predicted
 * passengers into realistic spatial heatmap points.
 *
 * passenger_pct: proportion of total hourly passengers placed in this zone.
 * radius:        scatter radius in degrees (~100m per 0.001 degrees latitude).
 */
const DUBLIN_AIRPORT_AREAS = [
    { name: 'Terminal 1 Check-in', lat: 53.4213, lon: -6.2701, radius: 0.0010, passenger_pct: 0.20 },
    { name: 'Terminal 2 Check-in', lat: 53.4273, lon: -6.2441, radius: 0.0010, passenger_pct: 0.10 },
    { name: 'Security',            lat: 53.4223, lon: -6.2681, radius: 0.0008, passenger_pct: 0.25 },
    { name: 'Gates 200-216',       lat: 53.4283, lon: -6.2511, radius: 0.0015, passenger_pct: 0.25 },
    { name: 'Gates 300',           lat: 53.4183, lon: -6.2651, radius: 0.0012, passenger_pct: 0.15 },
    { name: 'Retail / Food',       lat: 53.4233, lon: -6.2641, radius: 0.0006, passenger_pct: 0.05 }
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
 * Generates and renders algorithm-driven heatmap points for a given hour.
 * Distributes predicted passengers across realistic Dublin Airport terminal
 * areas with Gaussian scatter for visual realism.
 *
 * Performance requirement: < 0.5 seconds (purely client-side generation).
 *
 * @param {number} hour - Hour to visualise (0–23)
 */
function updateDynamicHeatmap(hour) {
    if (mapPredictions.length === 0) return;

    const prediction = mapPredictions.find(p => p.hour === hour);
    const passengers = prediction ? prediction.passengers : 0;

    // Remove existing heatmap layer before redrawing
    if (heatLayer) {
        map.removeLayer(heatLayer);
        heatLayer = null;
    }

    if (passengers === 0) {
        console.log(`Hour ${hour}: 0 passengers — heatmap cleared`);
        return;
    }

    // Calculate intensity relative to the busiest hour
    // so the colour scale always uses the full gradient range
    const maxPassengers = Math.max(...mapPredictions.map(p => p.passengers));
    const relativeIntensity = passengers / maxPassengers;

    // Generate spatial points: distribute passengers across terminal areas
    const heatPoints = generateHeatmapPoints(passengers, relativeIntensity);

    // Get user's intensity slider value
    const intensitySlider = document.getElementById('intensity-slider');
    const userIntensity = intensitySlider ? intensitySlider.value / 100 : 0.8;

    heatLayer = L.heatLayer(heatPoints, {
        radius:  18,
        blur:    12,
        maxZoom: 17,
        max:     1.0 * userIntensity,
        gradient: {
            0.0: '#0000FF',
            0.2: '#00FFFF',
            0.4: '#00FF00',
            0.6: '#FFFF00',
            0.8: '#FF8800',
            1.0: '#FF0000'
        }
    }).addTo(map);

    console.log(`✓ Dynamic heatmap: hour ${hour}, ${passengers} pax, ${heatPoints.length} points`);
}

/**
 * Generates an array of [lat, lon, intensity] heatmap points by distributing
 * passengers proportionally across terminal zones with random Gaussian scatter.
 *
 * Point count is capped at 250 to keep rendering fast (< 0.5s).
 * Scatter uses Box-Muller transform for realistic crowd clustering.
 *
 * @param {number} totalPassengers   - Passenger count for this hour
 * @param {number} relativeIntensity - 0–1 scale relative to busiest hour
 * @returns {Array} Array of [lat, lon, intensity] triples
 */
function generateHeatmapPoints(totalPassengers, relativeIntensity) {
    const points   = [];
    // Scale point count: 1 point per ~25 passengers, max 250 points
    const maxPoints = Math.min(250, Math.max(30, Math.round(totalPassengers / 25)));

    DUBLIN_AIRPORT_AREAS.forEach(area => {
        // Points allocated to this zone proportional to its passenger percentage
        const zonePoints = Math.round(maxPoints * area.passenger_pct);
        const zoneIntensity = relativeIntensity * area.passenger_pct * 6; // boost per-zone intensity

        for (let i = 0; i < zonePoints; i++) {
            // Box-Muller transform: convert uniform random to Gaussian distribution
            // This creates realistic crowd clustering (dense centre, sparse edges)
            const u1 = Math.random();
            const u2 = Math.random();
            const gaussian = Math.sqrt(-2 * Math.log(u1 + 1e-10)) * Math.cos(2 * Math.PI * u2);

            const lat = area.lat + gaussian * area.radius;
            const lon = area.lon + gaussian * area.radius * 1.5; // airports wider east-west
            const intensity = Math.min(1.0, Math.max(0.05, zoneIntensity + (Math.random() - 0.5) * 0.1));

            points.push([lat, lon, intensity]);
        }
    });

    return points;
}