/*
Author: Alexander Mackey
Student ID: C22739165
Description: Shared JavaScript for AirFlow - runs on BOTH map.html and analytics.html.
Handles: flight search modal, flight search API calls, toast notifications.

Page-specific logic is in:
- map.js        → map init, heatmap, collapsible panel, event listeners
- analytics.js  → predictions chart, time slider, run prediction

This file should be loaded on every page.
*/

// ===================================
// SHARED GLOBALS
// ===================================

// Shared across pages (analytics.js reads airport-select value)
let currentAirport = 'DUB';

// ===================================
// INIT ON DOM READY
// ===================================

document.addEventListener('DOMContentLoaded', function () {
    console.log('🚀 AirFlow shared JS initializing...');
    initFlightSearchModal();
    initFlightSearch();
    initAirportSelector();
    console.log('✓ Shared JS ready');
});

// ===================================
// AIRPORT SELECTOR (shared)
// ===================================

/**
 * Watches the airport selector and updates currentAirport global.
 * Map page reloads heatmap; analytics page shows notification.
 */
function initAirportSelector() {
    const airportSelect = document.getElementById('airport-select');
    if (!airportSelect) return;

    airportSelect.addEventListener('change', function () {
        currentAirport = this.value;
        const label = this.options[this.selectedIndex].text;
        showNotification(`Switched to ${label}`, 'info');

        // If map page: trigger heatmap reload (map.js defines loadHeatmapData)
        if (typeof loadHeatmapData === 'function') {
            loadHeatmapData();
        }
    });
}

// ===================================
// FLIGHT SEARCH MODAL
// ===================================

/**
 * Initialises the flight search modal open/close behaviour.
 * Works on both map and analytics pages.
 */
function initFlightSearchModal() {
    const modal   = document.getElementById('flight-modal');
    const openBtn = document.getElementById('btn-open-flight-modal');
    const closeBtn = document.getElementById('btn-close-flight-modal');

    if (!modal || !openBtn || !closeBtn) {
        console.warn('Flight modal elements not found');
        return;
    }

    // Open
    openBtn.addEventListener('click', function (e) {
        e.preventDefault();
        modal.classList.add('active');
        document.body.style.overflow = 'hidden';
    });

    // Close via X button
    closeBtn.addEventListener('click', function () {
        closeFlightModal(modal);
    });

    // Close on backdrop click
    modal.addEventListener('click', function (e) {
        if (e.target === modal) closeFlightModal(modal);
    });

    // Close on Escape key
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && modal.classList.contains('active')) {
            closeFlightModal(modal);
        }
    });

    console.log('✓ Flight search modal initialized');
}

/**
 * Closes the flight search modal and restores body scroll.
 * @param {HTMLElement} modal - The modal overlay element
 */
function closeFlightModal(modal) {
    modal.classList.remove('active');
    // Only restore body scroll if not on map page (map page always overflow:hidden via CSS)
    if (!document.body.classList.contains('map-page')) {
        document.body.style.overflow = '';
    }
}

// ===================================
// FLIGHT SEARCH API
// ===================================

/**
 * Wires up the flight number input and search button.
 */
function initFlightSearch() {
    const searchBtn   = document.getElementById('btn-search-flight');
    const flightInput = document.getElementById('flight-number-input');

    if (!searchBtn || !flightInput) return;

    searchBtn.addEventListener('click', performFlightSearch);
    flightInput.addEventListener('keypress', function (e) {
        if (e.key === 'Enter') performFlightSearch();
    });

    console.log('✓ Flight search initialized');
}

/**
 * Performs the flight search API call and displays results.
 * Performance requirement: < 1 second response time.
 */
async function performFlightSearch() {
    const flightInput = document.getElementById('flight-number-input');
    const flightNumber = flightInput.value.trim().toUpperCase();

    if (!flightNumber) {
        showNotification('Please enter a flight number', 'error');
        return;
    }

    const airport = document.getElementById('airport-select')?.value || 'DUB';
    // Use date from prediction-date if on analytics page, otherwise tomorrow
    const dateInput = document.getElementById('prediction-date');
    const date = dateInput?.value || getTomorrowString();

    const searchBtn       = document.getElementById('btn-search-flight');
    const loadingIndicator = document.getElementById('flight-loading-indicator');

    searchBtn.disabled = true;
    loadingIndicator.classList.add('active');

    // Clear previous results
    document.getElementById('flight-details').style.display = 'none';
    document.getElementById('arrival-recommendation').style.display = 'none';
    document.getElementById('flight-error').style.display = 'none';

    const startTime = performance.now();

    try {
        const response = await fetch(
            `/api/flights/search/?flight_number=${flightNumber}&airport=${airport}&date=${date}`
        );
        const data = await response.json();
        const elapsed = Math.round(performance.now() - startTime);
        console.log(`Flight search took ${elapsed}ms`);

        if (data.success) {
            displayFlightDetails(data.flight);
            displayArrivalRecommendation(data.recommendation);
            showNotification(`Flight ${flightNumber} found! (${elapsed}ms)`, 'success');
        } else {
            displayFlightError(data.error || 'Flight not found');
            showNotification('Flight not found', 'error');
        }
    } catch (error) {
        console.error('Flight search error:', error);
        displayFlightError('Error searching for flight. Check server connection.');
        showNotification('Search failed', 'error');
    } finally {
        searchBtn.disabled = false;
        loadingIndicator.classList.remove('active');
    }
}

/**
 * Renders flight detail rows in the modal.
 * @param {Object} flight - Flight data from API
 */
function displayFlightDetails(flight) {
    document.getElementById('detail-flight-number').textContent = flight.flight_number;
    document.getElementById('detail-airline').textContent       = flight.airline;
    document.getElementById('detail-destination').textContent   =
        `${flight.destination_name} (${flight.destination})`;
    document.getElementById('detail-departure').textContent     = flight.departure_time;
    document.getElementById('detail-aircraft').textContent      = flight.aircraft;
    document.getElementById('detail-passengers').textContent    =
        flight.estimated_passengers ? flight.estimated_passengers.toLocaleString() : 'N/A';

    document.getElementById('flight-details').style.display = 'block';
}

/**
 * Renders the personalised arrival recommendation in the modal.
 * @param {Object} recommendation - Recommendation data from API
 */
function displayArrivalRecommendation(recommendation) {
    document.getElementById('rec-arrival-time').textContent = recommendation.optimal_arrival;
    document.getElementById('rec-comparison').textContent   = recommendation.comparison;
    document.getElementById('rec-time-savings').textContent = recommendation.time_savings;
    document.getElementById('rec-route-note').textContent   = recommendation.route_type_note;

    document.getElementById('arrival-recommendation').style.display = 'block';
}

/**
 * Displays an error message in the modal.
 * @param {string} message - Error message to display
 */
function displayFlightError(message) {
    document.getElementById('flight-error-message').textContent = message;
    document.getElementById('flight-error').style.display = 'flex';
}

// ===================================
// NOTIFICATIONS (toast)
// ===================================

/**
 * Shows a temporary toast notification.
 *
 * @param {string} message - Text to display
 * @param {'info'|'success'|'error'} type - Controls background colour
 */
function showNotification(message, type = 'info') {
    console.log(`[${type.toUpperCase()}] ${message}`);

    const colours = {
        success: '#50C878',
        error:   '#E24A4A',
        info:    '#4A90E2'
    };

    const notification = document.createElement('div');
    notification.style.cssText = `
        position: fixed;
        top: 72px;
        right: 24px;
        background: ${colours[type] || colours.info};
        color: white;
        padding: 12px 18px;
        border-radius: 8px;
        box-shadow: 0 4px 14px rgba(0,0,0,0.2);
        z-index: 10000;
        font-size: 13px;
        font-weight: 500;
        max-width: 320px;
        animation: slideIn 0.3s ease;
    `;
    notification.textContent = message;
    document.body.appendChild(notification);

    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => {
            if (notification.parentNode) notification.parentNode.removeChild(notification);
        }, 300);
    }, 3000);
}

// ===================================
// UTILITY FUNCTIONS
// ===================================

/**
 * Returns tomorrow's date as a YYYY-MM-DD string.
 * @returns {string}
 */
function getTomorrowString() {
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    return tomorrow.toISOString().split('T')[0];
}