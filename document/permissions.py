from rest_framework.permissions import BasePermission


class IsAdminOfDocument(BasePermission):
    """
    Custom permission class to check if the user is an admin of the document.
    """
    def has_object_permission(self, request, view, obj):
        return  obj.admin == request.user