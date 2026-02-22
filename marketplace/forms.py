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
            cleaned["hosting_plan"] = None  

        return cleaned


class BuyerDetailsForm(forms.Form):
    buyer_name = forms.CharField(max_length=255)
    buyer_email = forms.EmailField()
    whatsapp_number = forms.CharField(max_length=30)
    note = forms.CharField(widget=forms.Textarea, required=False)

    DOMAIN_OPTION_CHOICES = (
        ("none", "No domain"),
        ("have_domain", "I already have a domain"),
        ("need_domain", "I want Lagoswebdev to register a domain"),
    )

    domain_option = forms.ChoiceField(choices=DOMAIN_OPTION_CHOICES, required=False)
    domain_name = forms.CharField(max_length=253, required=False)

    def clean(self):
        cleaned = super().clean()
        opt = cleaned.get("domain_option") or "none"
        name = (cleaned.get("domain_name") or "").strip().lower()

        if opt in ("have_domain", "need_domain") and not name:
            self.add_error("domain_name", "Enter your domain name.")
        return cleaned

class ReceiptUploadForm(forms.Form):
    receipt = forms.FileField()