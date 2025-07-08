import re
from rest_framework import serializers

def validate_password_strength(value):
    if not re.search(r'[A-Z]', value):
        raise serializers.ValidationError("Password must contain at least one uppercase letter.")
    if not re.search(r'[!@#$%^&*(),.?\":{}|<>]', value):
        raise serializers.ValidationError("Password must contain at least one special character.")
    return value
