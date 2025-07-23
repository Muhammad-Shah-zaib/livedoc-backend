from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import get_user_model
from django.contrib.auth.models import update_last_login
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from rest_framework_simplejwt.tokens import RefreshToken
from django.conf import settings

User = get_user_model()

class GoogleLoginAPIView(APIView):
    def post(self, request):
        token = request.data.get("token")
        if not token:
            return Response({"message": "Token is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user_info = id_token.verify_oauth2_token(
                token,
                google_requests.Request(),
                settings.GOOGLE_OAUTH2_CLIENT_ID
            )


            email = user_info['email']
            first_name = user_info.get('given_name', '')
            last_name = user_info.get('family_name', '')
            email_verified = user_info.get('email_verified', False)

            user, created = User.objects.get_or_create(email=email, defaults={
                'first_name': first_name,
                'last_name': last_name,
                'is_email_verified': email_verified,
                'is_oauth_verified': True
            })

            if not created:
                updated = False
                if not user.is_oauth_verified:
                    user.is_oauth_verified = True
                    updated = True
                if email_verified and not user.is_email_verified:
                    user.is_email_verified = True
                    updated = True
                if updated:
                    user.save()

            refresh = RefreshToken.for_user(user)

            # Update last login time
            update_last_login(None, user)  # type: ignore
            
            response = Response({
                "detail": "Login successful",
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "is_oauth_verified": user.is_oauth_verified,
                    "is_active": user.is_active,
                }
            }, status=200)
            response.set_cookie("access_token", str(refresh.access_token), httponly=True, secure=True, samesite="None")
            response.set_cookie("refresh_token", str(refresh), httponly=True, secure=True, samesite="None")
            return response

        except ValueError:
            return Response({"message": "Invalid or expired token"}, status=status.HTTP_401_UNAUTHORIZED)
