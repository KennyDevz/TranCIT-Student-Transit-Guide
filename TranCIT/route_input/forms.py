from django import forms
from .models import Route

class RouteForm(forms.ModelForm):
    class Meta:
        model = Route
        fields = ['origin', 'destination', 'optional_stops', 'fare']
        widgets = {
            'origin': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter origin'}),
            'destination': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter destination'}),
            'optional_stops': forms.Textarea(attrs={'rows': 2, 'class': 'form-control', 'placeholder': 'Optional stops'}),
            'fare': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
        }
