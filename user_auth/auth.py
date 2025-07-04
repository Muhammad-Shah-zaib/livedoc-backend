# for http
from django.contrib.auth import get_user_model
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken, TokenError

# for channels
from django.db import close_old_connections
from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async

User = get_user_model()
class CookieJwtAuthentication(BaseAuthentication):
    def authenticate(self, request):
        access_token = request._request.COOKIES.get('access_token')
        refresh_token = request._request.COOKIES.get('refresh_token')

        # 👇 Don't raise — just return None if no access token
        if not access_token:
            return None

        try:
            access = AccessToken(access_token)
            user = User.objects.get(id=access['user_id'])

            if not user.is_active:
                raise AuthenticationFailed('User is inactive.')

            return user, None

        except TokenError:
            # 👇 If no refresh token, just return None (user stays unauthenticated)
            if not refresh_token:
                return None

            try:
                refresh = RefreshToken(refresh_token)
                user = User.objects.get(id=refresh['user_id'])

                if not user.is_active:
                    raise AuthenticationFailed('User is inactive.')

                # Generate a new access token
                new_access_token = refresh.access_token
                request.new_access_token = str(new_access_token)

                return user, None

            except TokenError:
                return None

class CookieAuthMiddlewareStack(BaseMiddleware):

    def __init__(self, app):
        super().__init__(app)
        self.app = app

    async def __call__(self, scope, receive, send):
        headers = dict(scope["headers"])
        cookies = {}

        # --- Parse Cookies ---
        if b"cookie" in headers:
            cookie_header = headers[b"cookie"].decode()
            for part in cookie_header.split(";"):
                if "=" in part:
                    key, value = part.strip().split("=", 1)
                    cookies[key] = value

        # --- Try token from cookies ---
        access_token = cookies.get("access_token")
        refresh_token = cookies.get("refresh_token")

        # --- TEMPORARY: Try token from headers if not found in cookies ---
        if not access_token:
            access_token = self._get_header_token(headers, b'access-token')

        if not refresh_token:
            refresh_token = self._get_header_token(headers, b'refresh-token')
        scope["user"] = None



        user = None
        if access_token:
            user = await get_user_from_token(access_token)

        if not user and refresh_token:
            user = await get_user_from_refresh_token(refresh_token)

        if user:
            scope["user"] = user

        close_old_connections()
        return await super().__call__(scope, receive, send)

    def _get_header_token(self, headers, header_name):
        """
        Helper to extract token from custom headers (Postman testing)
        E.g., 'access-token: <token>' or 'refresh-token: <token>'
        """
        if header_name in headers:
            return headers[header_name].decode().strip()
        return None


@database_sync_to_async
def get_user_from_token(token):
    try:
        access = AccessToken(token)
        user = User.objects.get(id=access["user_id"])
        if not user.is_active:
            return None
        return user
    except (TokenError, User.DoesNotExist):
        return None


@database_sync_to_async
def get_user_from_refresh_token(refresh_token):
    try:
        refresh = RefreshToken(refresh_token)
        user = User.objects.get(id=refresh["user_id"])
        if not user.is_active:
            return None
        return user
    except (TokenError, User.DoesNotExist):
        return None
