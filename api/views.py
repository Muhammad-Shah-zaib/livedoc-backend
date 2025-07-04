from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from user_auth.auth import CookieJwtAuthentication

@api_view(['GET'])
def ping(request):
    """
    A simple view to check if the server is running.
    """
    return Response({"message": "Server is running."})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def test_token(request):
    """
    A simple view to test if the access token (from cookie or header) is working.
    Requires the user to be authenticated.
    """
    user = request.user
    return Response({
        "message": "Access token is valid.",
        "user_id": user.id,
        "email": user.email,
    })