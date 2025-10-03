document.addEventListener("DOMContentLoaded", function () {
    const routeForm = document.getElementById("routeForm");
    const originInput = document.querySelector('input[name="origin"]');
    const destinationInput = document.querySelector('input[name="destination"]');
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