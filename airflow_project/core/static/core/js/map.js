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

// ===================================
// INIT
// ===================================

document.addEventListener('DOMContentLoaded', function () {
    console.log('🗺️ Map page initializing...');
    initMap();
    loadHeatmapData();
    initCollapsiblePanel();
    initMapControls();
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