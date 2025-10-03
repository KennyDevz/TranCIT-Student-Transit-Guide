from django import forms
from .models import Route

class RouteForm(forms.ModelForm):
    class Meta:
        model = Route

        fields = [
            'origin',
            'destination',
            'transport_type',
            'notes', # Notes is user input
        ]
        widgets = {
            'origin': forms.TextInput(attrs={'placeholder': 'Enter your current location', 'class': 'form-control'}),
            'destination': forms.TextInput(attrs={'placeholder': 'Enter your destination', 'class': 'form-control'}),
            'transport_type': forms.Select(attrs={'class': 'form-control'}), # Select for choices
            'notes': forms.Textarea(attrs={'placeholder': 'Any additional route notes (optional)', 'rows': 3, 'class': 'form-control'}),
        }
        labels = {
            'origin': 'Current Location (Text)',
            'destination': 'Destination (Text)',
            'transport_type': 'Transportation Type',
            'notes': 'Route Notes (Optional)',
        }