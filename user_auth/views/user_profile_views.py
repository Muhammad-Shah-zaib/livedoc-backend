# user_profile_views.py
from django.contrib.auth import get_user_model
from rest_framework.generics import UpdateAPIView
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from redis import Redis
from django.conf import settings

from user_auth.models import CustomUser
from user_auth.serializers import UserUpdateSerializer, PasswordChangeSerializer, UserSerializer, UserMetaSerializer, LiveUsersSerializer
from utils.redis_key_generator import get_key_for_document

User = get_user_model();
# api view to get user details
class UserProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        serializer = UserSerializer(user)
        return Response(serializer.data, status=status.HTTP_200_OK)

# api to get all the users
class GetAllUsersView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        users = CustomUser.objects.filter(is_active=True)
        serializer = UserSerializer(users, many=True)
        return Response(
            {
                "users": serializer.data,
                "detail": "Users fetched successfully.",
            },
            status=status.HTTP_200_OK,
        )

class GetUserByEmailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        email = request.query_params.get('email')
        if not email:
            return Response(
                {"detail": "Email query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {"detail": "User with this email does not exist."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = UserSerializer(user)
        return Response(
            {
                "user": serializer.data,
                "detail": "User fetched successfully.",
            },
            status=status.HTTP_200_OK,
        )


class UserInfoUpdateView(UpdateAPIView):
    queryset = CustomUser.objects.all()
    serializer_class = UserUpdateSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

class PasswordChangeView(UpdateAPIView):
    serializer_class = PasswordChangeSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": "Password updated successfully."}, status=status.HTTP_200_OK)

# views.py
class GetUsersFromEmailListView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        emails = request.data.get('emails', [])
        if not emails:
            return Response(
                {"detail": "Email list is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        users = CustomUser.objects.filter(email__in=emails, is_active=True)
        serializer = UserMetaSerializer(users, many=True)
        return Response(
            {
                "users": serializer.data,
                "detail": "Users fetched successfully.",
            },
            status=status.HTTP_200_OK,
        )

class GetLiveUsersEmailsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        share_token = request.query_params.get("share_token")
        if not share_token:
            return Response({"detail": "Missing 'share_token' query parameter."}, status=400)

        redis = Redis.from_url(settings.REDIS_URL)
        users = []

        user_ids = redis.smembers(get_key_for_document(share_token))

        for user_id in user_ids:
            key = f"doc:{share_token}:user:{user_id.decode()}"
            user_data = redis.hgetall(key)

            # Decode all fields
            user = {
                "id": int(user_id),
                "first_name": user_data.get(b"first_name", b"").decode(),
                "last_name": user_data.get(b"last_name", b"").decode(),
                "email": user_data.get(b"email", b"").decode(),
                "isOauthVerified": user_data.get(b"isOauthVerified", b"false").decode().lower() == "true",
                "isActive": user_data.get(b"isActive", b"false").decode().lower() == "true",
            }

            users.append(user)

        serializer = LiveUsersSerializer({"users": users})
        return Response(serializer.data)

