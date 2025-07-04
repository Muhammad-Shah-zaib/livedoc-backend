import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "livedoc.settings")

# Only now it's safe to import Django-dependent things
from django.core.asgi import get_asgi_application

django_asgi_app = get_asgi_application()

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator

from document.routing import websocket_urlpatterns
from user_auth.auth import CookieAuthMiddlewareStack  # moved below


application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket":
            CookieAuthMiddlewareStack(URLRouter(websocket_urlpatterns))
        ,
    }
)
