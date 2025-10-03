from django.shortcuts import render, redirect
from django.db import DatabaseError
from django.db.models import Q
from .forms import RouteForm
import folium
from .models import Route
from decimal import Decimal, InvalidOperation
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

# Init geolocator
geolocator = Nominatim(user_agent="trancit_app_geocoder")

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

# Main Index View
def index(request):
    error_message = None
    success_message = None
    map_html = ""
    form = RouteForm()
    
    current_origin_lat = None
    current_origin_lon = None
    current_destination_lat = None
    current_destination_lon = None
    get_origin_text = None

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
    
    # --- End Suggestions Filtering ---


    # --- Handle GET request for initial page load or JS redirects with detected location ---
    if request.method == 'GET':
        get_origin_lat_str = request.GET.get('origin_latitude')
        get_origin_lon_str = request.GET.get('origin_longitude')
        get_origin_text = request.GET.get('origin_text')

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
                        form = RouteForm(initial={'origin': get_origin_text})
                    else:
                        get_origin_text = f"Lat: {get_origin_lat_str}, Lon: {get_origin_lon_str}"
                        print(f"WARNING: Backend reverse geocoding failed for {get_origin_lat_str},{get_origin_lon_str}")
                except (GeocoderTimedOut, GeocoderServiceError) as e:
                    get_origin_text = f"Lat: {get_origin_lat_str}, Lon: {get_origin_lon_str}"
                    print(f"ERROR: Backend reverse geocoding service error: {e}")

            except InvalidOperation:
                print("WARNING: Invalid latitude/longitude from GET parameters.")
        
        if not form.initial:
            form = RouteForm()

    # --- Handle POST request for saving new routes ---
    elif request.method == 'POST':
        form = RouteForm(request.POST) 
        if form.is_valid():
            route_instance = form.save(commit=False)

            origin_text = route_instance.origin
            destination_text = route_instance.destination
            
            # Check for hidden client-side coordinates for origin (from JS detect location)
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
            else: # Fallback to geocoding text origin if no client-side coords
                try:
                    origin_location = geolocator.geocode(origin_text + ", Cebu City, Philippines", timeout=5)
                    if origin_location:
                        route_instance.origin_latitude = Decimal(origin_location.latitude)
                        route_instance.origin_longitude = Decimal(origin_location.longitude)
                        current_origin_lat = origin_location.latitude
                        current_origin_lon = origin_location.longitude
                    else:
                        error_message = f"Could not find coordinates for Origin: '{origin_text}'. Try a more general name."
                        print(f"ERROR: Geocoding failed for origin: {origin_text}")
                except (GeocoderTimedOut, GeocoderServiceError) as e:
                    error_message = f"Geocoding service error for Origin: {origin_text}. Try again later. ({e})"
                    print(f"ERROR: Geocoding service error for origin: {e}")

            # Geocode destination
            if not error_message:
                try:
                    destination_location = geolocator.geocode(destination_text + ", Cebu City, Philippines", timeout=5)
                    if destination_location:
                        route_instance.destination_latitude = Decimal(destination_location.latitude)
                        route_instance.destination_longitude = Decimal(destination_location.longitude)
                        current_destination_lat = destination_location.latitude
                        current_destination_lon = destination_location.longitude
                    else:
                        error_message = f"Could not find coordinates for Destination: '{destination_text}'. Try a more general name."
                        print(f"ERROR: Geocoding failed for destination: {destination_text}")
                except (GeocoderTimedOut, GeocoderServiceError) as e:
                    error_message = f"Geocoding service error for Destination: {destination_text}. Try again later. ({e})"
                    print(f"ERROR: Geocoding service error for destination: {e}")
            
            # Distance/Time/Fare Calc
            if not error_message and route_instance.origin_latitude and route_instance.origin_longitude and \
               route_instance.destination_latitude and route_instance.destination_longitude:
                distance_km, travel_time_minutes = calculate_distance_and_time(
                    route_instance.origin_latitude, route_instance.origin_longitude,
                    route_instance.destination_latitude, route_instance.destination_longitude
                )
                route_instance.distance_km = distance_km
                route_instance.travel_time_minutes = travel_time_minutes
                route_instance.fare = calculate_fare(route_instance.transport_type, distance_km, travel_time_minutes)
            else:
                error_message = error_message or "Missing coordinates for distance/fare calculation."

            # Save if no errors
            if not error_message:
                try:
                    route_instance.code = request.POST.get('code') # Get code from hidden input
                    if route_instance.transport_type != 'Jeepney':
                        route_instance.code = None

                    route_instance.save()
                    success_message = "Route saved!"
                    print(f"INFO: Saved: {route_instance.transport_type} {route_instance.code or 'N/A'}: {route_instance.origin} to {route_instance.destination} (Fare: Php {route_instance.fare or 'N/A'})")
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
    
    
    map_center_lat = 10.3157
    map_center_lon = 123.8854

    if current_origin_lat and current_origin_lon:
        map_center_lat = float(current_origin_lat)
        map_center_lon = float(current_origin_lon)
        
    m = folium.Map(location=[map_center_lat, map_center_lon], zoom_start=14)

    # Plot current detected
    if current_origin_lat and current_origin_lon:
        popup_text = "Your Current Location"
        if get_origin_text:
            popup_text = get_origin_text
        folium.Marker(
            [float(current_origin_lat), float(current_origin_lon)],
            popup=popup_text,
            icon=folium.Icon(color='blue', icon='location-dot', prefix='fa')
        ).add_to(m)
    
    
    if current_destination_lat and current_destination_lon:
        folium.Marker(
            [float(current_destination_lat), float(current_destination_lon)],
            popup="Your Destination",
            icon=folium.Icon(color='darkred', icon='flag-checkered', prefix='fa')
        ).add_to(m)

    # Plot all existing routes
    for route in suggested_routes: 
        if all([route.origin_latitude, route.origin_longitude, route.destination_latitude, route.destination_longitude]):
            folium.Marker(
                [float(route.origin_latitude), float(route.origin_longitude)],
                popup=f"Origin: {route.origin}<br>Type: {route.transport_type}<br>Code: {route.code or 'N/A'}<br>Fare: Php {route.fare or 'N/A'}",
                icon=folium.Icon(color='green', icon='play', prefix='fa')
            ).add_to(m)

            folium.Marker(
                [float(route.destination_latitude), float(route.destination_longitude)],
                popup=f"Destination: {route.destination}<br>Type: {route.transport_type}<br>Code: {route.code or 'N/A'}<br>Fare: Php {route.fare or 'N/A'}",
                icon=folium.Icon(color='red', icon='stop', prefix='fa')
            ).add_to(m)

            points = [
                (float(route.origin_latitude), float(route.origin_longitude)),
                (float(route.destination_latitude), float(route.destination_longitude))
            ]
            folium.PolyLine(points, color="purple", weight=3, opacity=0.7,
                            popup=f"Route {route.code or 'N/A'}: {route.origin} to {route.destination}<br>Type: {route.transport_type}<br>Distance: {route.distance_km or 'N/A'} km<br>Time: {route.travel_time_minutes or 'N/A'} min<br>Fare: Php {route.fare or 'N/A'}").add_to(m)

    map_html = m._repr_html_()

    # Context for rendering (for both GET and POST re-renders)
    context = {
        'form': form,
        'success_message': success_message,
        'error_message': error_message,
        'map': map_html,
        'all_routes': suggested_routes, 
        'get_origin_text': get_origin_text, 
        'search_origin': search_query_origin,
        'search_destination': search_query_destination,
        'search_transport_type': search_transport_type,
        'search_jeepney_code': search_jeepney_code,
    }
    return render(request, 'route_input/index.html', context)