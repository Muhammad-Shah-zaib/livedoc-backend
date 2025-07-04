import json
from channels.exceptions import DenyConnection
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from document.models import Document, DocumentAccess


class DocumentLiveConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        self.share_token = self.scope["url_route"]["kwargs"]["share_token"]
        self.group_name = f"doc_{self.share_token}"

        # Auth check
        if not self.user or not self.user.is_authenticated:
            await self.accept()
            await self.send(json.dumps({
                "type": "error",
                "message": "User is not logged in"
            }))
            await self.close(code=4001)
            raise DenyConnection()

        # Fetch document
        self.document = await sync_to_async(Document.objects.get)(share_token=self.share_token)

        await self.accept()
        await self.channel_layer.group_add(self.group_name, self.channel_name)

        await self.send(text_data=json.dumps({
            "type": "connection",
            "message": "Connected to live document channel."
        }))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        message_type = data.get("type")

        print(f"USER -> {self.user}")

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
            if await self.is_user_admin():
                await self.set_document_live()
            else:
                await self.send(text_data=json.dumps({
                    "type": "error",
                    "message": "Only the admin can set the document live."
                }))

    async def document_update(self, event):
        await self.send(text_data=json.dumps({
            "type": "document_update",
            "content": event["content"]
        }))

    async def set_document_live(self):
        self.document.is_live = True
        await sync_to_async(self.document.save)()
        await self.send(text_data=json.dumps({
            "type": "document_live",
            "message": "Document is now live."
        }))

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
