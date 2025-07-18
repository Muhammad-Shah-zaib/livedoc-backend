# user_profile_views.py
from django.contrib.auth import get_user_model
from django.core.serializers import get_serializer
from rest_framework.generics import UpdateAPIView
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from user_auth.models import CustomUser
from user_auth.serializers import UserUpdateSerializer, PasswordChangeSerializer, UserSerializer


User = get_user_model();
# api view to get user details
class UserProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        serializer = UserSerializer(user)
        return Response(serializer.data, status=status.HTTP_200_OK)

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
