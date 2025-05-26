# pricing/views.py
from django.shortcuts import render
from .models import PricingPlan # Import your model
import datetime # For current_year

def pricing_page_view(request):
    plans = PricingPlan.objects.all().order_by('order') # Get all plans, ordered

    # Add AOS delay to each plan object
    for i, plan in enumerate(plans):
        plan.aos_delay = i * 100 # Calculate delay: 0, 100, 200, etc.
    current_year = datetime.datetime.now().year
    return render(request, 'pricing/pricing_page.html', {
        'plans': plans,
        'current_year': current_year
    })