import json

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.exceptions import DenyConnection
from django.template.defaulttags import ifchanged

from notification.serializers import NotificationSerializer
from utils.ws_groups import generate_group_name_from_user_id
from django.contrib.auth import get_user_model

from notification.models import Notification

User = get_user_model()

class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Check user authentication
        await self.check_user()

        # check if the user_id in the URL matches the authenticated user
        if self.scope["user"].id != int(self.scope["url_route"]["kwargs"]["user_id"]) :
            await self.accept()
            await self.send(json.dumps({
                "error": "unauthorized",
                "message": "User ID does not match authenticated user"
            }))
            await self.close(code=4002)
            raise DenyConnection()

        # now we have authentication suer and can access user information by scope["user"]
        user = self.scope["user"]
        self.user_group_name = generate_group_name_from_user_id(user.id)

        await self.accept()

        # Add user to their notification group
        await self.channel_layer.group_add(
            self.user_group_name,
            self.channel_name
        )

        await self.send(text_data=json.dumps({
            "type": "CONNECTED",
            "message": "Connected to user notification channel"
        }))


    async def check_user(self):
        if "user" not in self.scope or self.scope["user"] is None:
            await self.accept()  # Accept to send the error message
            await self.send(json.dumps({
                "error": "unauthorized",
                "message": "User is not logged in"
            }))
            await self.close(code=4001)
            raise DenyConnection()
    async def disconnect(self, close_code):
        if hasattr(self, "user_group_name"):
            await self.channel_layer.group_discard(
                self.user_group_name,
                self.channel_name
            )
        await self.close()

    # FUNCTION TO SEND NOTIFICATIONS TO THE USER
    async def send_notification(self, event):
        # Basic data
        message = event.get("message", "")
        notification_type = event.get("type", "info")
        recipient_id = self.scope["user"].id

        # Save notification in DB
        notification = await self.create_notification(recipient_id, message, notification_type)

        # Build dynamic payload
        payload = {
                "type": "notification",
                "payload": NotificationSerializer(notification).data,
        }

        # Optional extras

        if "doc_id" in event:
            payload["doc_id"] = event["doc_id"]
        if "revoked_access" in event:
            payload["revoked_access"] = event["revoked_access"]
        if "approved_access" in event:
            payload["approved_access"] = event["approved_access"]
        if "access_obj" in event:
            payload["access_obj"] = event["access_obj"]

        await self.send(text_data=json.dumps(payload))

    @sync_to_async
    def create_notification(self, recipient_id, message, notification_type):
        recipient = User.objects.get(id=recipient_id)
        return Notification.objects.create(
            recipient=recipient,
            message=message,
            type=notification_type
        )
