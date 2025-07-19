from asgiref.sync import sync_to_async
from pycrdt.websocket.django_channels_consumer import YjsConsumer

from document.models import Document

class YjsDocumentConsumer(YjsConsumer):
    async def connect(self):
        # Check the user in self.scope["user"]
        if "user" in self.scope and self.scope["user"] is None:
            await self.close()
            return

        # so get the document here
        document = await self.get_document()

        if not document.is_live and document.admin != self.scope["user"]:
            await self.close()
            return


        await super().connect()

    @sync_to_async
    def get_document(self):
        room = self.scope["url_route"]["kwargs"]["room"]
        # Assuming you have a method to get the document by room name
        return Document.objects.select_related("admin").get(share_token=room)