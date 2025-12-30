
from django import forms

class CheckoutForm(forms.Form):
    buyer_name = forms.CharField(
        max_length=100, 
        widget=forms.TextInput(attrs={'placeholder': 'Your full name', 'class': 'form-control'})
    )
    buyer_email = forms.EmailField(
        widget=forms.EmailInput(attrs={'placeholder': 'Your email', 'class': 'form-control'})
    )
