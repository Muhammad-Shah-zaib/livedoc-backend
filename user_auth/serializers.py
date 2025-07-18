from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from user_auth.models import CustomUser  # Adjust import if needed
from utils.validators import validate_password_strength

class UserSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(
        required=True,
        validators=[
            UniqueValidator(
                queryset=CustomUser.objects.all(),
                message="A user with this email already exists."
            )
        ],
        error_messages={
            "blank": "Email cannot be empty.",
            "required": "Email is required."
        }
    )

    password = serializers.CharField(
        write_only=True,
        min_length=6,
        error_messages={
            "min_length": "Password must be at least 6 characters long.",
            "blank": "Password cannot be empty.",
            "required": "Password is required."
        },
        validators=[validate_password_strength]
    )

    first_name = serializers.CharField(
        error_messages={
            "blank": "First name cannot be empty.",
            "required": "First name is required."
        }
    )

    class Meta:
        model = CustomUser
        fields = ['id', 'email', 'first_name', 'last_name', 'password', 'is_active', 'is_oauth_verified']
        read_only_fields = ['id', 'is_active', 'is_oauth_verified']

    def create(self, validated_data):
        return CustomUser.objects.create_user(
            email=validated_data['email'].strip().lower(),
            password=validated_data['password'],
            first_name=validated_data['first_name'],
            last_name=validated_data.get('last_name', '')
        )


class UserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name']

class PasswordChangeSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True,
        min_length=6,
        error_messages={
            "min_length": "New password must be at least 6 characters long.",
            "blank": "New password cannot be empty.",
            "required": "New password is required."
        },
        validators=[validate_password_strength]
    )

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value

    def save(self, **kwargs):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user
