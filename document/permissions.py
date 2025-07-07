from rest_framework.permissions import BasePermission
from document.models import Document, DocumentAccess, Comment

class IsAdminOfDocument(BasePermission):
    """
    Checks if the user is the admin of a Document.
    Supports:
    - Object-level permissions (when obj is a Document)
    - URL kwarg `access_id` for views using DocumentAccess
    """

    def has_object_permission(self, request, view, obj):
        # Direct object-level check for Document
        if isinstance(obj, Document):
            return obj.admin == request.user
        return False

    def has_permission(self, request, view):
        access_id = view.kwargs.get('access_id')
        if access_id:
            try:
                access = DocumentAccess.objects.select_related("document").get(id=access_id)
                return access.document.admin == request.user
            except DocumentAccess.DoesNotExist:
                return False

        # If no access_id in URL, fall back to True and rely on object-level check
        return True


class IsCommentOwner(BasePermission):
    """
    Checks if the user is the owner of a Comment.
    Supports:
    - Object-level permissions for Comment instances
    """

    def has_object_permission(self, request, view, obj):
        if isinstance(obj, Comment):
            return obj.user == request.user

        return False