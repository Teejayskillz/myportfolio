from django.shortcuts import render, redirect
from django.conf import settings
from django.contrib import messages
import os 
from .forms import ContactForm
from .utils import send_email_via_brevo  # import your Brevo function
import requests 

def contact_view(request):
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            
            name = form.cleaned_data['name']
            email = form.cleaned_data['email']
            phone = form.cleaned_data.get('phone', 'Not provided')

            subject = form.cleaned_data['subject']
            message = form.cleaned_data['message']

            full_subject = f"Portfolio Contact Form: {subject} from {name}"
            full_message = f"Name: {name}\nEmail: {email}\n\nMessage:\n{message} \n\nphone: {phone}"

            try:
                # Use Brevo API instead of send_mail
                response = send_email_via_brevo(
                    subject=full_subject,
                    to_email='contact@lagoswebdev.com',  # your destination inbox
                    content=full_message.replace("\n", "<br>"),
                    api_key=os.environ.get('BREVO_API_KEY')
                )

                if response.status_code == 201:
                    messages.success(request, 'Your message has been sent successfully! I will get back to you soon.')
                    return redirect('pages:home')
                else:
                    messages.error(request, f"Email failed to send. Brevo error: {response.status_code} - {response.text}")
            except Exception as e:
                messages.error(request, f"There was an error sending your message. Please try again later. Error: {e}")
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = ContactForm()

    return render(request, 'contact/contact.html', {'form': form})
