from django.shortcuts import render

# Create your views here.
# contact/views.py

from django.shortcuts import render, redirect # Import redirect for successful form submissions.
from django.core.mail import send_mail # Import send_mail to send emails.
from django.conf import settings # Import settings to access email configuration.
from django.contrib import messages # Import messages for user feedback (e.g., success/error).

from .forms import ContactForm # Import our ContactForm.

def contact_view(request):
    # Check if the request method is POST (meaning the form was submitted).
    if request.method == 'POST':
        # Create a form instance from the submitted data.
        form = ContactForm(request.POST)
        # Check if the submitted form data is valid according to our form's rules.
        if form.is_valid():
            # Extract cleaned (validated and converted) data from the form.
            name = form.cleaned_data['name']
            email = form.cleaned_data['email']
            subject = form.cleaned_data['subject']
            message = form.cleaned_data['message']

            # Construct the email subject for yourself.
            full_subject = f"Portfolio Contact Form: {subject} from {name}"
            # Construct the email message body.
            full_message = f"Name: {name}\nEmail: {email}\n\nMessage:\n{message}"

            try:
                # Send the email.
                # 'full_subject': The subject line of the email.
                # 'full_message': The body of the email.
                # 'settings.DEFAULT_FROM_EMAIL': The sender's email address (configured in settings.py).
                #   If not set, it defaults to settings.SERVER_EMAIL or 'webmaster@localhost'.
                # [settings.EMAIL_HOST_USER]: A list of recipients. Replace this with your actual email address.
                #   In production, you'd send it to your email like ['your_actual_email@example.com'].
                #   For development, you might just use settings.EMAIL_HOST_USER if configured.
                #   For console backend, any email here works for testing.
                send_mail(
                    full_subject,
                    full_message,
                    settings.DEFAULT_FROM_EMAIL, # Or simply 'your.email@example.com' for console backend testing
                    ['contact@sleekpedia.com.ng'], # <-- REPLACE WITH YOUR REAL EMAIL ADDRESS
                    fail_silently=False, # If True, suppresses exceptions raised during email sending. Keep False for debugging.
                )
                # Add a success message to be displayed to the user.
                messages.success(request, 'Your message has been sent successfully! I will get back to you soon.')
                # Redirect to the homepage or a thank-you page after successful submission.
                return redirect('pages:home') # Redirects to the homepage URL named 'home' in the 'pages' app.
            except Exception as e:
                # If an error occurs during email sending, add an error message.
                messages.error(request, f'There was an error sending your message. Please try again later. Error: {e}')
        else:
            # If the form is not valid, add an error message.
            messages.error(request, 'Please correct the errors below.')
    else:
        # If it's a GET request (meaning the user just navigated to the page), create an empty form.
        form = ContactForm()

    # Prepare the context dictionary to pass to the template.
    context = {
        'form': form # Pass the form instance to the template.
    }
    # Render the contact.html template, passing the form.
    return render(request, 'contact/contact.html', context)