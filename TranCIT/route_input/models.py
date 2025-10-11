# --- START OF FILE route_input/models.py ---

from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal
import json

JEEPNEY_CODE_CHOICES = [
        ('01A', '01A'), ('01B', '01B'), ('01C', '01C'), ('01K', '01K'),
        ('02A', '02A'), ('02B', '02B'),
        ('03A', '03A'), ('03B', '03B'), ('03G', '03G'), ('03L', '03L'), ('03Q', '03Q'),
        ('04B', '04B'), ('04C', '04C'), ('04D', '04D'), ('04H', '04H'), ('04I', '04I'), ('04L', '04L'), ('04M', '04M'),
        ('06A', '06A'), ('06B', '06B'), ('06C', '06C'), ('06F', '06F'), ('06G', '06G'), ('06H', '06H'),
        ('07B', '07B'), ('07D', '07D'),
        ('08F', '08F'), ('08G', '08G'),
        ('09C', '09C'), ('09F', '09F'), ('09G', '09G'),
        ('10C', '10C'), ('10E', '10E'), ('10F', '10F'), ('10G', '10G'), ('10H', '10H'), ('10K', '10K'), ('10M', '10M'),
        ('11A', '11A'), ('11D', '11D'),
        ('12A', '12A'), ('12B', '12B'), ('12C', '12C'), ('12D', '12D'), ('12F', '12F'), ('12G', '12G'), ('12I', '12I'), ('12J', '12J'), ('12L', '12L'),
        ('13B', '13B'), ('13C', '13C'), ('13H', '13H'),
        ('14D', '14D'),
        ('15', '15'),
        ('17B', '17B'), ('17C', '17C'), ('17D', '17D'),
        ('20A', '20A'), ('20B', '20B'),
        ('21A', '21A'), ('21D', '21D'),
        ('22A', '22A'), ('22I', '22I'),
        ('23D', '23D'),
        ('24A', '24A'), ('24F', '24F'), ('24I', '24I'),
        ('26', '26'), ('27', '27'),
        ('41B', '41B'), ('41D', '41D'),
        ('42B', '42B'), ('42C', '42C'), ('42D', '42D'),
        ('62B', '62B'),
    ]

class Route(models.Model):
    TRANSPORT_CHOICES = [
        ('Jeepney', 'Jeepney'),
        ('Bus', 'Bus'),
        ('Taxi', 'Taxi'),
        ('Motorcycle', 'Motorcycle'),
    ]

    # JEEPNEY_CODE_CHOICES = [
    #     ('01A', '01A'), ('01B', '01B'), ('01C', '01C'), ('01K', '01K'),
    #     ('02A', '02A'), ('02B', '02B'),
    #     ('03A', '03A'), ('03B', '03B'), ('03G', '03G'), ('03L', '03L'), ('03Q', '03Q'),
    #     ('04B', '04B'), ('04C', '04C'), ('04D', '04D'), ('04H', '04H'), ('04I', '04I'), ('04L', '04L'), ('04M', '04M'),
    #     ('06A', '06A'), ('06B', '06B'), ('06C', '06C'), ('06F', '06F'), ('06G', '06G'), ('06H', '06H'),
    #     ('07B', '07B'), ('07D', '07D'),
    #     ('08F', '08F'), ('08G', '08G'),
    #     ('09C', '09C'), ('09F', '09F'), ('09G', '09G'),
    #     ('10C', '10C'), ('10E', '10E'), ('10F', '10F'), ('10G', '10G'), ('10H', '10H'), ('10K', '10K'), ('10M', '10M'),
    #     ('11A', '11A'), ('11D', '11D'),
    #     ('12A', '12A'), ('12B', '12B'), ('12C', '12C'), ('12D', '12D'), ('12F', '12F'), ('12G', '12G'), ('12I', '12I'), ('12J', '12J'), ('12L', '12L'),
    #     ('13B', '13B'), ('13C', '13C'), ('13H', '13H'),
    #     ('14D', '14D'),
    #     ('15', '15'),
    #     ('17B', '17B'), ('17C', '17C'), ('17D', '17D'),
    #     ('20A', '20A'), ('20B', '20B'),
    #     ('21A', '21A'), ('21D', '21D'),
    #     ('22A', '22A'), ('22I', '22I'),
    #     ('23D', '23D'),
    #     ('24A', '24A'), ('24F', '24F'), ('24I', '24I'),
    #     ('26', '26'), ('27', '27'),
    #     ('41B', '41B'), ('41D', '41D'),
    #     ('42B', '42B'), ('42C', '42C'), ('42D', '42D'),
    #     ('62B', '62B'),
    # ]

    origin = models.CharField(max_length=255)
    destination = models.CharField(max_length=255)
    
    origin_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    origin_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    destination_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    destination_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    transport_type = models.CharField(
        max_length=50,
        choices=TRANSPORT_CHOICES,
        default='Jeepney',
    )
    code = models.CharField(
        max_length=10,
        choices=JEEPNEY_CODE_CHOICES,
        null=True, blank=True,
    )

    route_path_coords = models.TextField(
        blank=True,
        help_text="JSON array of [[lat, lon], ...] points defining the route path. For Jeepneys."
    )

    distance_km = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    travel_time_minutes = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    fare = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['transport_type', 'code', 'origin']
        verbose_name = "Route"
        verbose_name_plural = "Routes"

    def __str__(self):
        if self.code and self.transport_type == 'Jeepney':
            return f"[{self.code}] {self.origin} to {self.destination} ({self.transport_type})"
        return f"{self.origin} to {self.destination} ({self.transport_type})"

    def get_path_coords(self):
        if self.route_path_coords:
            try:
                return json.loads(self.route_path_coords)
            except json.JSONDecodeError:
                return []
        return []


class SavedRoute(models.Model):
    """
    Model to store user's saved/favorite routes.
    Can reference an existing Route or store custom route data.
    """
    # If user authentication is implemented, link to user
    # User field for authenticated users
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True,
                             related_name='saved_routes',
                             help_text="User who saved this route")
    
    # Session-based identification (for users without authentication)
    session_key = models.CharField(max_length=255, null=True, blank=True, 
                                    help_text="Session ID for anonymous users")
    
    # Reference to original route (if saved from suggestions)
    original_route = models.ForeignKey(Route, on_delete=models.SET_NULL, 
                                       null=True, blank=True,
                                       related_name='saved_by_users')
    
    # Route details (copied from Route or user's custom route)
    origin = models.CharField(max_length=255)
    destination = models.CharField(max_length=255)
    
    origin_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    origin_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    destination_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    destination_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    transport_type = models.CharField(max_length=50)
    code = models.CharField(max_length=10, null=True, blank=True)
    
    route_path_coords = models.TextField(blank=True)
    
    distance_km = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    travel_time_minutes = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    fare = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    notes = models.TextField(blank=True)
    
    saved_at = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-last_used']
        verbose_name = "Saved Route"
        verbose_name_plural = "Saved Routes"

    def __str__(self):
        identifier = f"Session: {self.session_key[:8]}..." if self.session_key else "User Route"
        if self.code and self.transport_type == 'Jeepney':
            return f"{identifier} - [{self.code}] {self.origin} to {self.destination}"
        return f"{identifier} - {self.origin} to {self.destination} ({self.transport_type})"

    def get_path_coords(self):
        if self.route_path_coords:
            try:
                return json.loads(self.route_path_coords)
            except json.JSONDecodeError:
                return []
        return []

# --- END OF FILE route_input/models.py ---