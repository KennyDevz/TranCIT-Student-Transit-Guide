from django import forms
from .models import JEEPNEY_CODE_CHOICES, Route

# Left Panel: Used for planning routes and navigation
class RouteForm(forms.ModelForm):
    code = forms.ChoiceField(choices=JEEPNEY_CODE_CHOICES, required=False)
    class Meta:
        model = Route
        fields = [
            'origin',
            'destination',
            'transport_type',
            'notes',
        ]
        widgets = {
            'origin': forms.TextInput(attrs={'placeholder': 'Enter your current location', 'class': 'form-control'}),
            'destination': forms.TextInput(attrs={'placeholder': 'Enter your destination', 'class': 'form-control'}),
            'transport_type': forms.Select(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'placeholder': 'Any additional route notes (optional)', 'rows': 3, 'class': 'form-control'}),
        }
        labels = {
            'origin': 'Current Location (Text)',
            'destination': 'Destination (Text)',
            'transport_type': 'Transportation Type',
            'notes': 'Route Notes (Optional)',
        }

# Right Panel: Used for suggesting community jeepney routes
class JeepneySuggestionForm(forms.ModelForm):
    code = forms.ChoiceField(choices=JEEPNEY_CODE_CHOICES, required=True)
    class Meta:
        model = Route
        fields = [
            'origin',
            'destination',
            'code',
            'notes',
        ]
        widgets = {
            'origin': forms.TextInput(attrs={'placeholder': 'e.g., SM City Cebu', 'class': 'form-control'}),
            'destination': forms.TextInput(attrs={'placeholder': 'e.g., Ayala Center', 'class': 'form-control'}),
            'code': forms.Select(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'placeholder': 'Additional info about this route...', 'rows': 3, 'class': 'form-control'}),
        }
