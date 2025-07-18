from django.urls import re_path
from consumers.notification_consumer import NotificationConsumer
from consumers.yjs_document_consumer import YjsDocumentConsumer



websocket_urlpatterns = [
    re_path(r"ws/notifications/(?P<user_id>[0-9]+)/$", NotificationConsumer.as_asgi()),
    re_path(r"ws/yjs-server/(?P<room>[a-zA-Z0-9\-]+)$", YjsDocumentConsumer.as_asgi()),
]
