from django.db import models
from django.contrib.auth import get_user_model
import uuid

User = get_user_model()

class Document(models.Model):
    admin = models.ForeignKey(User, on_delete=models.CASCADE, related_name='documents')
    name = models.CharField(max_length=255)
    content = models.TextField(blank=True)
    is_live = models.BooleanField(default=False)
    share_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.id} {self.name} ({self.admin})"


class DocumentAccess(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='accesses')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='document_accesses')
    can_edit = models.BooleanField(default=False)
    access_requested = models.BooleanField(default=False)
    access_approved = models.BooleanField(default=False)
    request_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('document', 'user')

    def __str__(self):
        return f"{self.user.username} access to {self.document.name}"


class Comment(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comments')
    content = models.TextField()
    commented_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    def __str__(self):
        return f"Comment by {self.user.username} on {self.document.name}"
