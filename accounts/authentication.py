from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from django.conf import settings
from django.core.cache import cache


def enforce_csrf_protection(request):
    """
    Strict CSRF, Sec-Fetch-Site, and Origin enforcement for cookie-authenticated requests.
    """
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

    # F06/R4-03 FIX: On HTTPS mutating requests, require Origin or Referer
    is_https = request.is_secure() or request.META.get('HTTP_X_FORWARDED_PROTO') == 'https'
    if is_https and not origin:
        raise PermissionDenied('CSRF Failed: Origin or Referer header required on HTTPS.')

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


class StrictCookieJWTAuthentication(JWTAuthentication):
    """
    Strict Cookie-Only JWT Authentication with CSRF / Origin enforcement
    and durable database-backed token blacklist verification.
    """
    def enforce_csrf(self, request):
        enforce_csrf_protection(request)

    def authenticate(self, request):
        raw_token = request.COOKIES.get('access_token')

        if raw_token is None:
            return None

        # Enforce CSRF check for cookie-authenticated mutating requests
        self.enforce_csrf(request)

        try:
            validated_token = self.get_validated_token(raw_token)
            user = self.get_user(validated_token)

            jti = validated_token.get('jti')
            if jti:
                # 1. Fast Cache check
                if cache.get(f"blacklisted_access_jti_{jti}"):
                    raise AuthenticationFailed('Token has been revoked by logout.')

                # 2. Durable database blacklist check (cross-worker and restart persistence)
                from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
                if BlacklistedToken.objects.filter(token__jti=jti).exists():
                    cache.set(f"blacklisted_access_jti_{jti}", True, timeout=7 * 86400)
                    raise AuthenticationFailed('Token has been revoked by logout.')

            # R4-01 FIX: Persistent token_version verification across all sessions and cache loss
            token_ver = validated_token.get('token_version')
            expected_ver = getattr(user, 'token_version', 1) or 1
            if token_ver is not None and token_ver != expected_ver:
                raise AuthenticationFailed('Session expired. Token revoked by logout.')

            # Check if user was logged out before this token was issued (legacy fallback for tokens without version)
            if token_ver is None:
                user_logout_time = cache.get(f"user_logout_time_{user.id}")
                token_iat = validated_token.get('iat')
                if user_logout_time and token_iat and token_iat < int(user_logout_time):
                    raise AuthenticationFailed('Session expired. Token revoked by logout.')

            if not user.is_active:
                raise AuthenticationFailed('User account is deactivated.')

            return user, validated_token
        except (AuthenticationFailed, PermissionDenied):
            raise
        except Exception:
            raise AuthenticationFailed('Invalid or expired cookie token')
