from django.db import models

class Route(models.Model):
    origin = models.CharField(max_length=100)
    destination = models.CharField(max_length=100)
    fare = models.DecimalField(max_digits=5, decimal_places=2)

    def __str__(self):
        return f"{self.origin} to {self.destination} - ${self.fare}"