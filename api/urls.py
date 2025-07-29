from django.urls import path
from rest_framework.routers import DefaultRouter

from liveblocks.views import liveblocks_auth
from notification.views import NotificationViewSet
from user_auth.views.auth_views import RegisterApiView, LoginAPIView, VerifyEmailView, ResetPasswordConfirmView, \
    ResetPasswordRequestView, LogoutAPIView, UpdateProfileView
from user_auth.views.google_oauth_views import GoogleLoginAPIView

from document.views import DocumentViewSet, RequestAccessAPIView, ApproveAccessAPIView, RevokeAccessAPIView, \
    CommentListCreateView, CommentUpdateView, DocumentAccessViewSet, LiveDocumentAccessView

from ai.views.summarize_document_view import SummarizeDocumentView
from ai.views.text_completion_view import TextCompletionView

from user_auth.views.user_profile_views import UserInfoUpdateView, UserProfileView, PasswordChangeView, \
    GetUserByEmailView, GetAllUsersView
from .views import ping, test_token

router = DefaultRouter()
router.register('documents', DocumentViewSet, basename='document')
router.register('document_access', DocumentAccessViewSet, basename='document_access')
router.register('notifications', NotificationViewSet, basename='notification')

urlpatterns = router.urls + [
    path('', ping, name='ping'),
    path('test-token/', test_token, name='test_tok`en'),

    # User authentication URLs
    path('register/', RegisterApiView.as_view(), name='register'),
    path('login/', LoginAPIView.as_view(), name='login'),
    path("logout/", LogoutAPIView.as_view(), name='logout'),
    path("login/google/", GoogleLoginAPIView.as_view(), name='google_login'),

    # User profile URLs
    path('user/profile/', UserInfoUpdateView.as_view(), name='user_profile_update'),
    path("user/get-profile/", UserProfileView.as_view(), name='user_profile_get'),
    path("user/change-password/", PasswordChangeView.as_view(), name='change_password'),
    path("user/by-email", GetUserByEmailView.as_view(), name='get_user_by_email'),
    path("user/update-profile/", UpdateProfileView.as_view(), name='user_update_profile'),
    path("user/all", GetAllUsersView.as_view(), name='get_all_users'),

    # request access to a document
    path('documents/<str:share_token>/request-access', RequestAccessAPIView.as_view(), name='request_access'),
    path("document_access/<int:access_id>/approve-access", ApproveAccessAPIView.as_view(), name='approve_access'),
    path("document_access/<int:access_id>/revoke-access", RevokeAccessAPIView.as_view(), name='revoke_access'),

    # Check if user can connect to the document or not
    path("documents/<str:share_token>/can-connect", LiveDocumentAccessView.as_view(), name='live_document_access'),

    # email verification url
    path("email-verification/<uidb64>/<token>/", VerifyEmailView.as_view(), name='email_verification'),

    # reset password url
    path("forgot-password/", ResetPasswordRequestView.as_view(), name='reset_password_request'),
    path("reset-password/<uidb64>/<token>/", ResetPasswordConfirmView.as_view(), name='reset_password'),

    # Comment URLs
    path("documents/<int:document_id>/comments/", CommentListCreateView.as_view(), name='comments'),
    path("comments/<int:pk>/", CommentUpdateView.as_view(), name='comment_update'),

    # ai URLs
    path("ai/documents/summarize/", SummarizeDocumentView.as_view(), name='summarize_document'),
    path("ai/documents/text-completion/", TextCompletionView.as_view(), name='text_completion'),

    # LIVEBLOCKS ROUTES
    path("liveblocks-auth/", liveblocks_auth, name="liveblocks_auth"),

]
