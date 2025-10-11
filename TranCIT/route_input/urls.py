from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='routes_page'),
    path('save_current_route/', views.save_current_route, name='save_current_route'),
    path('save_suggested_route/', views.save_suggested_route, name='save_suggested_route'),
]