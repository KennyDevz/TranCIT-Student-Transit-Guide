from django.shortcuts import render, redirect
from django.db import DatabaseError
from .forms import RouteForm
import folium
from .models import Route
from decimal import Decimal

def index(request):
    submitted_data = None
    error_message = None
    success_message = None
    map_html = ""

    if request.method == 'POST':
        form = RouteForm(request.POST)
        if form.is_valid():
            try:
                
                route = form.save() 
                submitted_data = {
                    'origin': route.origin,
                    'destination': route.destination,
                    'fare': route.fare,
                }
                success_message = "Route successfully saved!"
                print(f"INFO: Successfully saved new route to Supabase: {route.origin} to {route.destination} with fare {route.fare}") 

            except DatabaseError as e:
                error_message = f"Database Error: {e}"
                print(f"ERROR: DatabaseError while saving route: {e}")
            except Exception as e:
                error_message = f"An unexpected error occurred: {e}"
                print(f"ERROR: An unexpected error occurred while saving route: {e}")
        else:
            error_message = "Form is invalid. Please check your input."
            print(f"WARNING: Form is invalid: {form.errors}")
    else:
        form = RouteForm()

    m = folium.Map(location=[10.3157, 123.8854], zoom_start=13)
    folium.Marker([10.3157, 123.8854], popup="Cebu City").add_to(m)
    map_html = m._repr_html_()

    return render(
        request,
        'route_input/index.html',
        {
            'form': form,
            'submitted_data': submitted_data,
            'success_message': success_message,
            'error_message': error_message,
            'map': map_html,
        }
    )