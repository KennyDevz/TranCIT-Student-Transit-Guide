from django.shortcuts import render
import folium

def index(request):
    submitted_data = None
    if request.method == 'POST':
        submitted_data = {
            'origin': request.POST.get('origin'),
            'destination': request.POST.get('destination'),
            'transport_type': request.POST.get('transport_type'),
            'fare': request.POST.get('fare'),
        }
    
    m = folium.Map(location=[10.3157, 123.8854], zoom_start=13)
    folium.Marker([10.3157, 123.8854], popup="Cebu City").add_to(m)
    map_html = m._repr_html_()
    
    return render(
        request,
        'route_input/index.html',
        {
            'submitted_data': submitted_data,
            'map': map_html,
        }
    )