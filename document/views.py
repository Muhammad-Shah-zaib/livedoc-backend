from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .models import Document, DocumentAccess
from .permissions import IsAdminOfDocument
from .serializers import DocumentSerializer
from utils.ws_groups import generate_group_name_from_user_id


# Create your views here.


class DocumentViewSet(ModelViewSet):
    serializer_class = DocumentSerializer
    permission_classes = [IsAuthenticated, IsAdminOfDocument]

    def get_queryset(self):
        return Document.objects.filter(admin=self.request.user)

    def perform_create(self, serializer):
        serializer.save(admin=self.request.user)


class RequestAccessAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, document_id):
        try:
            document = Document.objects.get(id=document_id)
        except Document.DoesNotExist:
            return Response({"detail": "Document not found."}, status=status.HTTP_404_NOT_FOUND)

        if document.admin == request.user:
            return Response({"detail": "You are the admin of this document."}, status=status.HTTP_400_BAD_REQUEST)

        access_obj, created = DocumentAccess.objects.update_or_create(
            document=document,
            user=request.user,
            defaults={
                "access_requested": True,
                "request_at": timezone.now()
            }
        )

        # Use secure admin group
        admin_group = generate_group_name_from_user_id(document.admin.id)

        # Send WebSocket notification to admin-only group
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            admin_group,
            {
                "type": "send.notification",
                "message": f"{request.user.first_name} {request.user.last_name} has requested access to '{document.name}'."
            }
        )

        return Response({"detail": "Access request sent."}, status=status.HTTP_200_OK)

class ApproveAccessAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, access_id):
        try:
            access_obj = DocumentAccess.objects.select_related("document", "user").get(id=access_id)
        except DocumentAccess.DoesNotExist:
            return Response({"detail": "Access request not found."}, status=status.HTTP_404_NOT_FOUND)

        # Ensure only the admin can approve access
        if access_obj.document.admin != request.user:
            return Response({"detail": "You are not the admin of this document."}, status=status.HTTP_403_FORBIDDEN)

        # Approve access
        access_obj.access_approved = True
        access_obj.can_edit = True
        access_obj.approved_at = timezone.now()
        access_obj.save()

        # Notify the user via WebSocket
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            generate_group_name_from_user_id(access_obj.user.id),
            {
                "type": "send.notification",
                "message": f"Your access to '{access_obj.document.name}' has been granted by admin {request.user.first_name} {request.user.last_name}."
            }
        )

        return Response({"detail": "Access granted."}, status=status.HTTP_200_OK)


class RevokeAccessAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOfDocument]

    def put(self, request, access_id):
        try:
            access_obj = DocumentAccess.objects.select_related("document", "user").get(id=access_id)
        except DocumentAccess.DoesNotExist:
            return Response({"detail": "Access record not found."}, status=status.HTTP_404_NOT_FOUND)

        # Only the document admin can revoke access
        if access_obj.document.admin != request.user:
            return Response({"detail": "You are not the admin of this document."}, status=status.HTTP_403_FORBIDDEN)

        # If already revoked
        if not access_obj.access_approved:
            return Response({"detail": "Access is already revoked."}, status=status.HTTP_400_BAD_REQUEST)

        # Revoke access
        access_obj.access_approved = False
        access_obj.can_edit = False
        access_obj.save()

        # Notify the user via WebSocket
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            generate_group_name_from_user_id(access_obj.user.id),
            {
                "type": "send.notification",
                "message": f"Your access to '{access_obj.document.name}' has been revoked by the admin."
            }
        )

        return Response({"detail": "Access revoked."}, status=status.HTTP_200_OK)
