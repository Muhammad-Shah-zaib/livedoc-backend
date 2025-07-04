from django.conf import settings
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from utils.tokens import default_email_token_generator
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives


def send_verification_email(user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_email_token_generator.make_token(user)

    verify_url = f"http://localhost:8000/api/email-verification/{uid}/{token}/"

    subject = "Verify your email address"
    from_email = settings.DEFAULT_FROM_EMAIL
    to_email = user.email

    html_content = render_to_string("emails/verification_email.html", {
        "user": user,
        "verify_url": verify_url
    })

    email = EmailMultiAlternatives(subject, "", from_email, [to_email])
    email.attach_alternative(html_content, "text/html")
    email.send()



def send_reset_password_email(user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    reset_url = f"http://localhost:8000/api/reset-password/{uid}/{token}/"

    subject = "Reset your password"
    from_email = settings.DEFAULT_FROM_EMAIL
    to_email = user.email

    html_content = render_to_string("emails/reset_password_email.html", {
        "user": user,
        "reset_url": reset_url
    })

    email = EmailMultiAlternatives(subject, "", from_email, [to_email])
    email.attach_alternative(html_content, "text/html")
    email.send()