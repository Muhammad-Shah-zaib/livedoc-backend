from redis import Redis

from django.conf import settings
from rest_framework import serializers

from utils.redis_key_generator import get_key_for_document
from .models import Document, DocumentAccess, Comment

class DocumentSerializer(serializers.ModelSerializer):
    live_members_count = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = '__all__'
        read_only_fields = ['admin', 'created_at', 'updated_at', 'share_token', 'live_members_count']

    def get_live_members_count(self, obj):
        if not obj.is_live:
            return 0
        redis = Redis.from_url(settings.REDIS_URL)
        key: str = get_key_for_document(obj.share_token)
        try:
            print("Redis key for live members:", key)
            return redis.scard(key)  # number of unique users in the Redis set
        except redis.exceptions.ConnectionError:
            return 0


class DocumentAccessSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)
    document = serializers.StringRelatedField(read_only=True)

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
