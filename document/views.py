from django.contrib.auth import get_user_model
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.generics import ListCreateAPIView, UpdateAPIView
from rest_framework.decorators import action

from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .models import Document, DocumentAccess, Comment
from .permissions import IsAdminOfDocument, IsCommentOwner
from .serializers import DocumentSerializer, CommentSerializer, DocumentAccessSerializer
from utils.ws_groups import generate_group_name_from_user_id
from utils.db_helper import get_document_or_404, get_document_access_or_404, get_document_by_share_token_or_404

import uuid

User = get_user_model()

class DocumentAccessViewSet(ModelViewSet):
    serializer_class = DocumentAccessSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['document', 'access_requested', 'access_approved']

    def get_queryset(self):
        return DocumentAccess.objects.filter(document__admin=self.request.user)

    @action(detail=False, methods=["post"], url_path="grant-access")
    def grant_access(self, request):
        user_id = request.data.get("user_id")
        document_id = request.data.get("document_id")
        can_edit = request.data.get("can_edit", True)

        if not user_id or not document_id:
            return Response(
                {"detail": "Both fields are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.get(id=user_id)
            document = Document.objects.get(id=document_id, admin=request.user)
        except User.DoesNotExist:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)
        except Document.DoesNotExist:
            return Response({"detail": "Document not found or you're not the admin."}, status=status.HTTP_404_NOT_FOUND)

        access_obj, created = DocumentAccess.objects.update_or_create(
            document=document,
            user=user,
            defaults={
                "can_edit": can_edit,
                "access_requested": False,
                "access_approved": True,
                "approved_at": timezone.now(),
            },
        )

        # send notification
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            generate_group_name_from_user_id(access_obj.user.id),
            {
                "type": "send.notification",
                "message": f"Your access to '{access_obj.document.name}' has been granted by admin {request.user.first_name} {request.user.last_name}."
            }
        )

        serializer = self.get_serializer(access_obj, context={"request": request})
        return Response(
            {
                "detail": "Access granted successfully.",
                "access": serializer.data,
                "created": created,
            },
            status=status.HTTP_200_OK,
        )

class DocumentViewSet(ModelViewSet):
    serializer_class = DocumentSerializer
    permission_classes = [IsAuthenticated, IsAdminOfDocument]

    def get_queryset(self):
        return Document.objects.filter(admin=self.request.user)

    def perform_create(self, serializer):
        import secrets
        share_token = uuid.uuid4()
        serializer.save(admin=self.request.user, share_token=share_token)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        self.perform_destroy(instance)
        return Response({
            "detail": "Document deleted successfully.",
            "deleted_access": serializer.data
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="by-token/(?P<token>[^/.]+)", permission_classes=[])
    def get_by_share_token(self, request, token=None):
        document = get_document_by_share_token_or_404(share_token=token)
        serializer = self.get_serializer(document)
        return Response(serializer.data, status=status.HTTP_200_OK)

class RequestAccessAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, share_token):
        document = get_document_by_share_token_or_404(share_token)

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

        return Response({
            "detail": "Access granted.",
            "access": DocumentAccessSerializer(access_obj).data
        }, status=status.HTTP_200_OK)

class RevokeAccessAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOfDocument]

    def patch(self, request, access_id):
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

        return Response({
            "detail": "Access granted.",
            "access": DocumentAccessSerializer(access_obj).data
        }, status=status.HTTP_200_OK)

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

class LiveDocumentAccessView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, share_token, *args, **kwargs):
        if not share_token:
            return Response({"detail": "Missing share_token", "status": "CAN_NOT_CONNECT"}, status=status.HTTP_400_BAD_REQUEST)

        document = get_document_by_share_token_or_404(share_token)

        if document.admin == request.user or document.is_live:
            return Response({"detail": "Access granted", "status": "CAN_CONNECT"}, status=status.HTTP_200_OK)
        else:
            return Response({"detail": "Document is not live", "status": "CAN_NOT_CONNECT"}, status=status.HTTP_403_FORBIDDEN)