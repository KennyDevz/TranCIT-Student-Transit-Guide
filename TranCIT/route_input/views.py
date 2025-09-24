from django.shortcuts import render

def index(request):
    submitted_data = None
    if request.method == 'POST':
        submitted_data = {
            'origin': request.POST.get('origin'),
            'destination': request.POST.get('destination'),
            'transport_type': request.POST.get('transport_type'),
            'fare': request.POST.get('fare'),
        }
    return render(request, 'route_input/index.html', {'submitted_data': submitted_data})
