import json
from redis.asyncio import Redis
from channels.exceptions import DenyConnection
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from document.models import Document, DocumentAccess
from utils.redis_key_generator import get_key_for_document
import y_py as Y
from collections import defaultdict


from django.conf import settings

DOC_MAP = defaultdict(lambda: Y.YDoc())


class DocumentLiveConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Auth check
        await self.check_user()

        self.user = self.scope['user']
        self.share_token = self.scope["url_route"]["kwargs"]["share_token"]
        self.group_name = f"doc_{self.share_token}"

        # Fetch document
        self.document = await sync_to_async(Document.objects.get)(share_token=self.share_token)
        self.is_admin = await self.is_user_admin()
        self.redis = await Redis.from_url(settings.REDIS_URL)

        if not self.document.is_live and not self.is_admin:
            await self.accept()
            await self.send(json.dumps({
                "type": "error",
                "message": "Document is not live."
            }))
            await self.close(code=4002)
            raise DenyConnection()

        # Manually track presence
        # Add user ID to the presence set
        self.redis_document_key = get_key_for_document(self.document.share_token)
        await self.redis.sadd(self.redis_document_key, str(self.user.id))

        # Add user metadata to a hash
        await self.redis.hset(
            f"doc:{self.share_token}:user:{self.user.id}",
            mapping={
                "first_name": self.user.first_name,
                "last_name": self.user.last_name,
                "email": self.user.email
            }
        )

        await self.accept()
        await self.channel_layer.group_add(self.group_name, self.channel_name)

        await self.send(text_data=json.dumps({
            "type": "connection",
            "message": "Connected to live document channel.",
            "content": self.document.content,
            "document": {
                "id": str(self.document.id),
                "name": self.document.name,
                "content": self.document.content,
                "is_live": self.document.is_live,
                "created_at": self.document.created_at.isoformat(),
                "share_token": str(self.document.share_token),
            }
        }))

    async def disconnect(self, close_code):
        # Only try to clean up Redis if user and share_token are set
        if hasattr(self, "user") and hasattr(self, "share_token") and hasattr(self, "redis"):
            try:
                await self.redis.srem(f"doc:{self.share_token}:users", str(self.user.id))
                await self.redis.delete(f"doc:{self.share_token}:user:{self.user.id}")

            except Exception as e:
                # Log error if needed
                print(f"Redis cleanup error: {e}")

        if hasattr(self, "channel_layer") and hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data= None, bytes_data = None):
        if text_data is not None:
            await self.receive_text_data(text_data)
        if bytes_data is not None:
            await self.receive_bytes_data(bytes_data)

    async def receive_text_data(self, text_data):
        data = json.loads(text_data)
        message_type = data.get("type")


        if message_type == "update_content":
            content = data.get("content", "")
            allowed = await self.has_edit_permission()
            if not allowed:
                await self.send(text_data=json.dumps({
                    "type": "error",
                    "message": "You do not have permission to edit this document."
                }))
                return

            await self.update_document_content(content)
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "document.update",
                    "content": content
                }
            )

        elif message_type == "set_live":
            if self.is_admin:
                new_status = data.get("status", True)
                if (self.document.is_live == new_status):
                    await self.send(text_data=json.dumps({
                        "type": "error",
                        "message": f"Document is already {'live' if new_status else 'not live'}."
                    }))
                    return
                await self.set_document_live(status=new_status)
            else:
                await self.send(text_data=json.dumps({
                    "type": "error",
                    "message": "Only the admin can set the document live."
                }))

    async def receive_bytes_data(self, bytes_data):
        doc = DOC_MAP[self.share_token]

        try:
            msg_type = bytes_data[0]
            data = bytes_data[1:]

            if msg_type == 0:
                update = Y.encode_state_as_update(doc, data)
                await self.send(bytes_data=b"\x01" + update)

            elif msg_type == 1:
                Y.apply_update(doc, data)
                await self.channel_layer.group_send(
                    self.group_name,
                    {"type": "document.yjs_update", "bytes": bytes_data}
                )
        except Exception as e:
            print(f"Error processing bytes_data: {e}")

    async def document_yjs_update(self, event):
        await self.send(bytes_data=event["bytes"])  # Send raw Yjs update

    async def document_update(self, event):
        await self.send(text_data=json.dumps({
            "type": "document_update",
            "content": event["content"]
        }))

    async def set_document_live(self, status=True):
        self.document.is_live = status
        await sync_to_async(self.document.save)()

        if not status:
            # Broadcast force disconnect to all users in the group
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "force.disconnect",
                    "message": "Document is no longer live. Disconnecting."
                }
            )

        await self.send(text_data=json.dumps({
            "type": "document_live",
            "message": f"Document is now {'live' if status else 'not live'}."
        }))

    async def broadcast_comment(self, event):
        await self.send(text_data=json.dumps({
            "type": "new_comment" if event["action"] == "create" else "update_comment",
            "id": event["id"],
            "user": event["user"],
            "content": event["content"],
            "commented_at": event["commented_at"]
        }))

    async def force_disconnect(self, event):
        if not self.is_admin:
            await self.send(text_data=json.dumps({
                "type": "force_disconnect",
                "message": event["message"]
            }))
            await self.close()

    @sync_to_async
    def update_document_content(self, content):
        self.document.content = content
        self.document.save()

    @sync_to_async
    def has_edit_permission(self):
        if self.document.admin_id == self.user.id:
            return True
        return DocumentAccess.objects.filter(
            document=self.document,
            user=self.user,
            can_edit=True,
            access_approved=True
        ).exists()

    @sync_to_async
    def is_user_admin(self):
        return self.document.admin_id == self.user.id

    async def check_user(self):
        if "user" not in self.scope or self.scope["user"] is None:
            await self.accept()  # Accept to send the error message
            await self.send(json.dumps({
                "error": "unauthorized",
                "message": "User is not logged in"
            }))
            await self.close(code=4001)
            raise DenyConnection()
