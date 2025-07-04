from rest_framework import serializers
from .models import Document, DocumentAccess

class DocumentSerializer(serializers.ModelSerializer):
    """
    Serializer for a Document model.
    """
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