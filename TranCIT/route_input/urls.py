from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='routes_page'),
    
    # ADD THESE TWO LINES:
    path('plan_route/', views.plan_route, name='plan_route'),
    path('suggest_route/', views.suggest_route, name='suggest_route'),

    path('save_current_route/', views.save_current_route, name='save_current_route'),
    path('save_suggested_route/', views.save_suggested_route, name='save_suggested_route'),
    path('logout/', views.logout_view, name='logout'),
]