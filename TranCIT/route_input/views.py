from django.shortcuts import render, redirect
from django.db import DatabaseError
from django.db.models import Q
from .forms import RouteForm, JeepneySuggestionForm
import folium
from .models import Route
from decimal import Decimal, InvalidOperation
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

from django.http import JsonResponse, HttpResponseForbidden, HttpResponseBadRequest
from django.views.decorators.http import require_POST 
from django.shortcuts import get_object_or_404 
from .models import SavedRoute 
from django.utils import timezone

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from .models import SavedRoute, JEEPNEY_CODE_CHOICES

import openrouteservice
from openrouteservice import convert
from django.conf import settings

import json  # For storing/retrieving route path coordinates
import logging
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout

# Init geolocator
geolocator = Nominatim(user_agent="trancit_app_geocoder")
# Initialize the ORS client
client = openrouteservice.Client(key=settings.ORS_API_KEY)
# Optional: Setup logging for debugging
logger = logging.getLogger(__name__)

def get_route_geojson(start_lat, start_lon, end_lat, end_lon, profile='driving-car'):
    """
    Returns a GeoJSON route from ORS between two points.
    profile: 'driving-car', 'cycling-regular', 'foot-walking', etc.
    """
    try:
        coords = [(float(start_lon), float(start_lat)), (float(end_lon), float(end_lat))]
        route = client.directions(
            coordinates=coords,
            profile=profile,
            format='geojson'
        )
        return route
    except Exception as e:
        print(f"ERROR: ORS route request failed: {e}")
        return None
    
# ============ NEW HELPER FUNCTIONS FOR ORS ============
def get_route_and_calculate(start_lat, start_lon, end_lat, end_lon, transport_type='driving-car'):
    """
    Uses OpenRouteService to get a real route and extract distance/time.
    Returns: (distance_km, travel_time_minutes, route_geojson)
    """
    try:
        # Profile mapping based on transport type
        profile_map = {
            'Taxi': 'driving-car',
            'Motorcycle': 'driving-car',
            'Jeepney': 'driving-car',
            'Bus': 'driving-car',
        }
        profile = profile_map.get(transport_type, 'driving-car')
        
        # Call ORS
        route_data = get_route_geojson(start_lat, start_lon, end_lat, end_lon, profile=profile)
        
        if not route_data or 'features' not in route_data or len(route_data['features']) == 0:
            print(f"WARNING: ORS returned no features")
            return None, None, None
        
        # Extract distance and duration from first feature
        feature = route_data['features'][0]
        properties = feature.get('properties', {})
        
        # ORS returns total distance in meters and duration in seconds
        distance_m = properties.get('summary', {}).get('distance', 0)
        duration_s = properties.get('summary', {}).get('duration', 0)
        
        # Convert to km and minutes
        distance_km = Decimal(str(distance_m / 1000))
        travel_time_minutes = Decimal(str(duration_s / 60))
        
        return distance_km, travel_time_minutes, route_data
        
    except Exception as e:
        print(f"ERROR: ORS route calculation failed: {e}")
        return None, None, None

def store_route_path(route_instance, route_geojson):
    """
    Stores the route path coordinates in the Route model for future reference.
    """
    if not route_geojson or 'features' not in route_geojson:
        return
    
    try:
        feature = route_geojson['features'][0]
        coords = feature.get('geometry', {}).get('coordinates', [])
        
        # Store as JSON list of [lat, lon] pairs
        if coords:
            # Swap [lon, lat] to [lat, lon] for storage
            path_coords = [[lat, lon] for lon, lat in coords]
            route_instance.route_path_coords = json.dumps(path_coords)
    except Exception as e:
        print(f"WARNING: Could not store route path: {e}")

def routes_page(request):
    form = RouteForm()
    suggestion_form = JeepneySuggestionForm()
    success_message = None
    error_message = None

    if request.method == 'POST':
        form_type = request.POST.get('form_type')

        # 🟩 LEFT PANEL — User Route Planning
        if form_type == 'plan_route':
            form = RouteForm(request.POST)
            if form.is_valid():
                # Perform route calculation (distance, fare, etc.)
                route_instance = form.save(commit=False)
                # Example placeholders for backend-calculated fields
                route_instance.distance_km = request.POST.get('distance_km', 0)
                route_instance.fare = request.POST.get('fare', 0)
                route_instance.save()
                success_message = "Route successfully calculated and saved!"
            else:
                error_message = "Please check your inputs and try again."

        # 🟨 RIGHT PANEL — Jeepney Route Suggestion
        elif form_type == 'suggest_route':
            suggestion_form = JeepneySuggestionForm(request.POST)
            if suggestion_form.is_valid():
                suggestion_form.save()
                success_message = "Jeepney route suggestion added successfully!"
            else:
                error_message = "Please complete all required fields for jeepney route suggestion."

    # Get saved user routes and community routes
    saved_routes = Route.objects.all().order_by('-id')[:10]  # Adjust if you have filtering per user
    all_routes = Route.objects.all().order_by('-id')

    return render(request, 'route_input/index.html', {
        'form': form,
        'suggestion_form': suggestion_form,
        'saved_routes': saved_routes,
        'all_routes': all_routes,
        'success_message': success_message,
        'error_message': error_message,
    })


def safe_geocode(address):
    """Try multiple geocoding fallbacks for stubborn Cebu addresses."""
    if not address:
        return None

    try:
        query = address.strip()
        lower_addr = query.lower()

        # Append Cebu context if missing
        if not any(city in lower_addr for city in ["cebu", "mandaue", "lapu", "liloan", "consolacion", "talisay"]):
            query += ", Cebu, Philippines"

        # 1️⃣ Primary geocode
        location = geolocator.geocode(query, timeout=7)
        if location:
            return location

        # 2️⃣ Try without postal codes or region names
        query_no_numbers = " ".join([word for word in query.split() if not word.isdigit()])
        location = geolocator.geocode(query_no_numbers, timeout=7)
        if location:
            return location

        # 3️⃣ Simplify to just first two segments (street + barangay)
        parts = [p.strip() for p in query.split(",") if p.strip()]
        if len(parts) >= 2:
            simplified = ", ".join(parts[:2]) + ", Cebu, Philippines"
            location = geolocator.geocode(simplified, timeout=7)
            if location:
                return location

        # 4️⃣ As last resort, drop to city-level
        if "lapu" in lower_addr:
            location = geolocator.geocode("Lapu-Lapu City, Cebu, Philippines", timeout=7)
        elif "mandaue" in lower_addr:
            location = geolocator.geocode("Mandaue City, Cebu, Philippines", timeout=7)
        else:
            location = geolocator.geocode("Cebu City, Philippines", timeout=7)

        return location

    except (GeocoderTimedOut, GeocoderServiceError) as e:
        print(f"WARNING: Geocode failed for '{address}': {e}")
        return None

# Helper: distance/time approx
def calculate_distance_and_time(start_lat, start_lon, end_lat, end_lon):
    if not all([start_lat, start_lon, end_lat, end_lon]):
        return None, None

    coords_1 = (float(start_lat), float(start_lon))
    coords_2 = (float(end_lat), float(end_lon))

    distance_km = geodesic(coords_1, coords_2).km
    
    average_speed_kph = 20
    travel_time_minutes = distance_km * 3 # approx 3 minutes per km
    
    return Decimal(f"{distance_km:.2f}"), Decimal(f"{travel_time_minutes:.2f}")

# Helper: fare calc
def calculate_fare(transport_type, distance_km, travel_time_minutes):
    if distance_km is None or travel_time_minutes is None:
        return None

    distance_km = Decimal(distance_km)
    travel_time_minutes = Decimal(travel_time_minutes)

    if transport_type == 'Taxi':
        base_fare = Decimal('40.00')
        fare_per_km = Decimal('13.50')
        fare_per_minute = Decimal('2.00')
        calculated_fare = base_fare + (fare_per_km * distance_km) + (fare_per_minute * travel_time_minutes)
        return Decimal(f"{calculated_fare:.2f}")

    elif transport_type == 'Motorcycle':
        base_fare = Decimal('20.00')
        fare_per_km = Decimal('10.00')
        calculated_fare = base_fare + (fare_per_km * distance_km)
        return Decimal(f"{calculated_fare:.2f}")

    elif transport_type == 'Jeepney':
        return Decimal('13.00')
        
    return None

def logout_view(request):
    logout(request)
    return redirect('/')

# Main Index View

@login_required(login_url='/') #must login before seeing dashboard
def index(request):
    error_message = None
    success_message = None
    map_html = ""
    form = RouteForm()
    context = {}
    
    current_origin_lat = None
    current_origin_lon = None
    current_destination_lat = None
    current_destination_lon = None
    get_origin_text = None
    get_destination_text = None

    # --- Initialize search variables for the Suggestions panel ---
    search_query_origin = request.GET.get('origin_search', '')
    search_query_destination = request.GET.get('destination_search', '')
    search_transport_type = request.GET.get('transport_type_search', '')
    search_jeepney_code = request.GET.get('jeepney_code_search', '')

    # --- Routes for the Suggestions Panel (dynamic filtering) ---
    suggested_routes = Route.objects.all().order_by('transport_type', 'code', 'origin')

    if search_query_origin or search_query_destination or search_transport_type or search_jeepney_code:
        filters = Q()
        if search_query_origin:
            filters &= Q(origin__icontains=search_query_origin)
        if search_query_destination:
            filters &= Q(destination__icontains=search_query_destination)
        if search_transport_type and search_transport_type != '':
            filters &= Q(transport_type=search_transport_type)
        if search_jeepney_code and search_jeepney_code != '':
            filters &= Q(code=search_jeepney_code)
        
        suggested_routes = suggested_routes.filter(filters)
    
    # --- Handle GET request for initial page load or JS redirects with detected location ---
    if request.method == 'GET':
        get_origin_lat_str = request.GET.get('origin_latitude')
        get_origin_lon_str = request.GET.get('origin_longitude')
        get_origin_text = request.GET.get('origin_text')

        # Handle destination parameters from URL
        get_destination_lat_str = request.GET.get('destination_latitude')
        get_destination_lon_str = request.GET.get('destination_longitude')
        get_destination_text = request.GET.get('destination_text')

        if get_origin_lat_str and get_origin_lon_str:
            try:
                current_origin_lat = Decimal(get_origin_lat_str)
                current_origin_lon = Decimal(get_origin_lon_str)
                
                # Backend reverse geocoding for pre-filling form
                try:
                    reverse_location = geolocator.reverse(
                        (float(current_origin_lat), float(current_origin_lon)), timeout=5
                    )
                    if reverse_location:
                        get_origin_text = reverse_location.address
                        # Initialize form with both origin and destination if available
                        initial_data = {'origin': get_origin_text}
                        if get_destination_text:
                            initial_data['destination'] = get_destination_text
                        form = RouteForm(initial=initial_data)
                    else:
                        get_origin_text = f"Lat: {get_origin_lat_str}, Lon: {get_origin_lon_str}"
                        print(f"WARNING: Backend reverse geocoding failed for {get_origin_lat_str},{get_origin_lon_str}")
                except (GeocoderTimedOut, GeocoderServiceError) as e:
                    get_origin_text = f"Lat: {get_origin_lat_str}, Lon: {get_origin_lon_str}"
                    print(f"ERROR: Backend reverse geocoding service error: {e}")

            except InvalidOperation:
                print("WARNING: Invalid latitude/longitude from GET parameters.")

        #  Handle destination coordinates from URL
        if get_destination_lat_str and get_destination_lon_str:
            try:
                current_destination_lat = Decimal(get_destination_lat_str)
                current_destination_lon = Decimal(get_destination_lon_str)
                
                # Pre-fill destination form field with the raw text
                if get_destination_text and not form.initial:
                    form = RouteForm(initial={
                        'origin': get_origin_text if get_origin_text else '',
                        'destination': get_destination_text
                    })
                elif get_destination_text and form.initial:
                    # Update existing form initial data
                    form.initial['destination'] = get_destination_text
                
            except InvalidOperation:
                print("WARNING: Invalid destination latitude/longitude from GET parameters.")
        
        if not form.initial:
            form = RouteForm()

    # --- Handle POST request for saving new routes ---
    elif request.method == 'POST':
        form = RouteForm(request.POST) 
        if form.is_valid():
            route_instance = form.save(commit=False)

            origin_text = route_instance.origin
            destination_text = route_instance.destination
            
            # Check for hidden client-side coordinates for origin
            post_origin_lat_str = request.POST.get('origin_latitude')
            post_origin_lon_str = request.POST.get('origin_longitude')
            
            if post_origin_lat_str and post_origin_lon_str:
                try:
                    route_instance.origin_latitude = Decimal(post_origin_lat_str)
                    route_instance.origin_longitude = Decimal(post_origin_lon_str)
                    current_origin_lat = Decimal(post_origin_lat_str)
                    current_origin_lon = Decimal(post_origin_lon_str)
                except InvalidOperation:
                    error_message = "Invalid origin coordinates from client-side detection."
                    print(f"ERROR: Invalid client-side origin coords: {post_origin_lat_str}, {post_origin_lon_str}")
            else: 
                try:
                    search_query = origin_text.strip()
                    lower_origin = search_query.lower()

                    if not any(city in lower_origin for city in ["cebu", "mandaue", "lapu", "liloan", "consolacion", "talisay"]):
                        search_query += ", Cebu City, Philippines"

                    origin_location = safe_geocode(search_query)

                    if origin_location:
                        route_instance.origin_latitude = Decimal(str(origin_location.latitude))
                        route_instance.origin_longitude = Decimal(str(origin_location.longitude))
                    else:
                        error_message = f"Could not find coordinates for origin: {origin_text}"

                except (GeocoderTimedOut, GeocoderServiceError) as e:
                    error_message = f"Geocoding service error for Origin: {origin_text}. Try again later. ({e})"
                    print(f"ERROR: Geocoding service error for origin: {e}")

            # Geocode destination
            if not error_message:
                try:
                    search_query = destination_text.strip()
                    lower_dest = search_query.lower()

                    if not any(city in lower_dest for city in ["cebu", "mandaue", "lapu", "liloan", "consolacion", "talisay"]):
                        search_query += ", Cebu City, Philippines"

                    destination_location = safe_geocode(search_query)

                    if destination_location:
                        route_instance.destination_latitude = Decimal(str(destination_location.latitude))
                        route_instance.destination_longitude = Decimal(str(destination_location.longitude))
                    else:
                        error_message = f"Could not find coordinates for destination: {destination_text}"

                except (GeocoderTimedOut, GeocoderServiceError) as e:
                    error_message = f"Geocoding service error for Destination: {destination_text}. Try again later. ({e})"
                    print(f"ERROR: Geocoding service error for destination: {e}")
            
            # ===== NEW: Distance/Time/Fare Calc using ORS =====
            if not error_message and route_instance.origin_latitude and route_instance.origin_longitude and \
               route_instance.destination_latitude and route_instance.destination_longitude:
                
                # Use ORS to calculate real route distance and time
                distance_km, travel_time_minutes, route_geojson = get_route_and_calculate(
                    route_instance.origin_latitude, 
                    route_instance.origin_longitude,
                    route_instance.destination_latitude, 
                    route_instance.destination_longitude,
                    route_instance.transport_type
                )
                
                if distance_km and travel_time_minutes:
                    route_instance.distance_km = distance_km
                    route_instance.travel_time_minutes = travel_time_minutes
                    route_instance.fare = calculate_fare(route_instance.transport_type, distance_km, travel_time_minutes)
                    
                    # Store the actual route path coordinates
                    store_route_path(route_instance, route_geojson)
                else:
                    error_message = "Could not calculate route using OpenRouteService. Please try again."
            else:
                error_message = error_message or "Missing coordinates for distance/fare calculation."

            # Save if no errors
            if not error_message:
                try:
                    route_instance.code = request.POST.get('code')
                    if route_instance.transport_type != 'Jeepney':
                        route_instance.code = None

                    route_instance.save()
                    success_message = "Route saved!"
                    print(f"INFO: Saved: {route_instance.transport_type} {route_instance.code or 'N/A'}: {route_instance.origin} to {route_instance.destination} (Distance: {route_instance.distance_km} km, Fare: Php {route_instance.fare or 'N/A'})")
                    return redirect('routes_page')
                except DatabaseError as e:
                    error_message = f"DB Error: {e}"
                    print(f"ERROR: DB Error saving route: {e}")
                except Exception as e:
                    error_message = f"Unexpected error saving route: {e}"
                    print(f"ERROR: Unexpected error saving route: {e}")
            
        
        context = {
            'form': form, 'error_message': error_message, 'success_message': success_message,
            'map': map_html, 'all_routes': suggested_routes, 'get_origin_text': get_origin_text,
            'search_origin': search_query_origin, 'search_destination': search_query_destination,
            'search_transport_type': search_transport_type, 'search_jeepney_code': search_jeepney_code,
        }
        return render(request, 'route_input/index.html', context)
    
    # ===== NEW: Render routes with actual ORS polylines =====
    map_center_lat = 10.3157
    map_center_lon = 123.8854

    # Update map center to show both origin and destination if available
    if current_origin_lat and current_origin_lon and current_destination_lat and current_destination_lon:
        # Center between origin and destination
        map_center_lat = (float(current_origin_lat) + float(current_destination_lat)) / 2
        map_center_lon = (float(current_origin_lon) + float(current_destination_lon)) / 2
    elif current_origin_lat and current_origin_lon:
        map_center_lat = float(current_origin_lat)
        map_center_lon = float(current_origin_lon)
    elif current_destination_lat and current_destination_lon:
        map_center_lat = float(current_destination_lat)
        map_center_lon = float(current_destination_lon)
        
    m = folium.Map(location=[map_center_lat, map_center_lon], zoom_start=14)

    # Plot current detected location (origin)
    if current_origin_lat and current_origin_lon:
        popup_text = "Your Current Location"
        if get_origin_text:
            popup_text = get_origin_text
        folium.Marker(
            [float(current_origin_lat), float(current_origin_lon)],
            popup=popup_text,
            icon=folium.Icon(color='blue', icon='location-dot', prefix='fa')
        ).add_to(m)
    
    # Plot destination marker from URL parameters
    if current_destination_lat and current_destination_lon:
        popup_text = "Your Destination"
        if get_destination_text:
            popup_text = get_destination_text
        folium.Marker(
            [float(current_destination_lat), float(current_destination_lon)],
            popup=popup_text,
            icon=folium.Icon(color='darkred', icon='flag-checkered', prefix='fa')
        ).add_to(m)

    # Plot all existing routes with actual ORS polylines
    for route in suggested_routes: 
        if all([route.origin_latitude, route.origin_longitude, route.destination_latitude, route.destination_longitude]):
            
            # Origin marker
            folium.Marker(
                [float(route.origin_latitude), float(route.origin_longitude)],
                popup=f"Origin: {route.origin}<br>Type: {route.transport_type}<br>Code: {route.code or 'N/A'}<br>Fare: Php {route.fare or 'N/A'}",
                icon=folium.Icon(color='green', icon='play', prefix='fa')
            ).add_to(m)

            # Destination marker
            folium.Marker(
                [float(route.destination_latitude), float(route.destination_longitude)],
                popup=f"Destination: {route.destination}<br>Type: {route.transport_type}<br>Code: {route.code or 'N/A'}<br>Fare: Php {route.fare or 'N/A'}",
                icon=folium.Icon(color='red', icon='stop', prefix='fa')
            ).add_to(m)

            # NEW: Use stored route path if available, otherwise fall back to straight line
            path_coords = route.get_path_coords()
            if path_coords and len(path_coords) > 0:
                # Draw actual route polyline from ORS coordinates
                folium.PolyLine(
                    path_coords,
                    color="purple",
                    weight=3,
                    opacity=0.7,
                    popup=f"Route {route.code or 'N/A'}: {route.origin} to {route.destination}<br>Type: {route.transport_type}<br>Distance: {route.distance_km or 'N/A'} km<br>Time: {route.travel_time_minutes or 'N/A'} min<br>Fare: Php {route.fare or 'N/A'}"
                ).add_to(m)
            else:
                # Fallback: straight line if no path stored
                points = [
                    (float(route.origin_latitude), float(route.origin_longitude)),
                    (float(route.destination_latitude), float(route.destination_longitude))
                ]
                folium.PolyLine(
                    points,
                    color="purple",
                    weight=3,
                    opacity=0.7,
                    popup=f"Route {route.code or 'N/A'}: {route.origin} to {route.destination}<br>Type: {route.transport_type}<br>Distance: {route.distance_km or 'N/A'} km<br>Time: {route.travel_time_minutes or 'N/A'} min<br>Fare: Php {route.fare or 'N/A'}"
                ).add_to(m)

    map_html = m._repr_html_()
    # Context for rendering (for both GET and POST re-renders)
    context = {
        'form': form,
        'success_message': success_message,
        'error_message': error_message,
        'map': map_html,
        'all_routes': suggested_routes, 
        'get_origin_text': get_origin_text, 
        'get_destination_text': get_destination_text,
        'search_origin': search_query_origin,
        'search_destination': search_query_destination,
        'search_transport_type': search_transport_type,
        'search_jeepney_code': search_jeepney_code,
    }

    # FIXED: Handle saved routes with user field
    if request.user.is_authenticated:
        saved_routes = SavedRoute.objects.filter(user=request.user)
    else:
        sk = _get_session_key(request)
        saved_routes = SavedRoute.objects.filter(session_key=sk)
        
        context['saved_routes'] = saved_routes
    return render(request, 'route_input/index.html', context)

def _get_session_key(request):
    """Ensure each user (even anonymous) has a unique session key."""
    if not request.session.session_key:
        request.session.create()
    return request.session.session_key


@csrf_exempt
def save_current_route(request):
    """Save a route that the user manually inputs and likes."""
    if request.method == "POST":
        origin = request.POST.get("origin")
        destination = request.POST.get("destination")
        transport_type = request.POST.get("transport_type")
        code = request.POST.get("code")
        fare_val = request.POST.get("fare")
        notes = request.POST.get("notes")

        # Try finding the route if it already exists
        route = Route.objects.filter(
            Q(origin=origin) & Q(destination=destination) &
            Q(transport_type=transport_type) & Q(code=code)
        ).first()

        saved = SavedRoute.objects.create(
            user=request.user if request.user.is_authenticated else None,
            session_key=_get_session_key(request),
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
            notes=notes or ""
        )

        return JsonResponse({"message": "Route saved successfully!", "id": saved.id})

    return JsonResponse({"error": "Invalid request"}, status=400)


@csrf_exempt
def save_suggested_route(request):
    """Save a route suggested by other users."""
    if request.method == "POST":
        route_id = request.POST.get("route_id")

        try:
            route = Route.objects.get(pk=route_id)
        except Route.DoesNotExist:
            return JsonResponse({"error": "Route not found"}, status=404)

        saved = SavedRoute.objects.create(
            user=request.user if request.user.is_authenticated else None,
            session_key=_get_session_key(request),
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
            notes=route.notes or ""
        )

        return JsonResponse({"message": "Suggested route saved!", "id": saved.id})

    return JsonResponse({"error": "Invalid request"}, status=400)

@require_POST
def delete_saved_route(request):
    """
    Delete a saved route by id (only if owned by current user or session_key).
    Expects 'saved_id' in POST.
    """
    saved_id = request.POST.get('saved_id')
    if not saved_id:
        return JsonResponse({'success': False, 'error': 'saved_id required.'}, status=400)

    try:
        saved = SavedRoute.objects.get(pk=int(saved_id))
    except (SavedRoute.DoesNotExist, ValueError):
        return JsonResponse({'success': False, 'error': 'Not found.'}, status=404)

    # Ownership check: user or session
    if request.user.is_authenticated:
        if saved.user != request.user:
            return JsonResponse({'success': False, 'error': 'Forbidden.'}, status=403)
    else:
        if saved.session_key != _get_session_key(request):
            return JsonResponse({'success': False, 'error': 'Forbidden.'}, status=403)

    saved.delete()
    return JsonResponse({'success': True})

@require_POST
@csrf_exempt  # optional if JS doesn't yet send CSRF
def save_route(request):
    try:
        user = request.user if request.user.is_authenticated else None
        data = request.POST

        route = SavedRoute.objects.create(
            user=user,
            origin=data.get('origin', ''),
            destination=data.get('destination', ''),
            origin_latitude=float(data.get('origin_latitude', 0)),
            origin_longitude=float(data.get('origin_longitude', 0)),
            destination_latitude=float(data.get('destination_latitude', 0)),
            destination_longitude=float(data.get('destination_longitude', 0)),
            transport_type=data.get('transport_type', 'Unknown'),
            code=data.get('code', ''),
            fare=float(data.get('fare', 0))
        )

        return JsonResponse({
            'success': True,
            'route': {
                'id': route.id,
                'origin': route.origin,
                'destination': route.destination,
                'transport_type': route.transport_type,
                'code': route.code,
                'fare': float(route.fare)
            }
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


def get_jeep_codes(request):
    return JsonResponse({'codes': [code for code, _ in JEEPNEY_CODE_CHOICES]})