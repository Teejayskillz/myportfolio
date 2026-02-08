from django.shortcuts import render, redirect
from django.contrib import messages
from .models import ContactMessage

def contact_page(request):
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        email = request.POST.get("email", "").strip()
        message_text = request.POST.get("message", "").strip()

        if not name or not email or not message_text:
            messages.error(request, "Please fill in your name, email, and message.")
            return redirect("contact:contact_page")

        ContactMessage.objects.create(
            name=name,
            email=email,
            phone=request.POST.get("phone", "").strip(),
            project_type=request.POST.get("project_type", "").strip(),
            timeline=request.POST.get("timeline", "").strip(),
            budget=request.POST.get("budget", "").strip(),
            message=message_text,
        )
        messages.success(request, "Thanks! Your message has been submitted. I'll reply soon.")
        return redirect("contact:contact_page")

    return render(request, "contact/contact.html")
