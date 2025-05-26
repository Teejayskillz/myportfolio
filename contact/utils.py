import requests

def send_email_via_brevo(subject, to_email, content, api_key, sender_email="contact@lagoswebdev.com", sender_name="Lagos Web Dev"):
    url = "https://api.brevo.com/v3/smtp/email"
    headers = {
        "accept": "application/json",
        "api-key": api_key,
        "content-type": "application/json",
    }
    data = {
        "sender": {"name": sender_name, "email": sender_email},
        "to": [{"email": to_email}],
        "subject": subject,
        "htmlContent": f"<html><body><p>{content}</p></body></html>"
    }

    response = requests.post(url, headers=headers, json=data)
    return response
