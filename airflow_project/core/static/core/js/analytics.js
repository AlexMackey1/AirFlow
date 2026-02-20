/*
Author: Alexander Mackey
Student ID: C22739165
Description: Analytics page JavaScript - runs only on analytics.html.
Handles: Run Prediction button, Chart.js rendering, time slider, summary cards.

Performance requirements:
- Prediction API call: < 3 seconds
- Slider update: < 0.5 seconds (purely local - no API call)
*/

// ===================================
// ANALYTICS PAGE GLOBALS
// ===================================

let predictionChart   = null;   // Chart.js instance
let currentPredictions = [];    // Array of 24 hourly prediction objects

// ===================================
// INIT
// ===================================

document.addEventListener('DOMContentLoaded', function () {
    console.log('📊 Analytics page initializing...');
    initPredictionsFeature();
    initTimeSlider();
    console.log('✓ Analytics page ready');
});

// ===================================
// PREDICTIONS FEATURE
// ===================================

/**
 * Sets up the date picker (defaults to tomorrow) and Run Prediction button.
 */
function initPredictionsFeature() {
    const dateInput = document.getElementById('prediction-date');
    if (dateInput) {
        dateInput.value = getTomorrowString();
    }

    const runBtn = document.getElementById('btn-run-prediction');
    if (runBtn) {
        runBtn.addEventListener('click', runPrediction);
    }

    console.log('✓ Predictions feature initialized');
}

/**
 * Fetches hourly predictions from the EstimationService API and renders them.
 * Performance requirement: < 3 seconds.
 *
 * Args: (none - reads airport and date from DOM)
 *
 * Returns: Updates chart, summary cards, and time slider display.
 */
async function runPrediction() {
    const airport = document.getElementById('airport-select')?.value || 'DUB';
    const date    = document.getElementById('prediction-date')?.value;

    if (!date) {
        showNotification('Please select a date', 'error');
        return;
    }

    const runBtn           = document.getElementById('btn-run-prediction');
    const loadingIndicator = document.getElementById('loading-indicator');
    const chartHint        = document.getElementById('chart-hint');

    runBtn.disabled = true;
    loadingIndicator.classList.add('active');

    const startTime = performance.now();

    try {
        const data = await fetchPredictions(airport, date);
        const elapsed = Math.round(performance.now() - startTime);
        console.log(`Predictions fetched in ${elapsed}ms`);

        if (data.success) {
            currentPredictions = data.predictions;

            // Hide empty state, render chart
            hideChartEmptyState();
            displayHourlyChart(data.predictions);
            updatePredictionSummary(data.summary);

            // Update time slider to reflect current predictions
            const currentHour = parseInt(document.getElementById('time-slider')?.value || 12);
            updateTimeSliderDisplay(currentHour);

            if (chartHint) chartHint.textContent = `✓ ${data.summary.flights_processed} flights processed (${elapsed}ms)`;

            showNotification(
                `Predictions ready — ${data.summary.total_passengers.toLocaleString()} passengers, peak ${data.summary.peak_hour}:00`,
                'success'
            );
        } else {
            throw new Error(data.error || 'Failed to generate predictions');
        }
    } catch (error) {
        console.error('Prediction error:', error);
        showNotification('Failed to generate predictions. Check server.', 'error');
    } finally {
        runBtn.disabled = false;
        loadingIndicator.classList.remove('active');
    }
}

/**
 * Fetches the hourly predictions from the Django API.
 *
 * @param {string} airport - IATA code (e.g. 'DUB')
 * @param {string} date    - Date string YYYY-MM-DD
 * @returns {Promise<Object>} API response JSON
 */
async function fetchPredictions(airport, date) {
    const response = await fetch(`/api/predictions/hourly/?airport=${airport}&date=${date}`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return await response.json();
}

// ===================================
// CHART.JS RENDERING
// ===================================

/**
 * Renders or replaces the Chart.js line graph with the 24-hour prediction data.
 *
 * @param {Array} predictions - Array of {hour, passengers, confidence, level} objects
 */
function displayHourlyChart(predictions) {
    const ctx = document.getElementById('hourlyChart');
    if (!ctx) return;

    // Destroy existing chart to avoid canvas reuse error
    if (predictionChart) predictionChart.destroy();

    const hours      = predictions.map(p => `${p.hour.toString().padStart(2, '0')}:00`);
    const passengers = predictions.map(p => p.passengers);

    // Build per-point colour based on confidence level
    const pointColours = predictions.map(p => {
        if (p.confidence >= 0.8) return 'rgba(80, 200, 120, 0.9)';
        if (p.confidence >= 0.5) return 'rgba(255, 165, 0, 0.9)';
        return 'rgba(226, 74, 74, 0.9)';
    });

    predictionChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: hours,
            datasets: [{
                label: 'Estimated Passengers',
                data: passengers,
                backgroundColor: 'rgba(74, 144, 226, 0.15)',
                borderColor: 'rgba(74, 144, 226, 1)',
                borderWidth: 2.5,
                fill: true,
                tension: 0.4,
                pointRadius: 4,
                pointHoverRadius: 7,
                pointBackgroundColor: pointColours,
                pointBorderColor: 'white',
                pointBorderWidth: 1.5
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: {
                duration: 600,
                easing: 'easeInOutQuart'
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        /**
                         * Custom tooltip showing passengers + confidence.
                         * @param {Object} context - Chart.js tooltip context
                         * @returns {string[]} Tooltip lines
                         */
                        label: function (context) {
                            const prediction = predictions[context.dataIndex];
                            return [
                                `Passengers: ${prediction.passengers.toLocaleString()}`,
                                `Confidence: ${prediction.level} (${(prediction.confidence * 100).toFixed(0)}%)`
                            ];
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    title: { display: true, text: 'Passengers', font: { size: 12 } },
                    ticks: {
                        callback: value => value.toLocaleString(),
                        font: { size: 11 }
                    },
                    grid: { color: 'rgba(0,0,0,0.05)' }
                },
                x: {
                    title: { display: true, text: 'Hour of Day', font: { size: 12 } },
                    ticks: {
                        maxTicksLimit: 12,
                        font: { size: 11 }
                    },
                    grid: { display: false }
                }
            }
        }
    });

    console.log(`✓ Chart rendered: ${predictions.length} data points`);
}

/**
 * Updates the 4 summary cards below the header.
 *
 * @param {Object} summary - Summary object from API response
 */
function updatePredictionSummary(summary) {
    const totalEl      = document.getElementById('summary-total');
    const peakEl       = document.getElementById('summary-peak');
    const flightsEl    = document.getElementById('summary-flights');
    const confidenceEl = document.getElementById('summary-confidence');

    if (totalEl)   totalEl.textContent   = summary.total_passengers.toLocaleString();
    if (peakEl)    peakEl.textContent    =
        `${summary.peak_hour.toString().padStart(2, '0')}:00 (${summary.peak_passengers.toLocaleString()} pax)`;
    if (flightsEl) flightsEl.textContent = summary.flights_processed;

    if (confidenceEl) {
        const conf  = summary.avg_confidence;
        let badge, level;
        if (conf >= 0.8)      { badge = 'confidence-high';   level = 'High'; }
        else if (conf >= 0.5) { badge = 'confidence-medium'; level = 'Medium'; }
        else                  { badge = 'confidence-low';    level = 'Low'; }

        confidenceEl.innerHTML =
            `<span class="confidence-badge ${badge}">${level} (${conf.toFixed(2)})</span>`;
    }
}

/**
 * Hides the empty state overlay so the chart becomes fully visible.
 */
function hideChartEmptyState() {
    const emptyState = document.getElementById('chart-empty-state');
    if (emptyState) emptyState.classList.add('hidden');
}

// ===================================
// TIME SLIDER
// ===================================

/**
 * Initialises the time slider input listener.
 * Slider moves are purely local (reads currentPredictions array) — no API calls.
 * Performance requirement: < 0.5 seconds.
 */
function initTimeSlider() {
    const slider = document.getElementById('time-slider');
    if (!slider) return;

    slider.addEventListener('input', function () {
        const hour = parseInt(this.value);
        updateTimeSliderDisplay(hour);
        highlightChartHour(hour);
    });

    // Show initial display
    updateTimeSliderDisplay(parseInt(slider.value));
    console.log('✓ Time slider initialized');
}

/**
 * Updates the hour label and passenger count display for the selected hour.
 * Called on every slider movement — must be fast.
 *
 * @param {number} hour - Selected hour (0–23)
 */
function updateTimeSliderDisplay(hour) {
    const hourDisplay  = document.getElementById('selected-hour-display');
    const congestionEl = document.getElementById('selected-hour-congestion');

    if (hourDisplay) {
        hourDisplay.textContent = `${hour.toString().padStart(2, '0')}:00`;
    }

    if (congestionEl) {
        if (currentPredictions.length > 0) {
            const prediction = currentPredictions.find(p => p.hour === hour);
            if (prediction) {
                congestionEl.textContent = `${prediction.passengers.toLocaleString()} passengers`;
            } else {
                congestionEl.textContent = '0 passengers';
            }
        } else {
            congestionEl.textContent = 'Run prediction first';
        }
    }
}

/**
 * Adds a vertical annotation line on the chart for the selected hour.
 * Uses Chart.js annotation-free approach: rebuilds chart dataset colours.
 *
 * @param {number} hour - Selected hour (0–23)
 */
function highlightChartHour(hour) {
    if (!predictionChart || currentPredictions.length === 0) return;

    // Rebuild point colours with the selected hour highlighted in gold
    const pointColours = currentPredictions.map((p, index) => {
        if (index === hour) return 'rgba(255, 215, 0, 1)';           // Gold for selected
        if (p.confidence >= 0.8) return 'rgba(80, 200, 120, 0.7)';  // Green (high)
        if (p.confidence >= 0.5) return 'rgba(255, 165, 0, 0.7)';   // Orange (medium)
        return 'rgba(226, 74, 74, 0.7)';                             // Red (low)
    });

    const pointRadii = currentPredictions.map((_, index) => index === hour ? 8 : 4);
    const pointBorderWidths = currentPredictions.map((_, index) => index === hour ? 3 : 1.5);

    predictionChart.data.datasets[0].pointBackgroundColor = pointColours;
    predictionChart.data.datasets[0].pointRadius          = pointRadii;
    predictionChart.data.datasets[0].pointBorderWidth     = pointBorderWidths;

    predictionChart.update('none'); // 'none' = skip animation for instant response
}