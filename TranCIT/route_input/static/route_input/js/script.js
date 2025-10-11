document.addEventListener("DOMContentLoaded", function () {
    const routeForm = document.getElementById("routeForm");
    const originInput = document.querySelector('input[name="origin"]');
    const destinationInput = document.querySelector('input[name="destination"]');
    const destinationSuggestionsContainer = document.getElementById('destinationSuggestions');
    const transportTypeSelect = document.getElementById('id_transport_type');
    const calculatedFareDisplay = document.getElementById('calculatedFare');
    
    // Hidden inputs for data passed to backend
    const fareInput = document.getElementById('id_fare');
    const distanceHiddenInput = document.getElementById('id_distance_km');
    const timeHiddenInput = document.getElementById('id_travel_time_minutes');
    const originLatHidden = document.getElementById('id_origin_latitude');
    const originLonHidden = document.getElementById('id_origin_longitude');
    const destLatHidden = document.getElementById('id_destination_latitude');
    const destLonHidden = document.getElementById('id_destination_longitude');
    const codeHiddenInput = document.getElementById('id_code'); 
    
    const notesInput = document.querySelector('textarea[name="notes"]');

    const detectLocationBtn = document.getElementById('detectLocationBtn');

    // Search form elements in the suggestions panel
    const suggestionSearchForm = document.getElementById('suggestionSearchForm');
    const originSearchInput = document.querySelector('#suggestionSearchForm input[name="origin_search"]');
    const destinationSearchInput = document.querySelector('#suggestionSearchForm input[name="destination_search"]');
    const transportTypeSearchSelect = document.getElementById('id_transport_type_search');
    const jeepneyCodeSearchSelect = document.getElementById('id_jeepney_code_search'); // Jeepney Code search select

    const saveMyRouteBtn = document.getElementById('saveMyRouteBtn');

    // --- Handle View on Map button clicks (for suggestions) ---
    document.querySelectorAll('.view-journey-on-map-btn').forEach(button => {
        button.addEventListener('click', function() {
            const routeId = this.dataset.routeId;
            
            if (!routeId) {
                alert('Route ID missing');
                return;
            }
            
            // Navigate to the same page with highlight_route_id parameter
            // This will cause the server to only display that one route
            window.location.href = `${window.location.pathname}?highlight_route_id=${routeId}`;
        });
    });

    // --- Handle Save My Route button (shows user's own calculated route) ---
    if (saveMyRouteBtn) {
        saveMyRouteBtn.addEventListener('click', function () {
            const payload = new FormData();
            payload.append('origin', originInput.value || '');
            payload.append('destination', destinationInput.value || '');
            payload.append('transport_type', transportTypeSelect ? transportTypeSelect.value : '');
            payload.append('fare', fareInput ? fareInput.value : '0');
            payload.append('distance_km', distanceHiddenInput ? distanceHiddenInput.value : '');
            payload.append('travel_time_minutes', timeHiddenInput ? timeHiddenInput.value : '');
            payload.append('origin_latitude', originLatHidden ? originLatHidden.value : '');
            payload.append('origin_longitude', originLonHidden ? originLonHidden.value : '');
            payload.append('destination_latitude', destLatHidden ? destLatHidden.value : '');
            payload.append('destination_longitude', destLonHidden ? destLonHidden.value : '');
            payload.append('notes', notesInput ? notesInput.value : '');
            payload.append('code', codeHiddenInput ? codeHiddenInput.value : '');

            const saveUrl = window.location.pathname.replace(/\/$/, '') + '/save_current_route/';

            fetch(saveUrl, {
                method: 'POST',
                headers: { 'X-CSRFToken': csrftoken },
                body: payload
            })
            .then(r => r.json())
            .then(data => {
                if (data && data.id) {
                    alert('Route saved to your saved routes!');
                    // Just reload to refresh the map and show user's route
                    window.location.reload();
                } else {
                    alert('Could not save route: ' + (data.error || JSON.stringify(data)));
                }
            })
            .catch(err => {
                console.error('Save route error', err);
                alert('Error saving route. See console for details.');
            });
        });
    }

    // --- Handle Use Saved Route button ---
    document.querySelectorAll('.use-saved-route').forEach(btn => {
        btn.addEventListener('click', function () {
            const origin = this.dataset.origin;
            const destination = this.dataset.destination;
            const originLat = this.dataset.originLat;
            const originLon = this.dataset.originLon;
            const destLat = this.dataset.destLat;
            const destLon = this.dataset.destLon;
            const transport = this.dataset.transport;
            const code = this.dataset.code;

            // Populate the form with saved route data
            if (originInput) originInput.value = origin;
            if (destinationInput) destinationInput.value = destination;
            if (transportTypeSelect) transportTypeSelect.value = transport;
            if (originLatHidden) originLatHidden.value = originLat;
            if (originLonHidden) originLonHidden.value = originLon;
            if (destLatHidden) destLatHidden.value = destLat;
            if (destLonHidden) destLonHidden.value = destLon;
            if (codeHiddenInput) codeHiddenInput.value = code;

            // Update fare display
            updateFareDisplay();

            // Scroll to the form
            document.querySelector('.sidebar').scrollIntoView({ behavior: 'smooth' });
        });
    });

    // --- Handle Delete Saved Route button ---
    document.querySelectorAll('.delete-saved-route').forEach(btn => {
        btn.addEventListener('click', function () {
            if (!confirm('Are you sure you want to delete this saved route?')) {
                return;
            }

            const savedId = this.dataset.savedId;
            if (!savedId) return alert('Saved route ID missing');

            const deleteUrl = window.location.pathname.replace(/\/$/, '') + '/delete_saved_route/';

            fetch(deleteUrl, {
                method: 'POST',
                headers: { 'X-CSRFToken': csrftoken },
                body: new FormData(Object.assign(document.createElement('form'), {
                    innerHTML: `<input name="saved_id" value="${savedId}">`
                }))
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    alert('Saved route deleted!');
                    window.location.reload();
                } else {
                    alert('Error deleting route: ' + (data.error || 'Unknown error'));
                }
            })
            .catch(err => {
                console.error('Delete error', err);
                alert('Error deleting route.');
            });
        });
    });

    // Utility to get CSRF cookie
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                // Does this cookie string begin with the name we want?
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
    const csrftoken = getCookie('csrftoken');

    // --- updated validation: DON'T require Jeepney code for left-panel navigation ---
    if (routeForm) {
        routeForm.addEventListener('submit', function (e) {
            let valid = true;
            document.querySelectorAll(".error").forEach(el => el.textContent = "");

            const origin = originInput.value.trim();
            const destination = destinationInput.value.trim();
            const transportType = transportTypeSelect.value;
            const fare = fareInput.value;

            if (!origin) {
                document.getElementById("error-origin").textContent = "Origin is required.";
                valid = false;
            }
            if (!destination) {
                document.getElementById("error-destination").textContent = "Destination is required.";
                valid = false;
            }
            if (!transportType) {
                document.getElementById("error-transport-type").textContent = "Please select a transportation type.";
                valid = false;
            }
            // NOTE: we removed the left-panel Jeepney code enforcement here.
            if ((transportType === 'Taxi' || transportType === 'Motorcycle') && (fare === "" || parseFloat(fare) < 0)) {
                calculatedFareDisplay.style.color = "red";
                calculatedFareDisplay.textContent = "Calculate fare!";
                valid = false;
            } else {
                calculatedFareDisplay.style.color = "";
            }

            if (!valid) e.preventDefault();
        });
    }

    // --- Save current route (AJAX) ---
    if (saveMyRouteBtn) {
        saveMyRouteBtn.addEventListener('click', function () {
            // Build form data from the left-panel inputs (navigation values)
            const payload = new FormData();
            payload.append('origin', originInput.value || '');
            payload.append('destination', destinationInput.value || '');
            payload.append('transport_type', transportTypeSelect ? transportTypeSelect.value : '');
            payload.append('fare', fareInput ? fareInput.value : '0');
            payload.append('distance_km', distanceHiddenInput ? distanceHiddenInput.value : '');
            payload.append('travel_time_minutes', timeHiddenInput ? timeHiddenInput.value : '');
            payload.append('origin_latitude', originLatHidden ? originLatHidden.value : '');
            payload.append('origin_longitude', originLonHidden ? originLonHidden.value : '');
            payload.append('destination_latitude', destLatHidden ? destLatHidden.value : '');
            payload.append('destination_longitude', destLonHidden ? destLonHidden.value : '');
            payload.append('notes', notesInput ? notesInput.value : '');
            payload.append('code', codeHiddenInput ? codeHiddenInput.value : '');

            // POST to the save_current_route endpoint (relative to /routes/)
            const saveUrl = window.location.pathname.replace(/\/$/, '') + '/save_current_route/'; // yields '/routes/save_current_route/'

            fetch(saveUrl, {
                method: 'POST',
                headers: { 'X-CSRFToken': csrftoken },
                body: payload
            })
            .then(r => r.json())
            .then(data => {
                if (data && data.id) {
                    alert('Route saved to your saved routes!');
                    // Optionally reload to show the saved route in the left saved list
                    window.location.reload();
                } else {
                    alert('Could not save route: ' + (data.error || JSON.stringify(data)));
                }
            })
            .catch(err => {
                console.error('Save route error', err);
                alert('Error saving route. See console for details.');
            });
        });
    }

    // --- Save a suggested route (heart button on a card) via AJAX ---
    document.querySelectorAll('.save-suggested-route').forEach(btn => {
        btn.addEventListener('click', function () {
            const routeId = this.dataset.routeId;
            if (!routeId) return alert('Route id missing');

            const payload = new FormData();
            payload.append('route_id', routeId);

            const saveSuggestedUrl = window.location.pathname.replace(/\/$/, '') + '/save_suggested_route/';

            fetch(saveSuggestedUrl, {
                method: 'POST',
                headers: { 'X-CSRFToken': csrftoken },
                body: payload
            })
            .then(r => r.json())
            .then(data => {
                if (data && data.id) {
                    alert('Suggested route saved to your saved routes!');
                    window.location.reload();
                } else {
                    alert('Could not save suggested route: ' + (data.error || JSON.stringify(data)));
                }
            })
            .catch(err => {
                console.error('Save suggested route error', err);
                alert('Error saving suggested route. See console for details.');
            });
        });
    });

    // --- Geolocation Detection ---
    if (detectLocationBtn) {
        detectLocationBtn.addEventListener('click', function() {
            if (navigator.geolocation) {
                originInput.value = "Detecting location..."; // Immediate feedback
                if (originLatHidden) originLatHidden.value = '';
                if (originLonHidden) originLonHidden.value = '';

                navigator.geolocation.getCurrentPosition(
                    function(position) {
                        const lat = position.coords.latitude;
                        const lon = position.coords.longitude;
                        
                        fetch(`https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=${lat}&lon=${lon}`)
                            .then(response => response.json())
                            .then(data => {
                                const detectedAddress = (data && data.display_name) ? data.display_name : `Lat: ${lat}, Lon: ${lon} (Address Not Found)`;
                                window.location.href = `${window.location.pathname}?origin_latitude=${lat}&origin_longitude=${lon}&origin_text=${encodeURIComponent(detectedAddress)}`;
                            })
                            .catch(error => {
                                console.error("Error during frontend reverse geocoding for redirect:", error);
                                const detectedAddress = `Lat: ${lat}, Lon: ${lon} (Error Fetching Address)`;
                                window.location.href = `${window.location.pathname}?origin_latitude=${lat}&origin_longitude=${lon}&origin_text=${encodeURIComponent(detectedAddress)}`;
                            });
                    },
                    function(error) {
                        console.error("Geolocation error:", error);
                        originInput.value = "";
                        if (originLatHidden) originLatHidden.value = '';
                        if (originLonHidden) originLonHidden.value = '';
                        alert("Unable to detect your location. Ensure location services are enabled and permissions are granted in your browser. Enter it manually.");
                        updateFareDisplay();
                    },
                    { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
                );
            } else {
                alert("Geolocation is not supported by your browser.");
            }
        });
    }


    // --- Dynamic Fare Estimation and Display (Client-side approximation) ---
    function updateFareDisplay() {
        const transportType = transportTypeSelect.value;
        const originText = originInput.value.trim();
        const destinationText = destinationInput.value.trim();

        calculatedFareDisplay.textContent = "Php 0.00";
        fareInput.value = "0.00";
        if (distanceHiddenInput) distanceHiddenInput.value = "";
        if (timeHiddenInput) timeHiddenInput.value = "";

        // --- Control Hidden Code Input ---
        if (transportType === 'Jeepney') {
            if (codeHiddenInput) codeHiddenInput.value = 'UNKNOWN'; 
        } else {
            if (codeHiddenInput) codeHiddenInput.value = ''; 
        }


        if ((transportType === 'Taxi' || transportType === 'Motorcycle') && (!originText || !destinationText)) {
            return;
        }

        if (transportType === 'Taxi' || transportType === 'Motorcycle') {
            const simulatedDistanceKm = 5 + Math.random() * 10;
            const simulatedTimeMinutes = simulatedDistanceKm * 3;

            if (distanceHiddenInput) distanceHiddenInput.value = simulatedDistanceKm.toFixed(2);
            if (timeHiddenInput) timeHiddenInput.value = simulatedTimeMinutes.toFixed(2);

            let calculatedFare = 0;
            if (transportType === 'Taxi') {
                calculatedFare = 40 + (13.5 * simulatedDistanceKm) + (2 * simulatedTimeMinutes);
            } else if (transportType === 'Motorcycle') {
                calculatedFare = 20 + (10 * simulatedDistanceKm);
            }
            calculatedFareDisplay.textContent = `Php ${calculatedFare.toFixed(2)}`;
            fareInput.value = calculatedFare.toFixed(2);

        } else if (transportType === 'Jeepney') {
            calculatedFareDisplay.textContent = "Php ~13.00 (Fixed/Route-based)";
            fareInput.value = "13.00";
        } else {
            calculatedFareDisplay.textContent = "Php 0.00";
            fareInput.value = "0.00";
        }
    }

    // Attach event listeners for dynamic updates
    if (transportTypeSelect) {
        transportTypeSelect.addEventListener('change', updateFareDisplay);
    }
    if (originInput) {
        originInput.addEventListener('input', updateFareDisplay);
    }
    if (destinationInput) {
        destinationInput.addEventListener('input', updateFareDisplay);
    }
    
    updateFareDisplay();

    // --- Client-side form validation (for Add New Route form) ---
    if (routeForm) {
        routeForm.addEventListener("submit", function (e) {
            let valid = true;
            document.querySelectorAll(".error").forEach(el => el.textContent = "");

            const origin = originInput.value.trim();
            const destination = destinationInput.value.trim();
            const transportType = transportTypeSelect.value;
            const code = codeHiddenInput.value;
            const fare = fareInput.value;

            if (!origin) {
                document.getElementById("error-origin").textContent = "Origin is required.";
                valid = false;
            }
            if (!destination) {
                document.getElementById("error-destination").textContent = "Destination is required.";
                valid = false;
            }
            if (!transportType) {
                document.getElementById("error-transport-type").textContent = "Please select a transportation type.";
                valid = false;
            }
            if (transportType === 'Jeepney' && (!code || code === 'UNKNOWN')) {
                alert("Please select a Jeepney route from suggestions or ensure code is set.");
                valid = false;
            }
            if ((transportType === 'Taxi' || transportType === 'Motorcycle') && (fare === "" || parseFloat(fare) < 0)) {
                calculatedFareDisplay.style.color = "red";
                calculatedFareDisplay.textContent = "Calculate fare!";
                valid = false;
            } else {
                calculatedFareDisplay.style.color = "";
            }

            if (!valid) e.preventDefault();
        });
    }

     // --- FIXED: Destination Autocomplete Functionality ---
    let debounceTimeout; // Declare the missing variable

    if (destinationInput && destinationSuggestionsContainer) {
        destinationInput.addEventListener('input', function() {
            clearTimeout(debounceTimeout);
            const query = this.value.trim();

            if (query.length < 3) {
                destinationSuggestionsContainer.style.display = 'none';
                return;
            }

            debounceTimeout = setTimeout(() => {
                fetch(`https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(query)}, Cebu City, Philippines&format=json&limit=5`)
                    .then(response => response.json())
                    .then(data => {
                        destinationSuggestionsContainer.innerHTML = '';
                        if (data.length > 0) {
                            data.forEach(item => {
                                const suggestionItem = document.createElement('div');
                                suggestionItem.classList.add('destination-suggestions-item');
                                suggestionItem.textContent = item.display_name;
                                suggestionItem.dataset.lat = item.lat;
                                suggestionItem.dataset.lon = item.lon;
                                destinationSuggestionsContainer.appendChild(suggestionItem);

                                suggestionItem.addEventListener('click', function() {
                                    // Update destination input with selected suggestion
                                    destinationInput.value = this.textContent;
                                    
                                    // Set hidden latitude/longitude fields
                                    if (destLatHidden) destLatHidden.value = this.dataset.lat;
                                    if (destLonHidden) destLonHidden.value = this.dataset.lon;

                                    // Hide suggestions
                                    destinationSuggestionsContainer.style.display = 'none';
                                    
                                    // Update fare display with new destination
                                    updateFareDisplay();
                                    
                                    // PIN THE DESTINATION ON THE MAP via URL parameters
                                    pinDestinationOnMap(this.dataset.lat, this.dataset.lon, this.textContent);
                                });
                            });
                            destinationSuggestionsContainer.style.display = 'block';
                        } else {
                            destinationSuggestionsContainer.style.display = 'none';
                        }
                    })
                    .catch(error => {
                        console.error("Error fetching destination suggestions:", error);
                        destinationSuggestionsContainer.style.display = 'none';
                    });
            }, 500);
        });

        // Hide suggestions when clicking outside
        document.addEventListener('click', function(event) {
            if (!destinationInput.contains(event.target) && !destinationSuggestionsContainer.contains(event.target)) {
                destinationSuggestionsContainer.style.display = 'none';
            }
        });

        // Also hide suggestions when user presses Escape key
        destinationInput.addEventListener('keydown', function(event) {
            if (event.key === 'Escape') {
                destinationSuggestionsContainer.style.display = 'none';
            }
        });
    }
    // --- END FIXED: Destination Autocomplete Functionality ---


    // --- Function to pin destination on map via URL parameters ---
    function pinDestinationOnMap(lat, lon, address) {
        // Get current URL parameters
        const urlParams = new URLSearchParams(window.location.search);
        
        // Preserve existing origin parameters if they exist
        const currentOriginLat = urlParams.get('origin_latitude') || (originLatHidden ? originLatHidden.value : '');
        const currentOriginLon = urlParams.get('origin_longitude') || (originLonHidden ? originLonHidden.value : '');
        const currentOriginText = urlParams.get('origin_text') || (originInput ? originInput.value : '');
        
        // Update destination parameters - DON'T encode the address
        urlParams.set('destination_latitude', lat);
        urlParams.set('destination_longitude', lon);
        urlParams.set('destination_text', address); // REMOVED encodeURIComponent
        
        // Preserve origin parameters
        if (currentOriginLat) urlParams.set('origin_latitude', currentOriginLat);
        if (currentOriginLon) urlParams.set('origin_longitude', currentOriginLon);
        if (currentOriginText) urlParams.set('origin_text', currentOriginText);
        
        // Reload the page with new parameters
        window.location.href = `${window.location.pathname}?${urlParams.toString()}`;
    }

    

    // --- Handle View on Map button clicks (for suggestions) ---
    document.querySelectorAll('.view-journey-on-map-btn').forEach(button => {
        button.addEventListener('click', function() {
            const originLat = this.dataset.originLat;
            const originLon = this.dataset.originLon;
            const destLat = this.dataset.destLat;
            const destLon = this.dataset.destLon;
            const routeCode = this.dataset.routeCode;
            const transportType = this.dataset.transportType;
            const routeOrigin = this.dataset.routeOrigin;
            const routeDestination = this.dataset.routeDestination;
            
            window.location.href = `${window.location.pathname}?origin_latitude=${originLat}&origin_longitude=${originLon}&destination_latitude=${destLat}&destination_longitude=${destLon}&route_to_highlight_code=${encodeURIComponent(routeCode)}&route_to_highlight_type=${encodeURIComponent(transportType)}&route_to_highlight_origin=${encodeURIComponent(routeOrigin)}&route_to_highlight_destination=${encodeURIComponent(routeDestination)}`;
        });
    });

    // --- Handle suggestionSearchForm submission ---
    if (suggestionSearchForm) {
        suggestionSearchForm.addEventListener('submit', function(e) {

            
            if (originInput && originInput.value.trim() !== '') {
                originSearchInput.value = originInput.value.trim();
            }
            if (destinationInput && destinationInput.value.trim() !== '') {
                destinationSearchInput.value = destinationInput.value.trim();
            }
            // Let the form submit naturally
        });
    }

});