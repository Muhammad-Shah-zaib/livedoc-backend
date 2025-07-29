# liveblocks/views.py

import jwt
import datetime
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from django.conf import settings
from django.http import JsonResponse, HttpRequest
import logging

LIVEBLOCKS_SECRET_KEY = settings.LIVEBLOCKS_SECRET_KEY

logger = logging.getLogger(__name__)

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def liveblocks_auth(request: HttpRequest):
    logger.debug("liveblocks_auth called")
    logger.debug(f"Request user: {request.user}")
    logger.debug(f"Request data: {request.data}")

    user = request.user
    room_id = request.data.get("roomId")

    if not room_id:
        return JsonResponse({"error": "Missing roomId"}, status=400)

    room_key = f"liveblocks:{room_id}"

    payload = {
        "userId": str(user.id),
        "userInfo": {
            "name": f"{user.first_name} {user.last_name}",
            "color": "#7f63f4",
        },
        "permissions": {
            room_key: ["room:write"],
        },
        "iat": int(datetime.datetime.utcnow().timestamp()),
        "exp": int((datetime.datetime.utcnow() + datetime.timedelta(hours=2)).timestamp()),
    }

    token = jwt.encode(payload, settings.LIVEBLOCKS_SECRET_KEY, algorithm="HS256")
    if isinstance(token, bytes):
        token = token.decode("utf-8")

    logger.debug(f"Returning token: {token}")
    return JsonResponse({"token": token})
