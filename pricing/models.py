from django.db import models

# Create your models here.
# pricing/models.py

class PricingPlan(models.Model):
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2 )
    is_premium = models.BooleanField(default=False, help_text="Set to true for custom quote plans")
    features = models.TextField(help_text="Enter each feature on a new line") # Storing features as text, one per line
    button_text = models.CharField(max_length=50, default="Order Now")
    button_url_name = models.CharField(max_length=50, default="contact:contact_page", help_text="URL name (e.g., 'contact:contact_page')")
    order = models.IntegerField(default=0, help_text="Order in which plans are displayed")
    note = models.CharField(
        max_length=255, 
        blank=True, 
        null=True, 
        help_text="Optional note like: 'Best for enterprises, startups, and complex projects.'"
    )

    class Meta:
        ordering = ['order']
        verbose_name = "Pricing Plan"
        verbose_name_plural = "Pricing Plans"

    def get_features_list(self):
        return [f.strip() for f in self.features.split('\n') if f.strip()]

    def __str__(self):
        return self.name