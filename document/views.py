from django.utils import timezone
from rest_framework.generics import ListCreateAPIView, UpdateAPIView

from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .models import Document, DocumentAccess, Comment
from .permissions import IsAdminOfDocument, IsCommentOwner
from .serializers import DocumentSerializer, CommentSerializer
from utils.ws_groups import generate_group_name_from_user_id
from utils.db_helper import get_document_or_404, get_document_access_or_404


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
        document = get_document_or_404(document_id)

        if document.admin == request.user:
            return Response({"detail": "You are the admin of this document."}, status=status.HTTP_400_BAD_REQUEST)

        if document.accesses.filter(user=request.user, access_requested=True).exists():
            return Response({"detail": "Access request already sent."}, status=status.HTTP_400_BAD_REQUEST)

        if not document.is_live:
            return Response({"detail": "Document is not live."}, status=status.HTTP_400_BAD_REQUEST)

        # Create or update the access request
        access_obj, created = DocumentAccess.objects.update_or_create(
            document=document,
            user=request.user,
            defaults={
                "access_requested": True,
                "request_at": timezone.now()
            }
        )

        # admin group name to send notification
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
    permission_classes = [IsAuthenticated, IsAdminOfDocument]

    def patch(self, request, access_id):
        access_obj = get_document_access_or_404(access_id)

        # ✅ Check if already approved
        if access_obj.access_approved:
            return Response({"detail": "Access is already approved."}, status=status.HTTP_200_OK)

        # ✅ Check if access was even requested
        if not access_obj.access_requested:
            return Response({"detail": "Access has not been requested yet."}, status=status.HTTP_400_BAD_REQUEST)

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
        access_obj = get_document_access_or_404(access_id)

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

from rest_framework.exceptions import NotFound

class CommentListCreateView(ListCreateAPIView):
    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        document_id = self.kwargs["document_id"]
        return Comment.objects.filter(document_id=document_id).order_by("-id")

    def perform_create(self, serializer):
        document_id = self.kwargs["document_id"]
        document = get_document_or_404(document_id)

        comment = serializer.save(user=self.request.user, document=document)

        # Broadcast if live
        if document.is_live:
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f"doc_{document.share_token}",
                {
                    "type": "broadcast.comment",
                    "action": "create",
                    "user": {
                        "email": self.request.user.email,
                        "first_name": self.request.user.first_name,
                        "last_name": self.request.user.last_name,
                    },
                    "content": comment.content,
                    "commented_at": comment.commented_at.isoformat(),
                    "updated_at": comment.updated_at.isoformat(),
                    "id": comment.id
                }
            )


class CommentUpdateView(UpdateAPIView):
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticated, IsCommentOwner]

    def perform_update(self, serializer):
        comment = serializer.save()
        document = comment.document

        # Broadcast if live
        if document.is_live:
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f"doc_{document.share_token}",
                {
                    "type": "broadcast.comment",
                    "action": "update",
                    "user": {
                        "email": comment.user.email,
                        "first_name": comment.user.first_name,
                        "last_name": comment.user.last_name,
                    },
                    "content": comment.content,
                    "commented_at": comment.commented_at.isoformat(),
                    "updated_at": comment.updated_at.isoformat(),
                    "id": comment.id
                }
            )