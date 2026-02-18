/*
Author: Alexander Mackey
Student ID: C22739165
Description: Main JavaScript application for AirFlow with Phase 3A enhancements. Handles Leaflet map 
initialization, API communication with Django backend, heatmap rendering, user interface interactions, 
and real-time statistics updates. Phase 3A adds Chart.js hourly predictions visualization.

Key Functions:
- initMap(): Creates Leaflet map instance
- loadHeatmapData(): Fetches passenger data from Django API
- displayHeatmap(): Renders heatmap layer on map
- updateStatistics(): Calculates and displays live metrics
- initEventListeners(): Sets up button clicks and control interactions

Phase 3A Additions:
- fetchPredictions(): Calls /api/predictions/hourly/ endpoint
- displayHourlyChart(): Renders Chart.js line graph
- updatePredictionSummary(): Updates prediction statistics
- initPredictionsFeature(): Sets up date picker and run button
*/

// Global variables
let map;
let heatLayer;
let airportMarker;
let currentAirport = 'DUB';
let predictionChart = null;  // Phase 3A: Chart.js instance

// ===================================
// INITIALIZATION
// ===================================

document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 AirFlow initializing...');
    
    initMap();
    loadHeatmapData();
    initEventListeners();
    initPredictionsFeature();  // Phase 3A
    
    console.log('✓ AirFlow ready');
});

// ===================================
// MAP INITIALIZATION (EXISTING)
// ===================================

function initMap() {
    // Initialize Leaflet map centered on Dublin Airport
    map = L.map('map', {
        center: [53.4213, -6.2701],
        zoom: 15,
        zoomControl: true,
        preferCanvas: true
    });

    // Add OpenStreetMap base layer
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 19,
        minZoom: 12
    }).addTo(map);

    // Add zoom control to top right
    map.zoomControl.setPosition('topright');

    console.log('✓ Map initialized');
}

// ===================================
// HEATMAP DATA LOADING (EXISTING)
// ===================================

function loadHeatmapData() {
    updateStatus('loading');
    
    const airport = document.getElementById('airport-select').value;
    
    fetch(`/api/heatmap/?airport=${airport}`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('API Response:', data);
            
            if (data.success) {
                displayHeatmap(data);
                updateStatistics(data);
                updateStatus('success');
            } else {
                throw new Error(data.error || 'Unknown error');
            }
        })
        .catch(error => {
            console.error('Error loading heatmap:', error);
            updateStatus('error');
            showNotification('Failed to load data', 'error');
        });
}

// ===================================
// HEATMAP DISPLAY (EXISTING)
// ===================================

function displayHeatmap(data) {
    // Remove existing layers
    if (heatLayer) {
        map.removeLayer(heatLayer);
    }
    
    if (airportMarker) {
        map.removeLayer(airportMarker);
    }

    // Add airport marker
    airportMarker = L.marker([data.airport.lat, data.airport.lon], {
        title: data.airport.name,
        icon: L.divIcon({
            className: 'airport-icon',
            html: '✈️',
            iconSize: [30, 30]
        })
    }).addTo(map);
    
    airportMarker.bindPopup(`
        <div style="text-align: center; padding: 5px;">
            <strong style="font-size: 16px;">${data.airport.name}</strong><br>
            <span style="color: #666; font-size: 14px;">${data.airport.code}</span><br>
            <em style="font-size: 12px; color: #999;">Real-time Passenger Flow</em>
        </div>
    `);

    // Create heatmap layer
    if (data.points && data.points.length > 0) {
        const intensitySlider = document.getElementById('intensity-slider');
        const intensity = intensitySlider.value / 100;
        
        heatLayer = L.heatLayer(data.points, {
            radius: 15,
            blur: 10,
            maxZoom: 17,
            max: 1.0 * intensity,
            gradient: {
                0.0: '#0000FF',  // Blue
                0.2: '#00FFFF',  // Cyan
                0.4: '#00FF00',  // Green
                0.6: '#FFFF00',  // Yellow
                0.8: '#FF8800',  // Orange
                1.0: '#FF0000'   // Red
            }
        }).addTo(map);
        
        console.log(`✓ Created heatmap with ${data.point_count} points`);
    } else {
        console.warn('No data points to display');
    }
}

// ===================================
// STATISTICS UPDATE (EXISTING)
// ===================================

function updateStatistics(data) {
    // Estimate total passengers (sum of all intensities * 200)
    let totalPassengers = 0;
    if (data.points) {
        totalPassengers = data.points.reduce((sum, point) => sum + (point[2] * 200), 0);
    }
    
    // Find peak density location
    let peakLocation = 'Terminal 1';
    let maxIntensity = 0;
    if (data.points && data.points.length > 0) {
        data.points.forEach(point => {
            if (point[2] > maxIntensity) {
                maxIntensity = point[2];
                // Determine location based on coordinates
                if (point[0] > 53.428) {
                    peakLocation = 'Gates 200-216';
                } else if (point[0] > 53.426) {
                    peakLocation = 'Check-in Area';
                } else {
                    peakLocation = 'Gates 300';
                }
            }
        });
    }
    
    // Update stat displays
    document.getElementById('stat-passengers').textContent = 
        Math.round(totalPassengers).toLocaleString();
    document.getElementById('stat-peak').textContent = peakLocation;
    document.getElementById('stat-points').textContent = 
        (data.point_count || 0).toLocaleString();
    
    // Update timestamp
    if (data.timestamp) {
        const date = new Date(data.timestamp);
        document.getElementById('stat-updated').textContent = 
            date.toLocaleString('en-IE', { 
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit'
            });
    } else {
        document.getElementById('stat-updated').textContent = 'Just now';
    }
}

// ===================================
// STATUS MANAGEMENT (EXISTING)
// ===================================

function updateStatus(status) {
    const connectionStatus = document.getElementById('connection-status');
    const dataStatus = document.getElementById('data-status');
    
    switch(status) {
        case 'loading':
            connectionStatus.textContent = 'Loading...';
            dataStatus.textContent = 'Fetching Data';
            break;
        case 'success':
            connectionStatus.textContent = 'Connected';
            dataStatus.textContent = 'Data Loaded';
            break;
        case 'error':
            connectionStatus.textContent = 'Connection Error';
            dataStatus.textContent = 'Failed';
            break;
    }
}

// ===================================
// PHASE 3A: PREDICTIONS FEATURE
// ===================================

function initPredictionsFeature() {
    // Set date picker to tomorrow by default
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    const dateString = tomorrow.toISOString().split('T')[0];
    document.getElementById('prediction-date').value = dateString;
    
    // Add event listener to Run Prediction button
    document.getElementById('btn-run-prediction').addEventListener('click', runPrediction);
    
    console.log('✓ Predictions feature initialized');
}

async function runPrediction() {
    const airport = document.getElementById('airport-select').value;
    const date = document.getElementById('prediction-date').value;
    
    const button = document.getElementById('btn-run-prediction');
    const loadingIndicator = document.getElementById('loading-indicator');
    
    // Show loading state
    button.disabled = true;
    loadingIndicator.classList.add('active');
    
    try {
        const data = await fetchPredictions(airport, date);
        
        if (data.success) {
            displayHourlyChart(data.predictions);
            updatePredictionSummary(data.summary);
            showNotification('Predictions generated successfully', 'success');
        } else {
            throw new Error(data.error || 'Failed to generate predictions');
        }
    } catch (error) {
        console.error('Prediction error:', error);
        showNotification('Failed to generate predictions', 'error');
    } finally {
        // Hide loading state
        button.disabled = false;
        loadingIndicator.classList.remove('active');
    }
}

async function fetchPredictions(airport, date) {
    const response = await fetch(`/api/predictions/hourly/?airport=${airport}&date=${date}`);
    
    if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
    }
    
    return await response.json();
}

function displayHourlyChart(predictions) {
    const ctx = document.getElementById('hourlyChart').getContext('2d');
    
    // Destroy existing chart if it exists
    if (predictionChart) {
        predictionChart.destroy();
    }
    
    // Prepare data
    const hours = predictions.map(p => `${p.hour.toString().padStart(2, '0')}:00`);
    const passengers = predictions.map(p => p.passengers);
    
    // Create chart
    predictionChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: hours,
            datasets: [{
                label: 'Estimated Passengers',
                data: passengers,
                backgroundColor: 'rgba(74, 144, 226, 0.2)',
                borderColor: 'rgba(74, 144, 226, 1)',
                borderWidth: 2,
                fill: true,
                tension: 0.4,
                pointRadius: 3,
                pointHoverRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                title: {
                    display: false
                },
                legend: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const prediction = predictions[context.dataIndex];
                            return [
                                `Passengers: ${prediction.passengers}`,
                                `Confidence: ${prediction.level} (${prediction.confidence})`
                            ];
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Passengers'
                    },
                    ticks: {
                        callback: function(value) {
                            return value.toLocaleString();
                        }
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: 'Hour of Day'
                    }
                }
            }
        }
    });
    
    console.log('✓ Chart rendered with', predictions.length, 'data points');
}

function updatePredictionSummary(summary) {
    // Update total passengers
    document.getElementById('summary-total').textContent = 
        summary.total_passengers.toLocaleString();
    
    // Update peak hour
    document.getElementById('summary-peak').textContent = 
        `${summary.peak_hour.toString().padStart(2, '0')}:00 (${summary.peak_passengers} pax)`;
    
    // Update flights processed
    document.getElementById('summary-flights').textContent = 
        summary.flights_processed;
    
    // Update confidence with badge
    const confidence = summary.avg_confidence;
    let badge, level;
    
    if (confidence >= 0.8) {
        badge = 'confidence-high';
        level = 'High';
    } else if (confidence >= 0.5) {
        badge = 'confidence-medium';
        level = 'Medium';
    } else {
        badge = 'confidence-low';
        level = 'Low';
    }
    
    document.getElementById('summary-confidence').innerHTML = 
        `<span class="confidence-badge ${badge}">${level} (${confidence.toFixed(2)})</span>`;
}

// ===================================
// EVENT LISTENERS (EXISTING)
// ===================================

function initEventListeners() {
    // Refresh button
    const refreshBtn = document.getElementById('refresh-btn');
    refreshBtn.addEventListener('click', function() {
        refreshBtn.disabled = true;
        refreshBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Refreshing...';
        
        loadHeatmapData();
        
        setTimeout(() => {
            refreshBtn.disabled = false;
            refreshBtn.innerHTML = '<i class="fas fa-rotate"></i> Refresh Data';
            showNotification('Data refreshed successfully', 'success');
        }, 1000);
    });
    
    // Airport selector
    const airportSelect = document.getElementById('airport-select');
    airportSelect.addEventListener('change', function() {
        currentAirport = this.value;
        loadHeatmapData();
        showNotification(`Switched to ${this.options[this.selectedIndex].text}`, 'info');
    });
    
    // Intensity slider
    const intensitySlider = document.getElementById('intensity-slider');
    const rangeValue = document.querySelector('.range-value');
    
    intensitySlider.addEventListener('input', function() {
        rangeValue.textContent = this.value + '%';
    });
    
    intensitySlider.addEventListener('change', function() {
        if (heatLayer) {
            const intensity = this.value / 100;
            heatLayer.setOptions({ max: 1.0 * intensity });
        }
    });
    
    // Layer toggles
    const heatmapCheckbox = document.getElementById('layer-heatmap');
    heatmapCheckbox.addEventListener('change', function() {
        if (heatLayer) {
            if (this.checked) {
                map.addLayer(heatLayer);
            } else {
                map.removeLayer(heatLayer);
            }
        }
    });
    
    // Filter buttons
    const filterButtons = document.querySelectorAll('.filter-btn');
    filterButtons.forEach(btn => {
        btn.addEventListener('click', function() {
            // Remove active from all
            filterButtons.forEach(b => b.classList.remove('active'));
            // Add active to clicked
            this.classList.add('active');
            
            const filter = this.dataset.filter;
            showNotification(`Filter: ${filter}`, 'info');
        });
    });
    
    // Navigation items (fake for demo)
    const navItems = document.querySelectorAll('.nav-item');
    navItems.forEach(item => {
        item.addEventListener('click', function(e) {
            e.preventDefault();
            
            // Remove active from all
            navItems.forEach(i => i.classList.remove('active'));
            // Add active to clicked
            this.classList.add('active');
            
            const pageName = this.querySelector('span').textContent;
            showNotification(`Navigating to ${pageName}...`, 'info');
        });
    });
}

// ===================================
// NOTIFICATIONS (EXISTING)
// ===================================

function showNotification(message, type = 'info') {
    console.log(`[${type.toUpperCase()}] ${message}`);
    
    // Create notification element
    const notification = document.createElement('div');
    notification.style.cssText = `
        position: fixed;
        top: 85px;
        right: 30px;
        background: ${type === 'success' ? '#50C878' : type === 'error' ? '#E24A4A' : '#4A90E2'};
        color: white;
        padding: 15px 20px;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
        z-index: 10000;
        font-size: 14px;
        font-weight: 500;
        animation: slideIn 0.3s ease;
    `;
    notification.textContent = message;
    
    document.body.appendChild(notification);
    
    // Remove after 3 seconds
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => {
            document.body.removeChild(notification);
        }, 300);
    }, 3000);
}

// Add animation styles
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(400px);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(400px);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);