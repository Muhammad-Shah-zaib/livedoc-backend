from django.contrib.auth import get_user_model

User = get_user_model()

class RefreshTokenMiddleware:
    """
    Middleware to add access token to the response cookies.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        response = self.get_response(request) # calling the view

        if hasattr(request, 'new_access_token'): # checking if the request has a new access token
            response.set_cookie(
                key='access_token',
                value=request.new_access_token,
                httponly=True,
                secure=True,
                samesite='None',
                max_age=300,
            )
        return response
