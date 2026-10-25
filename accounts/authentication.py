from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from django.conf import settings
from django.core.cache import cache

class StrictCookieJWTAuthentication(JWTAuthentication):
    """
    Strict Cookie-Only JWT Authentication with CSRF / Origin enforcement
    and instant post-logout token revocation (F05 & F06 fix).
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
            user = self.get_user(validated_token)

            # F05 FIX: Check if this token's JTI was explicitly blacklisted upon logout
            jti = validated_token.get('jti')
            if jti and cache.get(f"blacklisted_access_jti_{jti}"):
                raise AuthenticationFailed('Token has been revoked by logout.')

            # F05 FIX: Check if user was logged out after this token was issued (revokes copied tokens)
            user_logout_time = cache.get(f"user_logout_time_{user.id}")
            token_iat = validated_token.get('iat')
            if user_logout_time and token_iat and token_iat <= user_logout_time:
                raise AuthenticationFailed('Session expired. Token revoked by logout.')

            if not user.is_active:
                raise AuthenticationFailed('User account is deactivated.')

            return user, validated_token
        except (AuthenticationFailed, PermissionDenied):
            raise
        except Exception:
            raise AuthenticationFailed('Invalid or expired cookie token')
