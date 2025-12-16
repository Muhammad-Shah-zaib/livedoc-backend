from django.contrib.auth import get_user_model
from django.contrib.auth.models import update_last_login
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from user_auth.serializers import UserSerializer, UserUpdateSerializer

User = get_user_model()

class RegisterApiView(APIView):
    def post(self, request, *args, **kwargs):
        serializer = UserSerializer(data=request.data)

        if serializer.is_valid():
            user = serializer.save()

            refresh = RefreshToken.for_user(user)
            access_token = str(refresh.access_token)
            refresh_token = str(refresh)

            response = Response({
                "message": "User registered successfully.",
                "user": UserSerializer(user).data,
            }, status=status.HTTP_201_CREATED)

            response.set_cookie(
                key='access_token',
                value=access_token,
                httponly=True,
                secure=True,
                samesite='None',
                max_age=60 * 60 * 24 * 100,
            )

            response.set_cookie(
                key='refresh_token',
                value=refresh_token,
                httponly=True,
                secure=True,
                samesite='None',
                max_age=60 * 60 * 24 * 100,
            )

            return response

        return Response({
            "message": "Invalid data",
            "errors": serializer.errors,
        }, status=status.HTTP_400_BAD_REQUEST)

class LoginAPIView(APIView):
    def post(self, request):
        email = request.data.get("email", "").strip().lower()
        password = request.data.get("password")

        if not email or not password:
            return Response({"message": "Email and password are required."},
                            status=status.HTTP_400_BAD_REQUEST)

        existing_user = User.objects.filter(email=email).first()
        
        if not existing_user:
            return Response({"message": "Invalid email or password."},
                            status=status.HTTP_401_UNAUTHORIZED)
        
        if existing_user.is_oauth_verified and not existing_user.check_password(password):
            return Response({
                "message": "This account was created using a third-party login (e.g., Google). Please use the appropriate login method.",
                "is_oauth_verified": True
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not existing_user.check_password(password):
            return Response({"message": "Invalid email or password."},
                            status=status.HTTP_401_UNAUTHORIZED)
        
        if not existing_user.is_active:
            return Response({"message": "Account is inactive. Please contact support."},
                            status=status.HTTP_403_FORBIDDEN)

        update_last_login(None, existing_user)

        refresh = RefreshToken.for_user(existing_user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)

        response = Response({
            "message": "Login successful",
            "user": UserSerializer(existing_user).data,
        }, status=status.HTTP_200_OK)

        response.set_cookie(
            key='access_token',
            value=access_token,
            httponly=True,
            secure=True,
            samesite='None',
            max_age=60 * 60 * 24 * 100,
        )

        response.set_cookie(
            key='refresh_token',
            value=refresh_token,
            httponly=True,
            secure=True,
            samesite='None',
            max_age=60 * 60 * 24 * 100,
        )

        return response

class LogoutAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        response = Response({"success": True}, status=status.HTTP_200_OK)

        response.delete_cookie(
            key='access_token',
            samesite='None',
        )

        response.delete_cookie(
            key='refresh_token',
            samesite='None',
        )

        return response

class UpdateProfileView(APIView):
    def patch(self, request):
        user = request.user
        serializer = UserUpdateSerializer(user, data=request.data, partial=True)

        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Profile updated successfully.", "user": serializer.data},
                            status=status.HTTP_200_OK)

        return Response({"message": "Invalid data", "errors": serializer.errors},
                        status=status.HTTP_400_BAD_REQUEST)