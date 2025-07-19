from redis import Redis

from django.conf import settings
from rest_framework import serializers

from user_auth.serializers import UserSerializer
from utils.redis_key_generator import get_key_for_document
from .models import Document, DocumentAccess, Comment

class DocumentSerializer(serializers.ModelSerializer):
    live_members_count = serializers.SerializerMethodField()
    can_write_access = serializers.SerializerMethodField()  # ✅ Add this

    class Meta:
        model = Document
        fields = '__all__'
        read_only_fields = [
            'admin', 'created_at', 'updated_at', 'share_token',
            'live_members_count', 'can_write_access'
        ]

    def get_live_members_count(self, obj):
        if not obj.is_live:
            return 0
        redis = Redis.from_url(settings.REDIS_URL)
        key: str = get_key_for_document(obj.share_token)
        try:
            return redis.scard(key)
        except redis.exceptions.ConnectionError:
            return 0

    def get_can_write_access(self, obj):
        request = self.context.get("request")

        if not request or not request.user:
            return False

        user = request.user
        # Admin always has write access
        if obj.admin == user:
            return True

        # Check DocumentAccess.can_edit
        return obj.accesses.filter(user=user, can_edit=True, access_approved=True).exists()


class DocumentAccessSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    document = DocumentSerializer(read_only=True)

    class Meta:
        model = DocumentAccess
        fields = "__all__"
        read_only_fields = ['request_at', 'approved_at']

class CommentSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Comment
        fields = ['id', 'content', 'commented_at', 'updated_at', 'user']
        read_only_fields = ['id', 'commented_at', 'updated_at', 'user']

    def get_user(self, obj):
        return {
            "email": obj.user.email,
            "first_name": obj.user.first_name,
            "last_name": obj.user.last_name
        }
