from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed

class StrictCookieJWTAuthentication(JWTAuthentication):
    """
    Strict Cookie-Only JWT Authentication.
    Reads access_token strictly from HTTP HttpOnly cookies.
    Ignores Authorization Headers to ensure JS never handles tokens (XSS protection).
    """
    def authenticate(self, request):
        raw_token = request.COOKIES.get('access_token')
        
        if raw_token is None:
            return None

        try:
            validated_token = self.get_validated_token(raw_token)
            return self.get_user(validated_token), validated_token
        except Exception:
            raise AuthenticationFailed('Invalid or expired cookie token')
