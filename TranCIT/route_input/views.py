from django.shortcuts import render, redirect, get_object_or_404
from django.core.cache import cache
from django.conf import settings
from django.db import DatabaseError
from django.db.models import Q
from django.views.decorators.http import require_POST, require_GET
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.utils import timezone
from decimal import Decimal, InvalidOperation
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import openrouteservice
import json
import logging
import folium

from .forms import RouteForm, JeepneySuggestionForm
from .models import Route, SavedRoute, JEEPNEY_CODE_CHOICES


# -----------------------------
# Configuration / Constants
# -----------------------------
logger = logging.getLogger(__name__)

# Cities for Cebu-area heuristics
CEBU_CITY_KEYWORDS = ["cebu", "mandaue", "lapu", "liloan", "consolacion", "talisay"]

# Default map center (put in settings if you prefer)
DEFAULT_MAP_CENTER = getattr(settings, 'DEFAULT_MAP_CENTER', (10.3157, 123.8854))
DEFAULT_MAP_ZOOM = getattr(settings, 'DEFAULT_MAP_ZOOM', 14)

# Cache timeouts (seconds)
GEOCODE_CACHE_TTL = getattr(settings, 'GEOCODE_CACHE_TTL', 24 * 60 * 60)  # 24 hours
ORS_ROUTE_CACHE_TTL = getattr(settings, 'ORS_ROUTE_CACHE_TTL', 6 * 60 * 60)  # 6 hours
MAP_HTML_CACHE_TTL = getattr(settings, 'MAP_HTML_CACHE_TTL', 5 * 60)  # 5 minutes

# Init geolocator
geolocator = Nominatim(user_agent=getattr(settings, 'GEOCODER_USER_AGENT', 'trancit_app_geocoder'))

# Initialize ORS client (may raise if not configured)
ORS_API_KEY = getattr(settings, 'ORS_API_KEY', None)
if ORS_API_KEY:
    ors_client = openrouteservice.Client(key=ORS_API_KEY)
else:
    ors_client = None


# -----------------------------
# Helper functions
# -----------------------------

def _cache_key_for_geocode(address: str) -> str:
    return f"geo:{address.strip().lower()}"


def cached_geocode(address: str):
    """Geocode with caching and fallback heuristics. Returns geopy Location or None."""
    if not address:
        return None

    key = _cache_key_for_geocode(address)
    cached = cache.get(key)
    if cached:
        return cached

    # Try a few fallbacks, similar to your safe_geocode
    query = address.strip()
    lower = query.lower()
    try:
        if not any(city in lower for city in CEBU_CITY_KEYWORDS):
            query_with_context = f"{query}, Cebu, Philippines"
        else:
            query_with_context = query

        location = geolocator.geocode(query_with_context, timeout=7)
        if not location:
            query_no_numbers = " ".join([w for w in query_with_context.split() if not w.isdigit()])
            location = geolocator.geocode(query_no_numbers, timeout=7)
        if not location:
            parts = [p.strip() for p in query.split(",") if p.strip()]
            if len(parts) >= 2:
                simplified = ", ".join(parts[:2]) + ", Cebu, Philippines"
                location = geolocator.geocode(simplified, timeout=7)
        if not location:
            # city-level fallback
            if "lapu" in lower:
                location = geolocator.geocode("Lapu-Lapu City, Cebu, Philippines", timeout=7)
            elif "mandaue" in lower:
                location = geolocator.geocode("Mandaue City, Cebu, Philippines", timeout=7)
            else:
                location = geolocator.geocode("Cebu City, Philippines", timeout=7)

        if location:
            # store a small tuple to avoid pickling geopy objects
            cached_val = (location.latitude, location.longitude, getattr(location, 'address', None))
            cache.set(key, cached_val, GEOCODE_CACHE_TTL)
            return cached_val

    except (GeocoderTimedOut, GeocoderServiceError) as e:
        logger.warning("Geocoder error for %s: %s", address, e, exc_info=True)

    return None


def _parse_decimal(value):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def calculate_distance_and_time(start_lat, start_lon, end_lat, end_lon):
    """Approximate (geodesic) distance and a naive travel time estimate."""
    if not all([start_lat, start_lon, end_lat, end_lon]):
        return None, None

    try:
        coords_1 = (float(start_lat), float(start_lon))
        coords_2 = (float(end_lat), float(end_lon))
        distance_km = geodesic(coords_1, coords_2).km
        # conservative average speed assumption (kph)
        average_speed_kph = 20
        travel_time_minutes = (distance_km / average_speed_kph) * 60
        return Decimal(f"{distance_km:.2f}"), Decimal(f"{travel_time_minutes:.2f}")
    except Exception:
        logger.exception("Failed to calculate geodesic distance")
        return None, None


def calculate_fare(transport_type, distance_km, travel_time_minutes):
    if distance_km is None or travel_time_minutes is None:
        return None
    try:
        distance_km = Decimal(distance_km)
        travel_time_minutes = Decimal(travel_time_minutes)

        if transport_type == 'Taxi':
            base_fare = Decimal('40.00')
            fare_per_km = Decimal('13.50')
            fare_per_minute = Decimal('2.00')
            return Decimal(f"{(base_fare + fare_per_km * distance_km + fare_per_minute * travel_time_minutes):.2f}")
        if transport_type == 'Motorcycle':
            base_fare = Decimal('20.00')
            fare_per_km = Decimal('10.00')
            return Decimal(f"{(base_fare + fare_per_km * distance_km):.2f}")
        if transport_type == 'Jeepney':
            # Flat rate preserved from original
            return Decimal('13.00')
    except Exception:
        logger.exception("Fare calculation failed")
    return None


# -----------------------------
# OpenRouteService helpers (cached)
# -----------------------------

def _ors_cache_key(a_lat, a_lon, b_lat, b_lon, profile):
    return f"ors:{float(a_lat):.6f},{float(a_lon):.6f}:{float(b_lat):.6f},{float(b_lon):.6f}:{profile}"


def get_route_geojson_cached(start_lat, start_lon, end_lat, end_lon, profile='driving-car'):
    """Fetch a geojson route from ORS with caching. Returns the geojson (dict) or None."""
    if ors_client is None:
        logger.warning("ORS client not configured (no API key)")
        return None

    key = _ors_cache_key(start_lat, start_lon, end_lat, end_lon, profile)
    cached = cache.get(key)
    if cached:
        return cached

    try:
        coords = [(float(start_lon), float(start_lat)), (float(end_lon), float(end_lat))]
        route = ors_client.directions(coordinates=coords, profile=profile, format='geojson')
        cache.set(key, route, ORS_ROUTE_CACHE_TTL)
        return route
    except Exception as e:
        logger.exception("ORS route request failed: %s", e)
        return None


def get_route_and_calculate(start_lat, start_lon, end_lat, end_lon, transport_type='driving-car'):
    profile_map = {
        'Taxi': 'driving-car',
        'Motorcycle': 'driving-car',
        'Jeepney': 'driving-car',
        'Bus': 'driving-car',
    }
    profile = profile_map.get(transport_type, 'driving-car')
    route_data = get_route_geojson_cached(start_lat, start_lon, end_lat, end_lon, profile=profile)
    if not route_data or 'features' not in route_data or not route_data['features']:
        logger.warning("ORS returned no features for route %s -> %s", (start_lat, start_lon), (end_lat, end_lon))
        return None, None, None

    try:
        feature = route_data['features'][0]
        props = feature.get('properties', {})
        distance_m = props.get('summary', {}).get('distance', 0)
        duration_s = props.get('summary', {}).get('duration', 0)
        distance_km = Decimal(str(distance_m / 1000))
        travel_time_minutes = Decimal(str(duration_s / 60))
        return distance_km, travel_time_minutes, route_data
    except Exception:
        logger.exception("Failed to extract ORS summary")
        return None, None, None


def store_route_path(route_instance, route_geojson):
    """Store route path coordinates on the model instance (as JSON lat/lon list)."""
    if not route_geojson or 'features' not in route_geojson:
        return
    try:
        feature = route_geojson['features'][0]
        coords = feature.get('geometry', {}).get('coordinates', [])
        # ORS returns [lon, lat]; convert to [lat, lon]
        path_coords = [[float(lat), float(lon)] for lon, lat in coords]
        route_instance.route_path_coords = json.dumps(path_coords)
    except Exception:
        logger.exception("Failed storing route path")


# -----------------------------
# View helpers (extracted from big views)
# -----------------------------

def _get_coords_from_request_data(text_value: str, lat_str: str = None, lon_str: str = None):
    """Return (lat, lon, error_message) — lat/lon are Decimal or None."""
    if lat_str and lon_str:
        try:
            return Decimal(lat_str), Decimal(lon_str), None
        except InvalidOperation:
            return None, None, 'Invalid latitude/longitude.'

    # Use cached geocoder
    geocoded = cached_geocode(text_value)
    if geocoded:
        lat, lon, address = geocoded
        return Decimal(str(lat)), Decimal(str(lon)), None
    return None, None, f"Could not find coordinates for '{text_value}'."


def _build_map_html(center_lat, center_lon, origin_marker=None, dest_marker=None, routes=[]):
    """Build and return folium map HTML. 'routes' is a list of dicts with path_coords and popup."""
    m = folium.Map(location=[center_lat, center_lon], zoom_start=DEFAULT_MAP_ZOOM)

    if origin_marker:
        folium.Marker(
            [float(origin_marker['lat']), float(origin_marker['lon'])],
            popup=origin_marker.get('popup', 'Origin'),
            icon=folium.Icon(color='blue', prefix='fa', icon='location-dot')
        ).add_to(m)

    if dest_marker:
        folium.Marker(
            [float(dest_marker['lat']), float(dest_marker['lon'])],
            popup=dest_marker.get('popup', 'Destination'),
            icon=folium.Icon(color='darkred', prefix='fa', icon='flag-checkered')
        ).add_to(m)

    for r in routes:
        coords = r.get('path_coords')
        if coords and len(coords) >= 2:
            folium.PolyLine(coords, weight=3, opacity=0.7, popup=r.get('popup')).add_to(m)
        else:
            # fallback: straight line between origin/dest
            o = r.get('origin')
            d = r.get('destination')
            if o and d:
                folium.PolyLine([ [float(o['lat']), float(o['lon'])], [float(d['lat']), float(d['lon'])] ], weight=3, opacity=0.7, popup=r.get('popup')).add_to(m)

    return m._repr_html_()


# -----------------------------
# Views
# -----------------------------

@login_required(login_url='/')
def index(request):
    """Main dashboard view. Builds the folium map inline and injects click JS for pinning."""
    error_message = None
    success_message = None

    # Suggestion filters (GET params)
    origin_q = request.GET.get('origin_search', '')
    dest_q = request.GET.get('destination_search', '')
    transport_q = request.GET.get('transport_type_search', '')
    code_q = request.GET.get('jeepney_code_search', '')

    # Base queryset for suggestions
    suggested_qs = Route.objects.all().order_by('transport_type', 'code', 'origin')

    filters = Q()
    if origin_q:
        filters &= Q(origin__icontains=origin_q)
    if dest_q:
        filters &= Q(destination__icontains=dest_q)
    if transport_q:
        filters &= Q(transport_type=transport_q)
    if code_q:
        filters &= Q(code=code_q)
    if filters:
        suggested_qs = suggested_qs.filter(filters)

    # Forms
    form = RouteForm()
    suggestion_form = JeepneySuggestionForm()

    # GET params for pre-filling map center and markers
    get_origin_lat = request.GET.get('origin_latitude')
    get_origin_lon = request.GET.get('origin_longitude')
    get_origin_text = request.GET.get('origin_text')
    get_dest_lat = request.GET.get('destination_latitude')
    get_dest_lon = request.GET.get('destination_longitude')
    get_dest_text = request.GET.get('destination_text')

    current_origin_lat = _parse_decimal(get_origin_lat) if get_origin_lat else None
    current_origin_lon = _parse_decimal(get_origin_lon) if get_origin_lon else None
    current_dest_lat = _parse_decimal(get_dest_lat) if get_dest_lat else None
    current_dest_lon = _parse_decimal(get_dest_lon) if get_dest_lon else None

    # Choose map center
    if current_origin_lat and current_origin_lon and current_dest_lat and current_dest_lon:
        center_lat = (float(current_origin_lat) + float(current_dest_lat)) / 2
        center_lon = (float(current_origin_lon) + float(current_dest_lon)) / 2
    elif current_origin_lat and current_origin_lon:
        center_lat, center_lon = float(current_origin_lat), float(current_origin_lon)
    elif current_dest_lat and current_dest_lon:
        center_lat, center_lon = float(current_dest_lat), float(current_dest_lon)
    else:
        center_lat, center_lon = DEFAULT_MAP_CENTER

    # Caching key
    map_cache_key = f"map_html:{center_lat:.6f},{center_lon:.6f}:{origin_q}:{dest_q}:{transport_q}:{code_q}:{request.user.id if request.user.is_authenticated else request.session.session_key}"
    map_html = cache.get(map_cache_key)

    if not map_html:
        # Build folium map inline
        m = folium.Map(location=[center_lat, center_lon], zoom_start=DEFAULT_MAP_ZOOM)

        if current_origin_lat and current_origin_lon:
            folium.Marker(
                [float(current_origin_lat), float(current_origin_lon)],
                popup=get_origin_text or "Origin",
                icon=folium.Icon(color='blue', icon='circle', prefix='fa')
            ).add_to(m)

        if current_dest_lat and current_dest_lon:
            folium.Marker(
                [float(current_dest_lat), float(current_dest_lon)],
                popup=get_dest_text or "Destination",
                icon=folium.Icon(color='red', icon='circle', prefix='fa')
            ).add_to(m)


        # Draw route between current origin and destination if both exist
        route_geojson = None
        
        if current_origin_lat and current_origin_lon and current_dest_lat and current_dest_lon:
            try:
                distance_km, travel_minutes, route_geojson = get_route_and_calculate(
                    current_origin_lat,
                    current_origin_lon,
                    current_dest_lat,
                    current_dest_lon,
                    'driving-car'
                )

                if route_geojson and 'features' in route_geojson and route_geojson['features']:
                    feature = route_geojson['features'][0]
                    coords = feature['geometry']['coordinates']
                    path_coords = [[coord[1], coord[0]] for coord in coords]
                    folium.PolyLine(path_coords,
                        color="#2B86C3EE",
                        weight=8,
                        opacity=0.8,
                        popup="Route"
                    ).add_to(m)
                else:
                    folium.PolyLine(
                        [[float(current_origin_lat), float(current_origin_lon)],
                        [float(current_dest_lat), float(current_dest_lon)]],
                        color="#2B86C3EE",
                        weight=3,
                        opacity=0.7,
                        popup="Approximate route"
                    ).add_to(m)

            except Exception as e:
                print("ORS route drawing error:", e)

        # Draw suggested routes (limit to 100 for performance)
        for route in suggested_qs[:100]:
            if all([route.origin_latitude, route.origin_longitude, route.destination_latitude, route.destination_longitude]):
                # If model stores full path coords, use them; otherwise use straight line
                path_coords = None
                try:
                    if hasattr(route, 'get_path_coords'):
                        path_coords = route.get_path_coords()
                except Exception:
                    logger.exception("Error getting path coords for route %s", route.id)

                if path_coords and len(path_coords) >= 2:
                    folium.PolyLine(
                        path_coords,
                        color='purple',
                        weight=3,
                        opacity=0.7,
                        popup=f"{route.transport_type} {route.code or ''}: {route.origin} → {route.destination}").add_to(m)
                else:
                    folium.PolyLine(
                        [[float(route.origin_latitude), float(route.origin_longitude)],
                         [float(route.destination_latitude), float(route.destination_longitude)]],
                        color='purple',
                        weight=3,
                        opacity=0.7,
                        popup=f"{route.transport_type} {route.code or ''}: {route.origin} → {route.destination}"
                    ).add_to(m)

        folium.LayerControl().add_to(m)


        # -- Inject JavaScript for map click-to-pin behavior --
        # Keep this JS indentation-free (no leading spaces) to avoid stray indentation in output.
        # ayaw jud ni hilabta kay mao ni siya ang maka ping og locatoin without the need to use you computers GPS
        click_js = """
// Runs inside the Folium iframe
function initFoliumMap() {
  for (const key in window) {
    if (key.startsWith("map_") && window[key] instanceof L.Map) {
      window.map = window[key];
      console.log("✅ Folium map found inside iframe:", key);
      attachHandlers();
      return;
    }
  }
  setTimeout(initFoliumMap, 500);
}

function attachHandlers() {
  if (!window.map) return;
  window.mapClickMode = null;

  // Listen for messages from the parent page
  window.addEventListener("message", function(event) {
    const data = event.data;
    if (data?.type === "SET_PIN_MODE") {
      window.mapClickMode = data.mode;
      alert("Click on the map to set " + data.mode);
    }
  });

  window.map.on("click", function(e) {
    if (!window.mapClickMode) return;
    const { lat, lng } = e.latlng;

    const markerKey = window.mapClickMode === "origin" ? "originMarker" : "destinationMarker";

    // Remove only the marker for the same type
    if (window[markerKey]) {
    try { window.map.removeLayer(window[markerKey]); } catch {}
    }

    // Add new marker
    window[markerKey] = L.marker([lat, lng]).addTo(window.map)
    .bindPopup(window.mapClickMode + ": " + lat.toFixed(5) + ", " + lng.toFixed(5))
    .openPopup();

    const latInput = parent.document.getElementById("id_" + window.mapClickMode + "_latitude");
    const lonInput = parent.document.getElementById("id_" + window.mapClickMode + "_longitude");
    const textInput = parent.document.querySelector("input[name='" + window.mapClickMode + "']");
    if (latInput && lonInput) {
      latInput.value = lat.toFixed(6);
      lonInput.value = lng.toFixed(6);
      fetch("https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=" + lat + "&lon=" + lng)
        .then(r => r.json())
        .then(d => { textInput.value = d.display_name || `${lat.toFixed(5)}, ${lng.toFixed(5)}`; })
        .catch(() => { textInput.value = `${lat.toFixed(5)}, ${lng.toFixed(5)}`; });
    }

    window.mapClickMode = null;
  });
}

initFoliumMap();
"""
        m.get_root().html.add_child(folium.Element(f"<script>{click_js}</script>"))

        # Render map HTML and cache
        use_cache = not (current_origin_lat and current_dest_lat)
        map_html = m._repr_html_()
        cache.set(map_cache_key, map_html, MAP_HTML_CACHE_TTL)

    # Saved routes for user or session
    if request.user.is_authenticated:
        saved_routes = SavedRoute.objects.filter(user=request.user)
    else:
        if not request.session.session_key:
            request.session.create()
        sk = request.session.session_key
        saved_routes = SavedRoute.objects.filter(session_key=sk)

    context = {
        'form': form,
        'suggestion_form': suggestion_form,
        'map': map_html,
        'all_routes': suggested_qs,
        'saved_routes': saved_routes,
        'success_message': success_message,
        'error_message': error_message,
        'get_origin_text': get_origin_text,
        'get_destination_text': get_dest_text,
        'search_origin': origin_q,
        'search_destination': dest_q,
        'search_transport_type': transport_q,
        'search_jeepney_code': code_q,
    }

    return render(request, 'route_input/index.html', context)


@require_POST
def plan_route(request):
    """Endpoint to handle route planning + saving. Expects CSRF token if called from JS."""
    form = RouteForm(request.POST)
    if not form.is_valid():
        return render(request, 'route_input/index.html', {'form': form, 'error_message': 'Please check your inputs.'})

    route_instance = form.save(commit=False)

    # First prefer client-supplied coordinates (hidden inputs)
    post_origin_lat = request.POST.get('origin_latitude')
    post_origin_lon = request.POST.get('origin_longitude')
    post_dest_lat = request.POST.get('destination_latitude')
    post_dest_lon = request.POST.get('destination_longitude')

    # Origin
    if post_origin_lat and post_origin_lon:
        try:
            route_instance.origin_latitude = Decimal(post_origin_lat)
            route_instance.origin_longitude = Decimal(post_origin_lon)
        except InvalidOperation:
            return render(request, 'route_input/index.html', {'form': form, 'error_message': 'Invalid origin coordinates.'})
    else:
        lat, lon, err = _get_coords_from_request_data(route_instance.origin)
        if err:
            return render(request, 'route_input/index.html', {'form': form, 'error_message': err})
        route_instance.origin_latitude = lat
        route_instance.origin_longitude = lon

    # Destination
    if post_dest_lat and post_dest_lon:
        try:
            route_instance.destination_latitude = Decimal(post_dest_lat)
            route_instance.destination_longitude = Decimal(post_dest_lon)
        except InvalidOperation:
            return render(request, 'route_input/index.html', {'form': form, 'error_message': 'Invalid destination coordinates.'})
    else:
        lat, lon, err = _get_coords_from_request_data(route_instance.destination)
        if err:
            return render(request, 'route_input/index.html', {'form': form, 'error_message': err})
        route_instance.destination_latitude = lat
        route_instance.destination_longitude = lon

    # Try ORS for exact route
    if all([route_instance.origin_latitude, route_instance.origin_longitude, route_instance.destination_latitude, route_instance.destination_longitude]):
        distance_km, travel_minutes, route_geojson = get_route_and_calculate(
            route_instance.origin_latitude, route_instance.origin_longitude,
            route_instance.destination_latitude, route_instance.destination_longitude,
            route_instance.transport_type
        )
        if distance_km and travel_minutes:
            route_instance.distance_km = distance_km
            route_instance.travel_time_minutes = travel_minutes
            route_instance.fare = calculate_fare(route_instance.transport_type, distance_km, travel_minutes)
            store_route_path(route_instance, route_geojson)
        else:
            # Fallback to simple geodesic estimate
            d_km, t_min = calculate_distance_and_time(route_instance.origin_latitude, route_instance.origin_longitude, route_instance.destination_latitude, route_instance.destination_longitude)
            route_instance.distance_km = d_km
            route_instance.travel_time_minutes = t_min
            route_instance.fare = calculate_fare(route_instance.transport_type, d_km, t_min)

    # sanitize code field for non-jeepney
    if route_instance.transport_type != 'Jeepney':
        route_instance.code = None
    else:
        route_instance.code = request.POST.get('code')

    try:
        route_instance.save()
        logger.info("Saved route %s -> %s (id=%s)", route_instance.origin, route_instance.destination, route_instance.id)

        # Redirect back with route data for displaying on map
        return redirect(
            f"/?origin_latitude={route_instance.origin_latitude}"
            f"&origin_longitude={route_instance.origin_longitude}"
            f"&origin_text={route_instance.origin}"
            f"&destination_latitude={route_instance.destination_latitude}"
            f"&destination_longitude={route_instance.destination_longitude}"
            f"&destination_text={route_instance.destination}"
        )
    except DatabaseError:
        logger.exception("DB Error saving route")
        return render(request, 'route_input/index.html', {'form': form, 'error_message': 'Database error saving route.'})


# Keep the community suggestion endpoint separated
@require_POST
def suggest_route(request):
    form = JeepneySuggestionForm(request.POST)
    if form.is_valid():
        form.save()
        return redirect('routes_page')
    return render(request, 'route_input/index.html', {'suggestion_form': form, 'error_message': 'Please complete all required fields.'})


# -----------------------------
# AJAX / API endpoints (require CSRF token)
# -----------------------------

@require_POST
def save_current_route(request):
    """Save a route (AJAX) for the current user or session."""
    origin = request.POST.get('origin')
    destination = request.POST.get('destination')
    transport_type = request.POST.get('transport_type')
    code = request.POST.get('code')
    fare_val = request.POST.get('fare')
    notes = request.POST.get('notes')

    route = Route.objects.filter(
        Q(origin=origin) & Q(destination=destination) & Q(transport_type=transport_type) & Q(code=code)
    ).first()

    saved = SavedRoute.objects.create(
        user=request.user if request.user.is_authenticated else None,
        session_key=request.session.session_key or _get_session_key(request),
        original_route=route,
        origin=origin,
        destination=destination,
        origin_latitude=route.origin_latitude if route else None,
        origin_longitude=route.origin_longitude if route else None,
        destination_latitude=route.destination_latitude if route else None,
        destination_longitude=route.destination_longitude if route else None,
        transport_type=transport_type,
        code=code,
        fare=fare_val or 0,
        notes=notes or "",
        created_at=timezone.now() if hasattr(SavedRoute, 'created_at') else None
    )

    return JsonResponse({"message": "Route saved successfully!", "id": saved.id})


@require_POST
def save_suggested_route(request):
    route_id = request.POST.get('route_id')
    if not route_id:
        return JsonResponse({'error': 'route_id required'}, status=400)
    try:
        route = Route.objects.get(pk=int(route_id))
    except Route.DoesNotExist:
        return JsonResponse({'error': 'Route not found'}, status=404)

    saved = SavedRoute.objects.create(
        user=request.user if request.user.is_authenticated else None,
        session_key=request.session.session_key or _get_session_key(request),
        original_route=route,
        origin=route.origin,
        destination=route.destination,
        origin_latitude=route.origin_latitude,
        origin_longitude=route.origin_longitude,
        destination_latitude=route.destination_latitude,
        destination_longitude=route.destination_longitude,
        transport_type=route.transport_type,
        code=route.code,
        fare=route.fare or 0,
        notes=route.notes or "",
        created_at=timezone.now() if hasattr(SavedRoute, 'created_at') else None
    )

    return JsonResponse({"message": "Suggested route saved!", "id": saved.id})


@require_POST
def delete_saved_route(request):
    saved_id = request.POST.get('saved_id')
    if not saved_id:
        return JsonResponse({'success': False, 'error': 'saved_id required.'}, status=400)
    try:
        saved = SavedRoute.objects.get(pk=int(saved_id))
    except (SavedRoute.DoesNotExist, ValueError):
        return JsonResponse({'success': False, 'error': 'Not found.'}, status=404)

    # Ownership check
    if request.user.is_authenticated:
        if saved.user != request.user:
            return JsonResponse({'success': False, 'error': 'Forbidden.'}, status=403)
    else:
        if saved.session_key != (request.session.session_key or _get_session_key(request)):
            return JsonResponse({'success': False, 'error': 'Forbidden.'}, status=403)

    saved.delete()
    return JsonResponse({'success': True})


@require_POST
def save_route_ajax(request):
    try:
        user = request.user if request.user.is_authenticated else None
        data = request.POST
        route = SavedRoute.objects.create(
            user=user,
            origin=data.get('origin', ''),
            destination=data.get('destination', ''),
            origin_latitude=_parse_decimal(data.get('origin_latitude')),
            origin_longitude=_parse_decimal(data.get('origin_longitude')),
            destination_latitude=_parse_decimal(data.get('destination_latitude')),
            destination_longitude=_parse_decimal(data.get('destination_longitude')),
            transport_type=data.get('transport_type', 'Unknown'),
            code=data.get('code', ''),
            fare=_parse_decimal(data.get('fare') or 0)
        )

        return JsonResponse({
            'success': True,
            'route': {
                'id': route.id,
                'origin': route.origin,
                'destination': route.destination,
                'transport_type': route.transport_type,
                'code': route.code,
                'fare': float(route.fare) if route.fare is not None else 0
            }
        })
    except Exception as e:
        logger.exception("Error saving route via ajax")
        return JsonResponse({'success': False, 'error': str(e)})


@require_GET
def get_jeep_codes(request):
    return JsonResponse({'codes': [code for code, _ in JEEPNEY_CODE_CHOICES]})


def _get_session_key(request):
    if not request.session.session_key:
        request.session.create()
    return request.session.session_key


def logout_view(request):
    logout(request)
    return redirect('/')