from rest_framework import serializers

from user_auth.models import CustomUser  # Adjust import if needed
from utils.validators import validate_password_strength

class UserSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(
        required=True,
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

    def validate_email(self, value):
        """
        Custom email validation that allows re-registration for unverified accounts.
        If a user exists but hasn't verified their email and is inactive, 
        we delete the old record to allow re-registration.
        """
        email = value.strip().lower()
        existing_user = CustomUser.objects.filter(email=email).first()
        
        if existing_user:
            # If user is active or email is verified, they can't register again
            if existing_user.is_active or existing_user.is_email_verified:
                raise serializers.ValidationError("A user with this email already exists.")
            
            # If user exists but is inactive and unverified, delete to allow re-registration
            # This handles the case where someone signed up but never verified their email
            existing_user.delete()
        
        return email

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

class UserMetaSerializer(serializers.ModelSerializer):
    info = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = ['id', 'info']

    def get_info(self, obj):
        user_colors = [
            "#7F63F4", "#F47F63", "#63F4A1", "#63C8F4", "#F4D063",
            "#FF9AA2", "#B5EAD7", "#C7CEEA", "#FFDAC1", "#E2F0CB",
            "#FFB347", "#A0CED9", "#D291BC", "#779ECB", "#77DD77",
            "#FF6961", "#CB99C9", "#FDFD96", "#AEC6CF", "#F49AC2",
        ]
        color = user_colors[obj.id % len(user_colors)]
        name = f"{obj.first_name} {obj.last_name}".strip()
        return {
            "name": name,
            "color": color
        }

class UserInfoSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    email = serializers.EmailField()
    isOauthVerified = serializers.BooleanField()
    isActive = serializers.BooleanField()

class LiveUsersSerializer(serializers.Serializer):
    users = UserInfoSerializer(many=True)
