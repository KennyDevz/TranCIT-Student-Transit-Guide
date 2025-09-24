from django.db import models

class Route(models.Model):
    origin = models.CharField(max_length=100)
    destination = models.CharField(max_length=100)
    optional_stops = models.TextField(blank=True, null=True)
    fare = models.DecimalField(max_digits=5, decimal_places=2)
