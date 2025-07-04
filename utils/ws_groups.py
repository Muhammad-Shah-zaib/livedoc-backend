import hashlib
import hmac
from django.conf import settings

def generate_admin_group_name(admin_id, share_token):
    secret_key = settings.SECRET_KEY.encode()
    message = f"{admin_id}:{share_token}".encode()
    h = hmac.new(secret_key, message, hashlib.sha256)
    return f"doc_admin_{h.hexdigest()}"


def generate_group_name_from_user_id(user_id):
    secret = settings.SECRET_KEY.encode("utf-8")  # Or another constant key
    message = str(user_id).encode("utf-8")

    h = hmac.new(secret, message, hashlib.sha256).hexdigest()
    return f"user_{h}"
