from django import forms
from .models import HostingPlan


class CheckoutOptionsForm(forms.Form):
    DELIVERY_CHOICES = (
        ('hosted', 'Hosted'),
        ('source', 'Source Code'),
        ('both', 'Hosted + Source Code'),
    )

    delivery_type = forms.ChoiceField(choices=DELIVERY_CHOICES)
    hosting_plan = forms.ModelChoiceField(
        queryset=HostingPlan.objects.none(),
        required=False
    )

    def __init__(self, *args, **kwargs):
        product = kwargs.pop('product', None)
        super().__init__(*args, **kwargs)

        if product:
            self.fields['hosting_plan'].queryset = product.available_hosting_plans.filter(is_active=True)

class BuyerDetailsForm(forms.Form):
    buyer_name = forms.CharField(max_length=255)
    buyer_email = forms.EmailField()
    whatsapp_number = forms.CharField(max_length=30)
    note = forms.CharField(widget=forms.Textarea, required=False)


class ReceiptUploadForm(forms.Form):
    receipt = forms.FileField()
