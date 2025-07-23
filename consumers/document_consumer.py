import json
import asyncio
from redis.asyncio import Redis
from channels.exceptions import DenyConnection
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from document.models import Document
from utils.redis_key_generator import get_key_for_document
from django.conf import settings


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

        # Add user ID to Redis presence set
        await self.redis.sadd(self.redis_document_key, str(self.user.id))

        # Add full user metadata
        await self.redis.hset(
            f"doc:{self.share_token}:user:{self.user.id}",
            mapping={
                "id": str(self.user.id),
                "first_name": self.user.first_name,
                "last_name": self.user.last_name,
                "email": self.user.email
            }
        )

        await self.accept()
        await self.channel_layer.group_add(self.group_name, self.channel_name)

        # Broadcast user joined
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "user.joined",
                "user": {
                    "id": str(self.user.id),
                    "first_name": self.user.first_name,
                    "last_name": self.user.last_name,
                    "email": self.user.email
                }
            }
        )

        # Send updated member count
        await self.broadcast_member_count()

    async def disconnect(self, close_code):
        if hasattr(self, "user") and hasattr(self, "share_token") and hasattr(self, "redis"):
            try:
                await self.redis.srem(get_key_for_document(self.share_token), str(self.user.id))
                await self.redis.delete(f"doc:{self.share_token}:user:{self.user.id}")

                # Broadcast user left
                await self.channel_layer.group_send(
                    self.group_name,
                    {
                        "type": "user.left",
                        "user": {
                            "id": str(self.user.id),
                            "first_name": self.user.first_name,
                            "last_name": self.user.last_name,
                            "email": self.user.email
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
                "count": count,
            }
        )

    async def live_member_count(self, event):
        await self.send(text_data=json.dumps({
            "type": "live_members",
            "count": event["count"],
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

    @sync_to_async
    def is_user_admin(self):
        return self.document.admin_id == self.user.id

    async def check_user(self):
        if "user" not in self.scope or self.scope["user"] is None:
            await self.accept()
            await self.send(json.dumps({
                "error": "unauthorized",
                "message": "User is not logged in"
            }))
            await self.close(code=4001)
            raise DenyConnection()
