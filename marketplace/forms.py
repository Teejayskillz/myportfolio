from django import forms
from .models import HostingPlan

from django import forms
from .models import HostingPlan

class CheckoutOptionsForm(forms.Form):
    DELIVERY_CHOICES = (
        ("full_ownership", "Full Ownership (Source Code + Docs)"),
        ("rent_own", "Rent & Host (Setup + Monthly)"),
    )

    delivery_type = forms.ChoiceField(choices=DELIVERY_CHOICES)
    hosting_plan = forms.ModelChoiceField(
        queryset=HostingPlan.objects.none(),
        required=False
    )

    def __init__(self, *args, **kwargs):
        product = kwargs.pop("product", None)
        super().__init__(*args, **kwargs)

        if product:
            self.fields["hosting_plan"].queryset = product.available_hosting_plans.filter(is_active=True)

    def clean(self):
        cleaned = super().clean()
        delivery_type = cleaned.get("delivery_type")
        hosting_plan = cleaned.get("hosting_plan")

        if delivery_type == "rent_own" and not hosting_plan:
            self.add_error("hosting_plan", "Please select a hosting plan for Rent & Host.")

        if delivery_type == "full_ownership":
            cleaned["hosting_plan"] = None  # ensure it doesn't carry over

        return cleaned


class BuyerDetailsForm(forms.Form):
    buyer_name = forms.CharField(max_length=255)
    buyer_email = forms.EmailField()
    whatsapp_number = forms.CharField(max_length=30)
    note = forms.CharField(widget=forms.Textarea, required=False)


class ReceiptUploadForm(forms.Form):
    receipt = forms.FileField()
