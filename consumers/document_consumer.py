import json
import random
from redis.asyncio import Redis
from channels.exceptions import DenyConnection
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from document.models import Document, LiveDocumentUser, USER_COLORS
from utils.redis_key_generator import get_key_for_document
from django.conf import settings

from utils.ws_groups import generate_group_name_from_user_id


class DocumentLiveConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.check_user()

        self.user = self.scope['user']
        self.share_token = self.scope["url_route"]["kwargs"]["share_token"]
        self.group_name = f"doc_{self.share_token}"

        self.document = await sync_to_async(Document.objects.get)(share_token=self.share_token)
        self.is_admin = await self.is_user_admin()
        self.redis = await Redis.from_url(settings.REDIS_URL)
        self.redis_document_key = get_key_for_document(self.document.share_token)

        if not self.document.is_live and not self.is_admin:
            await self.accept()
            await self.send(json.dumps({
                "type": "error",
                "message": "Document is not live."
            }))
            await self.close(code=4002)
            raise DenyConnection()

        live_user = await self.add_user_to_live_document()

        # Add user ID to Redis presence set
        await self.redis.sadd(self.redis_document_key, str(self.user.id))

        # Add full user metadata
        await self.redis.hset(
            f"doc:{self.share_token}:user:{self.user.id}",
            mapping={
                "id": str(self.user.id),
                "first_name": self.user.first_name,
                "last_name": self.user.last_name,
                "email": self.user.email,
                "color": live_user.color
            }
        )

        await self.accept()
        await self.channel_layer.group_add(self.group_name, self.channel_name)

        # Send the list of all live users to the newly connected user
        await self.send_live_users_list()

        # Broadcast user joined to all users in the group
        await self._broadcast_user_joined(live_user)

        # Send updated member count
        await self.broadcast_member_count()

    async def disconnect(self, close_code):
        if hasattr(self, "user") and hasattr(self, "share_token") and hasattr(self, "redis"):
            # Mark user as offline in the database
            await self.mark_user_offline()
            try:
                await self.redis.srem(get_key_for_document(self.share_token), str(self.user.id))
                await self.redis.delete(f"doc:{self.share_token}:user:{self.user.id}")

                # Send live count directly to disconnecting user (required for updating states)
                disconnecting_user_id = self.user.id
                remaining_count = await self.redis.scard(self.redis_document_key)

                await self.channel_layer.group_send(
                    generate_group_name_from_user_id(disconnecting_user_id),
                    {
                        "type": "notify_live_member_count",
                        "doc_id": self.document.id,
                        "count": remaining_count,
                        "message": f"Live member count updated to {remaining_count}"
                    }
                )

                # Broadcast user left
                await self.channel_layer.group_send(
                    self.group_name,
                    {
                        "type": "user.left",
                        "user": {
                            "id": str(self.user.id),
                            "first_name": self.user.first_name,
                            "last_name": self.user.last_name,
                            "name": f"{self.user.first_name} {self.user.last_name}",
                            "email": self.user.email,
                            "is_online": False,
                        }
                    }
                )

                await self.broadcast_member_count()
            except Exception as e:
                print(f"Redis cleanup error: {e}")

        if hasattr(self, "channel_layer") and hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        if text_data:
            await self.receive_text_data(text_data)

    async def receive_text_data(self, text_data):
        data = json.loads(text_data)
        message_type = data.get("type")

        if message_type == "comment":
            comment_data = data.get("comment")
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "broadcast.comment",
                    "action": comment_data.get("action", "create"),
                    "id": comment_data["id"],
                    "user": comment_data["user"],
                    "content": comment_data["content"],
                    "commented_at": comment_data["commented_at"]
                }
            )

    async def broadcast_comment(self, event):
        await self.send(text_data=json.dumps({
            "type": "new_comment" if event["action"] == "create" else "update_comment",
            "id": event["id"],
            "user": event["user"],
            "content": event["content"],
            "commented_at": event["commented_at"]
        }))

    async def broadcast_member_count(self):
        count = await self.redis.scard(self.redis_document_key)
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "live.member.count",
                "doc_id": self.document.id,
                "count": count,
            }
        )

        # Notify all present users individually
        user_ids = await self.redis.smembers(self.redis_document_key)
        for user_id_bytes in user_ids:
            user_id = int(user_id_bytes.decode("utf-8"))

            await self.channel_layer.group_send(
                generate_group_name_from_user_id(user_id),  # Send to NotificationConsumer
                {
                    "type": "notify.live.member.count",
                    "message": f"Live member count updated to {count}",
                    "doc_id": self.document.id,
                    "count": count,
                }
            )

    async def live_member_count(self, event):
        await self.send(text_data=json.dumps({
            "type": "live_members",
            "doc_id": self.document.id,
            "count": event["count"],
        }))

    async def send_live_users_list(self):
        live_users = await self.get_all_live_users()
        await self.send(text_data=json.dumps({
            "type": "live_users_list",
            "users": list(live_users)
        }))

    async def user_joined(self, event):
        await self.send(text_data=json.dumps({
            "type": "user_joined",
            "user": event["user"]
        }))

    async def user_left(self, event):
        await self.send(text_data=json.dumps({
            "type": "user_left",
            "user": event["user"]
        }))

    async def _broadcast_user_joined(self, live_user):
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "user.joined",
                "user": {
                    "id": str(self.user.id),
                    "name": f"{self.user.first_name} {self.user.last_name}",
                    "email": self.user.email,
                    "color": live_user.color,
                    "is_online": True,
                }
            }
        )

    @sync_to_async()
    def mark_user_offline(self):
        try:
            live_user = LiveDocumentUser.objects.get(document=self.document, user=self.user)
            live_user.is_online = False
            live_user.save()
        except LiveDocumentUser.DoesNotExist:
            pass

    @sync_to_async
    def add_user_to_live_document(self):
        live_user, created = LiveDocumentUser.objects.get_or_create(
            document=self.document,
            user=self.user,
            defaults={
                'email': self.user.email,
                'name': f'{self.user.first_name} {self.user.last_name}' or self.user.email,
                'color': random.choice(USER_COLORS),
                'is_online': True,
            }
        )

        if not created:
            # Update the existing record
            live_user.email = self.user.email
            live_user.name = f'{self.user.first_name} {self.user.last_name}' or self.user.email
            live_user.is_online = True  # or False, depending on your logic
            # Optionally update color if you want
            # live_user.color = random.choice(USER_COLORS)
            live_user.save()

        return live_user

    @sync_to_async
    def _remove_user_from_live_document(self):
        LiveDocumentUser.objects.filter(document=self.document, user=self.user).delete()


    @sync_to_async
    def is_user_admin(self):
        return self.document.admin_id == self.user.id

    @sync_to_async
    def get_all_live_users(self):
        users = LiveDocumentUser.objects.filter(document=self.document).values(
            "user_id", "name", "email", "color"
        )
        # formatting for frontend
        formatted_users = [
            {
                "userId": user["user_id"],
                "name": user["name"],
                "email": user["email"],
                "color": user["color"]
            }
            for user in users
        ]

        return list(formatted_users)

    async def check_user(self):
        if "user" not in self.scope or self.scope["user"] is None:
            await self.accept()
            await self.send(json.dumps({
                "error": "unauthorized",
                "message": "User is not logged in"
            }))
            await self.close(code=4001)
            raise DenyConnection()
