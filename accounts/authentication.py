from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from django.conf import settings

class StrictCookieJWTAuthentication(JWTAuthentication):
    """
    Strict Cookie-Only JWT Authentication with CSRF / Origin enforcement.
    Reads access_token strictly from HTTP HttpOnly cookies.
    Enforces Origin / Referer validation on mutating HTTP methods to prevent CSRF.
    """
    def enforce_csrf(self, request):
        # Safe methods don't mutate state
        if request.method in ('GET', 'HEAD', 'OPTIONS', 'TRACE'):
            return

        # Check Sec-Fetch-Site: if the browser explicitly marks it as cross-site, reject
        sec_fetch_site = request.META.get('HTTP_SEC_FETCH_SITE')
        if sec_fetch_site and sec_fetch_site.lower() == 'cross-site':
            raise PermissionDenied('CSRF Failed: Cross-site request rejected.')

        # Check Origin or Referer
        origin = request.META.get('HTTP_ORIGIN')
        if not origin:
            referer = request.META.get('HTTP_REFERER')
            if referer:
                from urllib.parse import urlparse
                parsed = urlparse(referer)
                origin = f"{parsed.scheme}://{parsed.netloc}"

        if origin:
            allowed_origins = getattr(settings, 'CORS_ALLOWED_ORIGINS', [])
            try:
                host = request.get_host().lower()
            except Exception:
                host = ''
            clean_origin = origin.rstrip('/').lower()

            is_allowed = (
                clean_origin in [o.rstrip('/').lower() for o in allowed_origins]
                or (host and (
                    clean_origin == f"https://{host}"
                    or clean_origin == f"http://{host}"
                    or clean_origin.endswith(f"://{host}")
                    or f"://{host}:" in clean_origin
                ))
            )
            if not is_allowed:
                raise PermissionDenied(f'CSRF Failed: Origin {origin} is not allowed.')

    def authenticate(self, request):
        raw_token = request.COOKIES.get('access_token')

        if raw_token is None:
            return None

        # Enforce CSRF check for cookie-authenticated mutating requests
        self.enforce_csrf(request)

        try:
            validated_token = self.get_validated_token(raw_token)
            return self.get_user(validated_token), validated_token
        except (AuthenticationFailed, PermissionDenied):
            raise
        except Exception:
            raise AuthenticationFailed('Invalid or expired cookie token')
