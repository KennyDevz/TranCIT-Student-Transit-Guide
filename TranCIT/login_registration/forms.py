from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

class RegistrationForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'autocomplete': 'username',
            'class': 'form-input'
        })
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'autocomplete': 'email',
            'class': 'form-input'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'autocomplete': 'new-password',
            'class': 'form-input'
        })
    )
    password_confirm = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'autocomplete': 'new-password',
            'class': 'form-input'
        })
    )

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise ValidationError("Username already exists.")
        if len(username) < 3:
            raise ValidationError("Username must be at least 3 characters long.")
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError("Email already registered.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')

        # Only validate if both fields are present
        if password and password_confirm:
            if len(password) < 8:
                raise ValidationError("Password must be at least 8 characters long.")
            
            if password != password_confirm:
                raise ValidationError("Passwords do not match.")

        return cleaned_data

class LoginForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'autocomplete': 'username',
            'class': 'form-input'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'autocomplete': 'current-password',
            'class': 'form-input'
        })
    )