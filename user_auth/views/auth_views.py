from django.contrib.auth import get_user_model
from django.contrib.auth.models import update_last_login
from django.utils.http import urlsafe_base64_decode
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.tokens import default_token_generator
from utils.tokens import default_email_token_generator

from user_auth.email import send_verification_email, send_reset_password_email
from user_auth.serializers import UserSerializer, UserUpdateSerializer

User = get_user_model()

class RegisterApiView(APIView):
    def post(self, request, *args, **kwargs):
        serializer = UserSerializer(data=request.data)

        if serializer.is_valid():
            user = serializer.save()

            # OPTIONAL: deactivate user until email is verified
            user.is_active = False
            user.save()

            # send verification email
            send_verification_email(user)

            return Response({
                "message": "User registered successfully. Please verify your email.",
                "email_verification_required": True,
            }, status=status.HTTP_201_CREATED)

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

        # First check if user exists at all
        existing_user = User.objects.filter(email=email).first()
        
        if not existing_user:
            return Response({"message": "Invalid email or password."},
                            status=status.HTTP_401_UNAUTHORIZED)
        
        # Check if user was created via OAuth
        if existing_user.is_oauth_verified and not existing_user.check_password(password):
            return Response({
                "message": "This account was created using a third-party login (e.g., Google). Please use the appropriate login method.",
                "is_oauth_verified": True
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if the password is correct
        if not existing_user.check_password(password):
            return Response({"message": "Invalid email or password."},
                            status=status.HTTP_401_UNAUTHORIZED)
        
        # Check if user has verified their email
        if not existing_user.is_active:
            if not existing_user.is_email_verified:
                # Resend verification email
                send_verification_email(existing_user)
                return Response({
                    "message": "Please verify your email before logging in. A new verification email has been sent.",
                    "email_verification_required": True
                }, status=status.HTTP_403_FORBIDDEN)
            else:
                return Response({"message": "Account is inactive. Please contact support."},
                                status=status.HTTP_403_FORBIDDEN)

        update_last_login(None, existing_user)  # type: ignore

        refresh = RefreshToken.for_user(existing_user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)

        response = Response({
            "message": "Login successful",
            "user": UserSerializer(existing_user).data,
        }, status=status.HTTP_200_OK)

        # Set HttpOnly cookies
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

        # Delete access_token cookie
        response.delete_cookie(
            key='access_token',
            samesite='None',
        )

        # Delete refresh_token cookie
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

class VerifyEmailView(APIView):
    def get(self, request, uidb64, token):
        try:
            uid = urlsafe_base64_decode(uidb64).decode()
            user = User.objects.get(pk=uid)

            if not default_email_token_generator.check_token(user, token):
                return Response({"message": "Invalid or expired token."},
                                status=status.HTTP_400_BAD_REQUEST)

            user.is_active = True
            user.is_email_verified = True
            user.save()

            return Response({"message": "Email verified successfully. You can now log in."},
                            status=status.HTTP_200_OK)

        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response({"message": "Invalid verification link."},
                            status=status.HTTP_400_BAD_REQUEST)

class ResetPasswordRequestView(APIView):
    def post(self, request):
        email = request.data.get("email").strip().lower()
        # normalize email input

        if not email:
            return Response({"message": "Email is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"message": "User with this email does not exist."}, status=status.HTTP_404_NOT_FOUND)

        # Send reset password email
        send_reset_password_email(user)

        return Response({"message": "Password reset link sent to your email."}, status=status.HTTP_200_OK)

class ResetPasswordConfirmView(APIView):
    def post(self, request, uidb64, token):
        try:
            uid = urlsafe_base64_decode(uidb64).decode()
            user = User.objects.get(pk=uid)

        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response({"message": "Invalid or expired link."}, status=status.HTTP_400_BAD_REQUEST)

        if not default_token_generator.check_token(user, token):
            return Response({"message": "Invalid or expired token."}, status=status.HTTP_400_BAD_REQUEST)

        password = request.data.get("password")
        password2 = request.data.get("confirm_password")

        if not password or not password2:
            return Response({"message": "Both password fields are required."}, status=status.HTTP_400_BAD_REQUEST)

        if password != password2:
            return Response({"message": "Passwords do not match."}, status=status.HTTP_400_BAD_REQUEST)

        if len(password) < 8:
            return Response({"message": "Password must be at least 8 characters long."}, status=status.HTTP_400_BAD_REQUEST)

        # Set and save new password
        user.set_password(password)
        user.save()

        return Response({"message": "Password reset successful."}, status=status.HTTP_200_OK)