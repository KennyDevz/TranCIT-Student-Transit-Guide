from django.shortcuts import render, redirect
from django.db import DatabaseError
from django.db.models import Q
from .forms import RouteForm
import folium
from decimal import Decimal, InvalidOperation
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import json
from .models import Route # Ensure Route model is imported

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
    travel_time_minutes = distance_km * (60 / average_speed_kph)
    
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
    get_destination_text = None

    search_query_origin = request.GET.get('origin_search', '')
    search_query_destination = request.GET.get('destination_search', '')
    search_transport_type = request.GET.get('transport_type_search', '')
    search_jeepney_code = request.GET.get('jeepney_code_search', '')
    
    route_to_highlight_id = request.GET.get('highlight_route_id', None)

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
    
    if request.method == 'GET':
        get_origin_lat_str = request.GET.get('origin_latitude')
        get_origin_lon_str = request.GET.get('origin_longitude')
        get_origin_text = request.GET.get('origin_text')
        
        get_destination_lat_str = request.GET.get('destination_latitude')
        get_destination_lon_str = request.GET.get('destination_longitude')
        get_destination_text = request.GET.get('destination_text')

        # MODIFIED: Process origin coordinates from GET (or geocode origin_text if no coords provided)
        if get_origin_lat_str and get_origin_lon_str:
            try:
                current_origin_lat = Decimal(get_origin_lat_str)
                current_origin_lon = Decimal(get_origin_lon_str)
                
                if not get_origin_text: # Only reverse geocode if text wasn't provided in URL
                    try:
                        reverse_location = geolocator.reverse(
                            (float(current_origin_lat), float(current_origin_lon)), timeout=5
                        )
                        if reverse_location:
                            get_origin_text = reverse_location.address
                    except (GeocoderTimedOut, GeocoderServiceError) as e:
                        print(f"ERROR: Backend reverse geocoding service error for origin (coords): {e}")
            except InvalidOperation:
                print("WARNING: Invalid latitude/longitude from GET parameters for origin.")
        elif get_origin_text: # NEW: If only origin_text is provided, attempt to geocode it
            try:
                origin_location = geolocator.geocode(get_origin_text + ", Cebu City, Philippines", timeout=5)
                if origin_location:
                    current_origin_lat = Decimal(origin_location.latitude)
                    current_origin_lon = Decimal(origin_location.longitude)
                else:
                    print(f"WARNING: Geocoding failed for origin_text from GET: {get_origin_text}")
            except (GeocoderTimedOut, GeocoderServiceError) as e:
                print(f"ERROR: Geocoding service error for origin_text from GET: {e}")


        # Process destination coordinates from GET (or geocode destination_text if no coords provided)
        if get_destination_lat_str and get_destination_lon_str:
            try:
                current_destination_lat = Decimal(get_destination_lat_str)
                current_destination_lon = Decimal(get_destination_lon_str)
                
                if not get_destination_text: # Only reverse geocode if text wasn't provided in URL
                    try:
                        reverse_location = geolocator.reverse(
                            (float(current_destination_lat), float(current_destination_lon)), timeout=5
                        )
                        if reverse_location:
                            get_destination_text = reverse_location.address
                    except (GeocoderTimedOut, GeocoderServiceError) as e:
                        print(f"ERROR: Backend reverse geocoding service error for destination (coords): {e}")
            except InvalidOperation:
                print("WARNING: Invalid latitude/longitude from GET parameters for destination.")
        elif get_destination_text: # NEW: If only destination_text is provided, attempt to geocode it
            try:
                destination_location = geolocator.geocode(get_destination_text + ", Cebu City, Philippines", timeout=5)
                if destination_location:
                    current_destination_lat = Decimal(destination_location.latitude)
                    current_destination_lon = Decimal(destination_location.longitude)
                else:
                    print(f"WARNING: Geocoding failed for destination_text from GET: {get_destination_text}")
            except (GeocoderTimedOut, GeocoderServiceError) as e:
                print(f"ERROR: Geocoding service error for destination_text from GET: {e}")

        # Pre-fill form fields if human-readable text is available from GET
        initial_data = {}
        if get_origin_text:
            initial_data['origin'] = get_origin_text
        if get_destination_text:
            initial_data['destination'] = get_destination_text
        
        form = RouteForm(initial=initial_data)

    elif request.method == 'POST':
        form = RouteForm(request.POST) 
        if form.is_valid():
            route_instance = form.save(commit=False)

            origin_text = route_instance.origin
            destination_text = route_instance.destination
            
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

            if not error_message:
                post_dest_lat_str = request.POST.get('destination_latitude')
                post_dest_lon_str = request.POST.get('destination_longitude')

                if post_dest_lat_str and post_dest_lon_str:
                    try:
                        route_instance.destination_latitude = Decimal(post_dest_lat_str)
                        route_instance.destination_longitude = Decimal(post_dest_lon_str)
                        current_destination_lat = Decimal(post_dest_lat_str)
                        current_destination_lon = Decimal(post_dest_lon_str)
                    except InvalidOperation:
                        error_message = "Invalid destination coordinates from client-side detection."
                        print(f"ERROR: Invalid client-side destination coords: {post_dest_lat_str}, {post_dest_lon_str}")
                else:
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

            if not error_message:
                try:
                    route_instance.code = request.POST.get('code')
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
    zoom_start = 13 

    # MODIFIED: Adjust map center based on current origin if available
    if current_origin_lat and current_origin_lon:
        map_center_lat = float(current_origin_lat)
        map_center_lon = float(current_origin_lon)
        zoom_start = 14
    # NEW: Also adjust map center based on current destination if origin is not set but destination is
    elif current_destination_lat and current_destination_lon:
        map_center_lat = float(current_destination_lat)
        map_center_lon = float(current_destination_lon)
        zoom_start = 14
        
    m = folium.Map(location=[map_center_lat, map_center_lon], zoom_start=zoom_start, tiles='OpenStreetMap') # MODIFIED: Explicitly set tiles, you can change this

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
        popup_text = "Your Destination"
        if get_destination_text:
            popup_text = get_destination_text
        folium.Marker(
            [float(current_destination_lat), float(current_destination_lon)],
            popup=popup_text,
            icon=folium.Icon(color='darkred', icon='flag-checkered', prefix='fa')
        ).add_to(m)

    if route_to_highlight_id:
        try:
            highlight_route = Route.objects.get(id=route_to_highlight_id)
            routes_to_plot = [highlight_route]
            if highlight_route.origin_latitude and highlight_route.origin_longitude:
                 m.location = [float(highlight_route.origin_latitude), float(highlight_route.origin_longitude)]
            elif highlight_route.get_path_coords():
                first_path_point = highlight_route.get_path_coords()[0]
                m.location = [first_path_point[0], first_path_point[1]]
            zoom_start = 15
            m.zoom_start = zoom_start
        except Route.DoesNotExist:
            routes_to_plot = []
            error_message = "Requested route to highlight does not exist."
            print(f"ERROR: Route with ID {route_to_highlight_id} not found.")
    else:
        routes_to_plot = suggested_routes

    for route in routes_to_plot:
        if route.origin_latitude and route.origin_longitude:
            folium.Marker(
                [float(route.origin_latitude), float(route.origin_longitude)],
                popup=f"Origin: {route.origin}<br>Type: {route.transport_type}<br>Code: {route.code or 'N/A'}<br>Fare: Php {route.fare or 'N/A'}",
                icon=folium.Icon(color='green', icon='play', prefix='fa')
            ).add_to(m)

        if route.destination_latitude and route.destination_longitude:
            folium.Marker(
                [float(route.destination_latitude), float(route.destination_longitude)],
                popup=f"Destination: {route.destination}<br>Type: {route.transport_type}<br>Code: {route.code or 'N/A'}<br>Fare: Php {route.fare or 'N/A'}",
                icon=folium.Icon(color='red', icon='stop', prefix='fa')
            ).add_to(m)

        path_points = route.get_path_coords()
        if path_points:
            folium.PolyLine(
                path_points,
                color="blue" if route.id == int(route_to_highlight_id or 0) else "purple",
                weight=6 if route.id == int(route_to_highlight_id or 0) else 4,
                opacity=0.9,
                popup=f"Route {route.code or 'N/A'}: {route.origin} to {route.destination}<br>Type: {route.transport_type}<br>Distance: {route.distance_km or 'N/A'} km<br>Time: {route.travel_time_minutes or 'N/A'} min<br>Fare: Php {route.fare or 'N/A'}"
            ).add_to(m)
        else:
            if route.origin_latitude and route.origin_longitude and route.destination_latitude and route.destination_longitude:
                points = [
                    (float(route.origin_latitude), float(route.origin_longitude)),
                    (float(route.destination_latitude), float(route.destination_longitude))
                ]
                folium.PolyLine(
                    points,
                    color="gray",
                    weight=3,
                    opacity=0.7,
                    dash_array='5, 5',
                    popup=f"Route {route.code or 'N/A'}: {route.origin} to {route.destination}<br>Type: {route.transport_type}<br>Distance: {route.distance_km or 'N/A'} km<br>Time: {route.travel_time_minutes or 'N/A'} min<br>Fare: Php {route.fare or 'N/A'} (Approximation)"
                ).add_to(m)

    map_html = m._repr_html_()

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
        'highlight_route_id': route_to_highlight_id,
    }
    return render(request, 'route_input/index.html', context)