from django.urls import re_path
from consumers.notification_consumer import NotificationConsumer
from consumers.document_consumer import DocumentLiveConsumer

websocket_urlpatterns = [
    re_path(r"ws/notifications/(?P<user_id>[0-9]+)/$", NotificationConsumer.as_asgi()),
    re_path(r"ws/document-live/(?P<share_token>[a-zA-Z0-9\-]+)/$", DocumentLiveConsumer.as_asgi()),
]
