from django.urls import path
from rest_framework.routers import DefaultRouter

from user_auth.views import RegisterApiView, LoginAPIView, VerifyEmailView, ResetPasswordConfirmView, \
    ResetPasswordRequestView, LogoutAPIView
from document.views import DocumentViewSet, RequestAccessAPIView, ApproveAccessAPIView, RevokeAccessAPIView, \
    CommentListCreateView, CommentUpdateView
from .views import ping, test_token

router = DefaultRouter()
router.register('documents', DocumentViewSet, basename='document')

urlpatterns = router.urls + [
    path('', ping, name='ping'),
    path('test-token/', test_token, name='test_tok`en'),

    # User authentication URLs
    path('register/', RegisterApiView.as_view(), name='register'),
    path('login/', LoginAPIView.as_view(), name='login'),
    path("logout/", LogoutAPIView.as_view(), name='logout'),

    # request access to a document
    path('documents/<int:document_id>/request-access', RequestAccessAPIView.as_view(), name='request_access'),
    path("documentaccess/<int:access_id>/approve-access", ApproveAccessAPIView.as_view(), name='approve_access'),
    path("documentaccess/<int:access_id>/revoke-access", RevokeAccessAPIView.as_view(), name='revoke_access'),

    # email verification url
    path("email-verification/<uidb64>/<token>/", VerifyEmailView.as_view(), name='email_verification'),

    # reset password url
    path("reset-password/", ResetPasswordRequestView.as_view(), name='reset_password_request'),
    path("reset-password/<uidb64>/<token>/", ResetPasswordConfirmView.as_view(), name='reset_password'),

    # Comment URLs
    path("documents/<int:document_id>/comments/", CommentListCreateView.as_view(), name='comments'),
    path("comments/<int:pk>/", CommentUpdateView.as_view(), name='comment_update'),
]
