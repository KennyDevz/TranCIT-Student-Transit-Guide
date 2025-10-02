from django import forms
from .models import Route

class RouteForm(forms.ModelForm):
    class Meta:
        model = Route
        fields = ['origin', 'destination', 'fare'] 
        widgets = {
            'origin': forms.TextInput(attrs={'placeholder': 'Enter current location'}),
            'destination': forms.TextInput(attrs={'placeholder': 'Search destination'}),
            
            'fare': forms.NumberInput(attrs={'placeholder': 'Estimated Fare'}),
        }