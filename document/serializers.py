from rest_framework import serializers
from .models import Document, DocumentAccess, Comment

class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = '__all__'
        read_only_fields = ['admin', 'created_at', 'updated_at', 'share_token']

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
        fields = ['id', 'content', 'commented_at', 'user']
        read_only_fields = ['id', 'commented_at', 'user']

    def get_user(self, obj):
        return {
            "email": obj.user.email,
            "first_name": obj.user.first_name,
            "last_name": obj.user.last_name
        }
