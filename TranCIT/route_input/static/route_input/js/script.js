document.addEventListener('DOMContentLoaded', () => {
    const $ = (sel) => document.querySelector(sel);
    const $$ = (sel) => document.querySelectorAll(sel);

    // === Cached DOM Elements ===
    const routeForm = $('#routeForm');
    const originInput = $('#id_origin');
    const destinationInput = $('#id_destination');
    const suggestionsContainer = $('#destinationSuggestions');
    const transportSelect = $('#id_transport_type');
    const fareDisplay = $('#calculatedFare');
    const fareInput = $('#id_fare');
    const distInput = $('#id_distance_km');
    const timeInput = $('#id_travel_time_minutes');
    const originLat = $('#id_origin_latitude');
    const originLon = $('#id_origin_longitude');
    const destLat = $('#id_destination_latitude');
    const destLon = $('#id_destination_longitude');
    const codeInput = $('#id_code');
    const notesInput = $('#id_notes');
    const detectBtn = $('#detectLocationBtn');
    const saveBtn = $('#saveMyRouteBtn');
    const pinOriginBtn = $('#pinOriginBtn');
    const pinDestinationBtn = $('#pinDestinationBtn');
    const navigateBtn = $('#navigateBtn');

    const csrftoken = document.cookie.split('; ').find(r => r.startsWith('csrftoken='))?.split('=')[1];

    // === Utilities ===
    const alertMsg = (msg) => alert(msg);
    const qs = (params) => new URLSearchParams(params).toString();

    const postJSON = async (url, data) => {
        const res = await fetch(url, {
            method: 'POST',
            headers: { 'X-CSRFToken': csrftoken },
            body: data
        });
        return res.json();
    };

    const updateURL = (params) => {
        const newUrl = `${window.location.pathname}?${qs(params)}`;
        window.history.replaceState({}, '', newUrl);
    };

    // === Toggle Navigate Button ===
    function toggleNavigateButton() {
        const hasOrigin = originLat.value && originLon.value;
        const hasDestination = destLat.value && destLon.value;
        const enabled = hasOrigin && hasDestination;

        navigateBtn.disabled = !enabled;
        navigateBtn.style.opacity = enabled ? 1 : 0.6;
        navigateBtn.style.cursor = enabled ? 'pointer' : 'not-allowed';
    }

    // === Poll for changes (handles async map pin updates) ===
    setInterval(toggleNavigateButton, 1000);

    // === Sync hidden inputs from URL (on refresh or after detect) ===
    function syncInputsFromURL() {
        const params = new URLSearchParams(window.location.search);

        if (params.has('origin_latitude')) originLat.value = params.get('origin_latitude');
        if (params.has('origin_longitude')) originLon.value = params.get('origin_longitude');
        if (params.has('destination_latitude')) destLat.value = params.get('destination_latitude');
        if (params.has('destination_longitude')) destLon.value = params.get('destination_longitude');

        if (params.has('origin_text')) originInput.value = decodeURIComponent(params.get('origin_text'));
        if (params.has('destination_text')) destinationInput.value = decodeURIComponent(params.get('destination_text'));

        toggleNavigateButton();
    }

    syncInputsFromURL();
    window.addEventListener('load', syncInputsFromURL);
    window.addEventListener('pageshow', syncInputsFromURL);

    // === Tooltip for Navigate Button ===
    const tooltip = document.createElement('div');
    tooltip.textContent = 'Please pin both your origin and destination';
    Object.assign(tooltip.style, {
        position: 'absolute',
        background: '#333',
        color: '#fff',
        padding: '6px 10px',
        borderRadius: '6px',
        fontSize: '12px',
        whiteSpace: 'nowrap',
        pointerEvents: 'none',
        opacity: '0',
        transition: 'opacity 0.2s'
    });
    document.body.appendChild(tooltip);

    const showTooltip = (e) => {
        if (!navigateBtn.disabled) return;
        tooltip.style.left = e.pageX + 15 + 'px';
        tooltip.style.top = e.pageY - 35 + 'px';
        tooltip.style.opacity = '1';
    };
    const hideTooltip = () => (tooltip.style.opacity = '0');
    navigateBtn?.addEventListener('mousemove', showTooltip);
    navigateBtn?.addEventListener('mouseleave', hideTooltip);

    // === Map Pin Commands ===
    function sendPinCommand(mode) {
        const iframe = document.querySelector('#map-container iframe');
        if (!iframe?.contentWindow) return alertMsg('Map not ready yet. Please wait.');

        const params = new URLSearchParams(window.location.search);
        if (mode === 'origin' && destLat.value && destLon.value) {
            params.set('destination_latitude', destLat.value);
            params.set('destination_longitude', destLon.value);
            params.set('destination_text', destinationInput.value);
        } else if (mode === 'destination' && originLat.value && originLon.value) {
            params.set('origin_latitude', originLat.value);
            params.set('origin_longitude', originLon.value);
            params.set('origin_text', originInput.value);
        }

        updateURL(params);
        iframe.contentWindow.postMessage({ type: 'SET_PIN_MODE', mode }, '*');
    }

    pinOriginBtn?.addEventListener('click', () => sendPinCommand('origin'));
    pinDestinationBtn?.addEventListener('click', () => sendPinCommand('destination'));

    // === Navigate Route ===
    navigateBtn?.addEventListener('click', () => {
        if (!originLat.value && !destLat.value)
            return alertMsg('Please pin both your origin and destination.');
        if (!originLat.value)
            return alertMsg('Please pin your origin.');
        if (!destLat.value)
            return alertMsg('Please pin your destination.');

        window.location.href = `/routes/?${qs({
            origin_latitude: originLat.value,
            origin_longitude: originLon.value,
            destination_latitude: destLat.value,
            destination_longitude: destLon.value,
            origin_text: originInput.value,
            destination_text: destinationInput.value
        })}`;
    });

    // === Fare Calculation ===
    function updateFare() {
        const type = transportSelect?.value;
        if (!type) return;

        fareDisplay.textContent = 'Php 0.00';
        fareInput.value = '0.00';
        distInput.value = '';
        timeInput.value = '';

        if (type === 'Jeepney') {
            codeInput.value = 'UNKNOWN';
            fareInput.value = '13.00';
            fareDisplay.textContent = 'Php ~13.00 (Fixed)';
            return;
        }

        if (!['Taxi', 'Motorcycle'].includes(type)) return;

        const dist = 5 + Math.random() * 10;
        const time = dist * 3;
        const fare = type === 'Taxi'
            ? 40 + 13.5 * dist + 2 * time
            : 20 + 10 * dist;

        distInput.value = dist.toFixed(2);
        timeInput.value = time.toFixed(2);
        fareInput.value = fare.toFixed(2);
        fareDisplay.textContent = `Php ${fare.toFixed(2)}`;
    }

    ['change', 'input'].forEach(evt => {
        transportSelect?.addEventListener(evt, updateFare);
        originInput?.addEventListener(evt, updateFare);
        destinationInput?.addEventListener(evt, updateFare);
    });
    setTimeout(updateFare, 300);

    // === Geolocation Detection ===
    detectBtn?.addEventListener('click', () => {
        if (!navigator.geolocation) return alertMsg('Geolocation not supported.');
        originInput.value = 'Detecting location...';

        navigator.geolocation.getCurrentPosition(async pos => {
            const { latitude: lat, longitude: lon } = pos.coords;
            originLat.value = lat;
            originLon.value = lon;
            toggleNavigateButton();

            try {
                const res = await fetch(`https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=${lat}&lon=${lon}`);
                const data = await res.json();
                const addr = data?.display_name || `Lat: ${lat.toFixed(5)}, Lon: ${lon.toFixed(5)}`;
                originInput.value = addr;

                const params = {
                    origin_latitude: lat,
                    origin_longitude: lon,
                    origin_text: addr
                };
                if (destLat.value && destLon.value) {
                    params.destination_latitude = destLat.value;
                    params.destination_longitude = destLon.value;
                    params.destination_text = destinationInput.value;
                }
                window.location.href = `${window.location.pathname}?${qs(params)}`;
            } catch {
                alertMsg('Unable to retrieve address, but location saved.');
            }
        }, err => {
            console.error(err);
            alertMsg('Location detection failed.');
        }, { enableHighAccuracy: true, timeout: 7000 });
    });

    // === Destination Autocomplete ===
    let debounce;
    destinationInput?.addEventListener('input', () => {
        clearTimeout(debounce);
        const query = destinationInput.value.trim();
        if (query.length < 3) return (suggestionsContainer.style.display = 'none');

        debounce = setTimeout(async () => {
            try {
                const res = await fetch(`https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(query)}, Cebu City, Philippines&format=json&limit=5`);
                const results = await res.json();

                suggestionsContainer.innerHTML = '';
                if (!results.length) return (suggestionsContainer.style.display = 'none');

                results.forEach(item => {
                    const div = document.createElement('div');
                    div.className = 'destination-suggestions-item';
                    div.textContent = item.display_name;

                    div.addEventListener('click', () => {
                        destinationInput.value = item.display_name;
                        destLat.value = item.lat;
                        destLon.value = item.lon;
                        suggestionsContainer.style.display = 'none';
                        toggleNavigateButton();

                        const params = {
                            destination_latitude: item.lat,
                            destination_longitude: item.lon,
                            destination_text: item.display_name
                        };
                        if (originLat.value && originLon.value) {
                            params.origin_latitude = originLat.value;
                            params.origin_longitude = originLon.value;
                            params.origin_text = originInput.value;
                        }
                        window.location.href = `${window.location.pathname}?${qs(params)}`;
                    });

                    suggestionsContainer.appendChild(div);
                });
                suggestionsContainer.style.display = 'block';
            } catch {
                suggestionsContainer.style.display = 'none';
            }
        }, 400);
    });

    document.addEventListener('click', (e) => {
        if (!suggestionsContainer.contains(e.target) && e.target !== destinationInput)
            suggestionsContainer.style.display = 'none';
    });
});