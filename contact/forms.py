from django import forms

class ContactForm(forms.Form):
    name = forms.CharField(max_length=100, label='Your Name',
                           widget=forms.TextInput(attrs={'class': 'form-control','placeholder': 'Enter Your Name'}))
    email = forms.EmailField(label='Your Email',
                             required=True,
                             widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'your email address'}))
    phone = forms.CharField(
        max_length=15,
        label='Your Phone Number',
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional WhatsApp or phone number'})
    )
    subject = forms.CharField(max_length=200, required=True,
                              widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Subject'}))

    # CharField with Textarea widget for a larger multi-line input box.
    message = forms.CharField(widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Your Message'}),
                              required=True)
    