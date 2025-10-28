from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from .forms import RegistrationForm, LoginForm

def login_view(request):
    # If user is already authenticated, redirect them
    if request.user.is_authenticated:
        return redirect('/routes/')
    
    show_register = False
    
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            
            user = authenticate(request, username=username, password=password)
            
            if user is not None:
                login(request, user)
                return redirect('/routes/')
            else:
                # This handles authentication failures
                messages.error(request, 'Invalid username or password.')
        else:
            # This handles form validation errors
            for field_errors in form.errors.values():
                for error in field_errors:
                    messages.error(request, error)
    
    return render(request, 'login_registration/login.html', {
        'show_register': show_register
    })

def register_view(request):
    # If user is already authenticated, redirect them
    if request.user.is_authenticated:
        return redirect('/routes/')
    
    show_register = True
    
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            email = form.cleaned_data.get('email')
            password = form.cleaned_data.get('password')
            
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password
            )
            user.save()
            
            messages.success(request, 'Account created successfully! Please log in.')
            return redirect('login_registration:login')
        else:
            # Handle form validation errors
            for field_errors in form.errors.values():
                for error in field_errors:
                    messages.error(request, error)
    
    return render(request, 'login_registration/login.html', {
        'show_register': show_register
    })

def logout_view(request):
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('login_registration:login')