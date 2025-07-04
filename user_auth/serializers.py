from rest_framework import serializers
from user_auth.models import CustomUser  # Adjust import if needed

class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        min_length=6,
        error_messages={
            "min_length": "Password must be at least 6 characters long.",
            "blank": "Password cannot be empty.",
            "required": "Password is required."
        }
    )

    first_name = serializers.CharField(
        error_messages={
            "blank": "First name cannot be empty.",
            "required": "First name is required."
        }
    )
    class Meta:
        model = CustomUser
        fields = ['id', 'email', 'first_name', 'last_name', 'password', 'is_active']
        read_only_fields = ['id', 'is_active']

    def create(self, validated_data):
        return CustomUser.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data['first_name'],
            last_name=validated_data.get('last_name', '')
        )
