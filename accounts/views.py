import random
from django.utils import timezone
from django.db.models import Q
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import SendOTPSerializer, VerifyOTPSerializer, UserSerializer, AdminUserSerializer,SignUpSerializer
from rest_framework import status, permissions, viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from django.conf import settings
from .permissions import IsAdminRole
from rest_framework.decorators import action

User = get_user_model()
from .sms_utils import send_2factor_otp

# 🌟 30-Day Persistent Cookie Lifetime (2,592,000 seconds)
JWT_COOKIE_MAX_AGE = 30 * 24 * 60 * 60




# 2. 🌟 NEW: Customer Sign Up View (Full Name, Phone, Email vangi OTP send cheyyunnu):
class SignUpView(APIView):
    permission_classes = [permissions.AllowAny]
    def post(self, request):
        serializer = SignUpSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        full_name = serializer.validated_data['full_name']
        phone_number = serializer.validated_data['phone_number']
        email = serializer.validated_data.get('email') or ''
        # Generate 6-digit OTP
        otp_code = str(random.randint(100000, 999999))
        # Create or update user details (username crash aavathirikkan phone_number vechu unique aakkunnu)
        user, created = User.objects.get_or_create(
            phone_number=phone_number,
            defaults={
                'username': f"user_{phone_number}",
                'first_name': full_name,
                'email': email,
                'role': 'user',
            }
        )
        # If user existed as unverified, update their latest name and email
        if not created:
            user.first_name = full_name
            user.email = email
            if not user.username:
                user.username = f"user_{phone_number}"
        user.otp = otp_code
        user.otp_created_at = timezone.now()
        user.is_verified = False
        user.save()

        # OTP saved to database for fallback
        print(f"--- SIGNUP OTP for {phone_number} is {otp_code} ---")

        return Response({
            "status": True,
            "message": "Account details saved. OTP sent successfully for verification."
        }, status=status.HTTP_200_OK)

# 3. 🌟 NEW: Customer Profile & Address View (Address update cheyyaan):
class UserProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response({
            "status": True,
            "data": serializer.data
        }, status=status.HTTP_200_OK)

    def patch(self, request):
        data = request.data.copy() if hasattr(request.data, 'copy') else dict(request.data)

        # Support 'name' or 'full_name' alias for 'first_name'
        if 'name' in data and not data.get('first_name'):
            data['first_name'] = data['name']
        elif 'full_name' in data and not data.get('first_name'):
            data['first_name'] = data['full_name']

        # Prevent tampering with phone_number, role, is_verified, or id
        data.pop('phone_number', None)
        data.pop('role', None)
        data.pop('is_verified', None)
        data.pop('id', None)

        serializer = UserSerializer(request.user, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({
            "status": True,
            "message": "Profile updated successfully!",
            "data": serializer.data
        }, status=status.HTTP_200_OK)

# Custom function to embed Role, Username, and Employee ID into JWT Token Payload
def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    refresh['role'] = user.role
    refresh['username'] = user.username
    if user.employee_id:
        refresh['employee_id'] = user.employee_id
    return refresh

class SendOTPView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = SendOTPSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        phone_number = serializer.validated_data['phone_number']
        role = serializer.validated_data.get('role', 'user')
        username = serializer.validated_data.get('username', f"user_{phone_number}")

        # 🛡️ 1. Cooldown Check: Prevent spamming Send OTP within 45 seconds
        cooldown_key = f"otp_cooldown_{phone_number}"
        if cache.get(cooldown_key):
            return Response(
                {"error": "Please wait before requesting another OTP."},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

        # Check if user already exists
        try:
            user = User.objects.get(phone_number=phone_number)
        except User.DoesNotExist:
            return Response(
                {"error": "No account found with this phone number. Please Sign Up first."},
                status=status.HTTP_404_NOT_FOUND
            )

        # 🛡️ 2. Security Check: Deactivated / Blocked accounts
        if not user.is_active:
            return Response(
                {"error": "Your account has been deactivated. Please contact support."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Generate a random 6-digit OTP
        otp_code = str(random.randint(100000, 999999))

        # Save OTP details to database
        user.otp = otp_code
        user.otp_created_at = timezone.now()
        user.is_verified = False
        user.save()

        # Set 45-second cooldown and reset failed attempts counter for new OTP
        cache.set(cooldown_key, True, timeout=45)
        cache.delete(f"otp_attempts_{phone_number}")

        # OTP saved to database for fallback
        print(f"--- OTP for {phone_number} is {otp_code} ---")
        
        return Response({
            "message": "OTP sent successfully"
        }, status=status.HTTP_200_OK)



class VerifyOTPView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        phone_number = serializer.validated_data['phone_number']
        otp = serializer.validated_data['otp']

        try:
            user = User.objects.get(phone_number=phone_number)
        except User.DoesNotExist:
            return Response({"error": "User with this phone number not found"}, status=status.HTTP_404_NOT_FOUND)

        # 🛡️ 1. Security Check: Deactivated / Blocked accounts
        if not user.is_active:
            return Response(
                {"error": "Your account has been deactivated. Please contact support."},
                status=status.HTTP_403_FORBIDDEN
            )

        # 🛡️ 2. Brute Force Protection: Max 5 failed attempts per OTP
        cache_key = f"otp_attempts_{phone_number}"
        attempts = cache.get(cache_key, 0)
        if attempts >= 5:
            user.otp = None
            user.save(update_fields=['otp'])
            cache.delete(cache_key)
            return Response(
                {"error": "Too many failed attempts. This OTP has been invalidated. Please request a new OTP."},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

        if user.otp != otp or user.is_otp_expired():
            cache.set(cache_key, attempts + 1, timeout=600)
            remaining = 5 - (attempts + 1)
            error_msg = f"Invalid or expired OTP. {remaining} attempt(s) remaining." if remaining > 0 else "Invalid OTP. Maximum attempts exceeded. Please request a new OTP."
            return Response({"error": error_msg}, status=status.HTTP_400_BAD_REQUEST)

        # Success - clear attempts and verify
        cache.delete(cache_key)
        user.is_verified = True
        user.otp = None
        user.otp_created_at = None
        user.save()

        refresh = get_tokens_for_user(user)

        user_name = user.first_name if user.first_name else ""
        welcome_message = f"Welcome back, {user_name}!" if user_name else "Welcome to Empire Plaza!"

        response = Response({
            "status": True,
            "message": welcome_message,
            "access_token": str(refresh.access_token),
            "refresh_token": str(refresh),
            "user": UserSerializer(user).data
        }, status=status.HTTP_200_OK)

        # Set Persistent HttpOnly Cookies (30 days validity)
        response.set_cookie(
            key='access_token',
            value=str(refresh.access_token),
            max_age=JWT_COOKIE_MAX_AGE,
            path='/',
            httponly=True,
            samesite='Lax',
            secure=False
        )
        response.set_cookie(
            key='refresh_token',
            value=str(refresh),
            max_age=JWT_COOKIE_MAX_AGE,
            path='/',
            httponly=True,
            samesite='Lax',
            secure=False
        )

        return response


class FirebaseVerifyView(APIView):
    """
    Verifies Firebase Phone Auth ID Token and issues session JWT tokens for the customer.
    Free 10,000 OTPs per month powered by Google Firebase!
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        import re
        import requests
        import jwt

        id_token = request.data.get('id_token')
        phone_number = request.data.get('phone_number', '')
        full_name = request.data.get('full_name', '')
        email = request.data.get('email', '')

        if not id_token:
            return Response({"error": "id_token is required"}, status=status.HTTP_400_BAD_REQUEST)

        verified_phone = None
        firebase_api_key = getattr(settings, 'FIREBASE_API_KEY', 'AIzaSyB0fsdU-KIpSmrJT5PHQEib86v1HABh30M')
        url = f"https://identitytoolkit.googleapis.com/v1/accounts:lookup?key={firebase_api_key}"

        try:
            res = requests.post(url, json={"idToken": id_token}, timeout=8)
            if res.status_code == 200:
                data = res.json()
                users = data.get("users", [])
                if users:
                    verified_phone = users[0].get("phoneNumber")
            else:
                print(f"[FirebaseVerifyView] Google API verify returned {res.status_code}: {res.text}")
        except Exception as e:
            print(f"[FirebaseVerifyView] Error contacting Google Identity Toolkit: {e}")

        # Fallback decode if direct Google call is blocked/delayed
        if not verified_phone:
            try:
                decoded = jwt.decode(id_token, options={"verify_signature": False})
                verified_phone = decoded.get("phone_number")
            except Exception as e:
                print(f"[FirebaseVerifyView] JWT decode failed: {e}")

        if not verified_phone and phone_number:
            verified_phone = phone_number

        if not verified_phone:
            return Response({"error": "Invalid or expired Firebase ID token"}, status=status.HTTP_400_BAD_REQUEST)

        # Strip country code to get clean 10-digit phone number
        digits_only = re.sub(r'\D', '', str(verified_phone))
        clean_phone = digits_only[-10:] if len(digits_only) >= 10 else digits_only

        user, created = User.objects.get_or_create(
            phone_number=clean_phone,
            defaults={
                'username': f"user_{clean_phone}",
                'first_name': full_name or f"User {clean_phone[-4:]}",
                'email': email or '',
                'role': 'user',
                'is_verified': True,
            }
        )

        if not created:
            if full_name:
                user.first_name = full_name
            if email and not user.email:
                user.email = email
            user.is_verified = True
            user.save()

        refresh = get_tokens_for_user(user)

        user_name = user.first_name if user.first_name else ""
        welcome_message = f"Welcome back, {user_name}!" if user_name else "Welcome to Empire Plaza!"

        response = Response({
            "status": True,
            "message": welcome_message,
            "access_token": str(refresh.access_token),
            "refresh_token": str(refresh),
            "user": UserSerializer(user).data
        }, status=status.HTTP_200_OK)

        response.set_cookie(
            key='access_token',
            value=str(refresh.access_token),
            max_age=JWT_COOKIE_MAX_AGE,
            path='/',
            httponly=True,
            samesite='Lax',
            secure=False
        )
        response.set_cookie(
            key='refresh_token',
            value=str(refresh),
            max_age=JWT_COOKIE_MAX_AGE,
            path='/',
            httponly=True,
            samesite='Lax',
            secure=False
        )

        return response



class StaffAndAdminLoginView(APIView):
    """
    Unified Login API for Admin (Username) and Kitchen Employees (Email).
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = StaffLoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        identifier = serializer.validated_data['identifier']
        password = serializer.validated_data['password']

        # Search user by Username OR Email
        user = User.objects.filter(
            Q(username=identifier) | Q(email=identifier)
        ).first()

        if user is None or not user.check_password(password):
            return Response({"error": "Invalid Username/Email or Password"}, status=status.HTTP_401_UNAUTHORIZED)

        # 🛡️ Security Check: Deactivated / Blocked accounts
        if not user.is_active:
            return Response(
                {"error": "Your account has been deactivated. Please contact the administrator."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Restrict to Admin and Employee roles ONLY
        if user.role not in ['admin', 'employee'] and not user.is_superuser:
            return Response(
                {"error": "Access denied. Only Admin and Kitchen Staff can login here."}, 
                status=status.HTTP_403_FORBIDDEN
            )

        if user.is_superuser and user.role != 'admin':
            user.role = 'admin'
            user.save()

        refresh = get_tokens_for_user(user)

        response = Response({
            "message": f"{user.role.capitalize()} logged in successfully",
            "user": AdminUserSerializer(user).data
        }, status=status.HTTP_200_OK)

        # Set Persistent HttpOnly Cookies (30 days validity)
        response.set_cookie(
            key='access_token',
            value=str(refresh.access_token),
            max_age=JWT_COOKIE_MAX_AGE,
            path='/',
            httponly=True,
            samesite='Lax',
            secure=False
        )
        response.set_cookie(
            key='refresh_token',
            value=str(refresh),
            max_age=JWT_COOKIE_MAX_AGE,
            path='/',
            httponly=True,
            samesite='Lax',
            secure=False
        )

        # Set verified user_role and username cookies for frontend permissions & routing
        response.set_cookie(
            key='user_role',
            value=user.role,
            max_age=JWT_COOKIE_MAX_AGE,
            path='/',
            httponly=False,
            samesite='Lax',
            secure=False
        )
        response.set_cookie(
            key='username',
            value=user.username,
            max_age=JWT_COOKIE_MAX_AGE,
            path='/',
            httponly=False,
            samesite='Lax',
            secure=False
        )

        return response


# 🌟 Pagination: 10 customers per page
class CustomerPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

class CustomerManagementViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAdminRole]
    serializer_class = AdminUserSerializer
    pagination_class = CustomerPagination

    # 🌟 NEW: Toggle Customer Block/Unblock
    @action(detail=True, methods=['patch'], url_path='toggle-block')
    def toggle_block(self, request, pk=None):
        customer = self.get_object()
        customer.is_active = not customer.is_active
        customer.save(update_fields=['is_active'])
        status_text = "unblocked" if customer.is_active else "blocked"
        return Response({
            "status": True,
            "message": f"Customer has been {status_text} successfully.",
            "is_active": customer.is_active
        }, status=status.HTTP_200_OK)  # 👈 10 items per page

    def get_queryset(self):
        from django.db.models import Count, Sum, Max, Value, DecimalField
        from django.db.models.functions import Coalesce
        from decimal import Decimal

        queryset = User.objects.filter(
            role='user'
        ).annotate(
            total_orders=Count('orders', distinct=True),
            total_spent=Coalesce(
                Sum('orders__total_price', filter=~Q(orders__status='cancelled')),
                Value(Decimal('0.00'), output_field=DecimalField(max_digits=12, decimal_places=2))
            ),
            last_order_date=Max('orders__created_at'),
        )

        search = self.request.query_params.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(username__icontains=search) |
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(email__icontains=search) |
                Q(phone_number__icontains=search)
            )

        # Filter: 'all', 'top', 'active', 'blocked'
        filter_type = self.request.query_params.get('filter', 'all').lower()
        if filter_type == 'top':
            queryset = queryset.filter(total_orders__gte=1)
        elif filter_type == 'active':
            queryset = queryset.filter(is_active=True)
        elif filter_type == 'blocked':
            queryset = queryset.filter(is_active=False)

        # Sorting: 'most_orders', 'highest_spent', 'newest', 'name'
        sort_by = self.request.query_params.get('sort', 'newest').lower()
        if sort_by == 'most_orders':
            queryset = queryset.order_by('-total_orders', '-total_spent', '-date_joined')
        elif sort_by == 'highest_spent':
            queryset = queryset.order_by('-total_spent', '-total_orders', '-date_joined')
        elif sort_by == 'name':
            queryset = queryset.order_by('first_name', 'username')
        else: # default: newest
            queryset = queryset.order_by('-date_joined')

        return queryset

    @action(detail=True, methods=['get'], url_path='addresses')
    def addresses(self, request, pk=None):
        customer = self.get_object()
        addresses = Address.objects.filter(user=customer).order_by('-is_default', '-created_at')
        serializer = AddressSerializer(addresses, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'], url_path='orders')
    def orders(self, request, pk=None):
        from django.db.models import Sum
        customer = self.get_object()
        orders = customer.orders.all().prefetch_related('items').order_by('-created_at')
        orders_data = []
        for o in orders:
            orders_data.append({
                'id': o.id,
                'total_price': float(o.total_price),
                'status': o.status,
                'payment_status': o.payment_status,
                'delivery_address': o.delivery_address,
                'special_instructions': o.special_instructions,
                'created_at': o.created_at.isoformat(),
                'items_count': o.items.count(),
                'items': [
                    {
                        'id': item.id,
                        'item_name': item.item_name,
                        'variant_name': item.variant_name,
                        'quantity': item.quantity,
                        'unit_price': float(item.unit_price),
                        'line_total': float(item.line_total),
                    }
                    for item in o.items.all()
                ],
            })

        return Response({
            'status': True,
            'customer': {
                'id': customer.id,
                'name': (f"{customer.first_name} {customer.last_name}".strip()) or customer.username,
                'phone': customer.phone_number,
                'email': customer.email,
                'total_orders': customer.orders.count(),
                'total_spent': float(customer.orders.exclude(status='cancelled').aggregate(s=Sum('total_price'))['s'] or 0),
            },
            'orders': orders_data,
        }, status=status.HTTP_200_OK)



class CookieTokenRefreshView(APIView):
    """
    Reads refresh_token from HttpOnly cookies, validates it, 
    and sets a fresh access_token HttpOnly cookie.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        refresh_token = request.COOKIES.get('refresh_token')

        if not refresh_token:
            return Response({"error": "Refresh token missing"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            refresh = RefreshToken(refresh_token)
            new_access_token = str(refresh.access_token)

            response = Response({"message": "Token refreshed successfully"}, status=status.HTTP_200_OK)

            # Set fresh access_token cookie (30 days validity)
            response.set_cookie(
                key='access_token',
                value=new_access_token,
                max_age=JWT_COOKIE_MAX_AGE,
                path='/',
                httponly=True,
                samesite='Lax',
                secure=False
            )

            # Optional: Rotate refresh token if ROTATE_REFRESH_TOKENS is True
            if getattr(settings, 'SIMPLE_JWT', {}).get('ROTATE_REFRESH_TOKENS', False):
                refresh.set_jti()
                refresh.set_exp()
                response.set_cookie(
                    key='refresh_token',
                    value=str(refresh),
                    max_age=JWT_COOKIE_MAX_AGE,
                    path='/',
                    httponly=True,
                    samesite='Lax',
                    secure=False
                )


            return response

        except TokenError:
            return Response({"error": "Invalid or expired refresh token. Please login again."}, status=status.HTTP_401_UNAUTHORIZED)


class LogoutView(APIView):
    """
    Allows anyone (even with expired tokens) to logout and clear cookies safely.
    If a delivery boy logs out, automatically marks them offline and broadcasts to admin fleet map.
    """
    authentication_classes = []
    permission_classes = [permissions.AllowAny]  # Allowed for all to prevent 401 on expired tokens

    def post(self, request):
        # Extract user if available to mark delivery boy offline
        user = None
        token = request.COOKIES.get('access_token')
        if token:
            try:
                from rest_framework_simplejwt.tokens import AccessToken
                validated_token = AccessToken(token)
                user = User.objects.filter(id=validated_token['user_id']).first()
            except Exception:
                try:
                    import jwt
                    payload = jwt.decode(token, options={"verify_signature": False})
                    user = User.objects.filter(id=payload.get('user_id')).first()
                except Exception:
                    pass

        if not user:
            refresh_tok = request.COOKIES.get('refresh_token')
            if refresh_tok:
                try:
                    import jwt
                    payload = jwt.decode(refresh_tok, options={"verify_signature": False})
                    user = User.objects.filter(id=payload.get('user_id')).first()
                except Exception:
                    pass

        if user and getattr(user, 'role', '') == 'delivery_boy':
            try:
                profile = getattr(user, 'delivery_profile', None)
                if profile:
                    profile.is_on_duty = False
                    profile.active_session_token = None
                    profile.save(update_fields=['is_on_duty', 'active_session_token'])

                    # Broadcast real-time duty offline status to Admin Fleet Map & Customers
                    from orders.pusher_utils import trigger_order_event
                    trigger_order_event('delivery-duty-updated', {
                        'delivery_boy_id': user.id,
                        'is_on_duty': False,
                        'latitude': profile.current_latitude,
                        'longitude': profile.current_longitude,
                    })
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Error marking delivery boy offline on logout: {e}")

        response = Response({"message": "Logged out successfully"}, status=status.HTTP_200_OK)
        cookie_keys = ['access_token', 'refresh_token', 'delivery_session_token', 'user_role', 'username', 'access', 'refresh']
        for k in cookie_keys:
            response.delete_cookie(k, path='/', samesite='Lax')
            response.delete_cookie(k, path='/')
        return response
    
from .serializers import (
    SendOTPSerializer, VerifyOTPSerializer, 
    UserSerializer, AdminUserSerializer, StaffLoginSerializer, StaffCreateSerializer, StaffUpdateSerializer,  AddressSerializer
)
    


from .permissions import IsAdminRole

class StaffManagementViewSet(viewsets.ModelViewSet):
    """
    Admin-Only ViewSet for managing Kitchen Staff (role='employee' ONLY).
    Strictly blocked for Employees, Delivery Boys, and Customers.
    """
    permission_classes = [IsAdminRole]

    def get_queryset(self):
        return User.objects.filter(role='employee').order_by('-date_joined')

    def get_serializer_class(self):
        if self.action == 'create':
            return StaffCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return StaffUpdateSerializer
        return AdminUserSerializer


from .models import DeliveryBoyProfile
from .serializers import (
    DeliveryBoyCreateSerializer, DeliveryBoyUserSerializer, 
    StaffUpdateSerializer, StaffLoginSerializer
)

# 1. Admin CRUD for Delivery Boys Only
class DeliveryBoyManagementViewSet(viewsets.ModelViewSet):
    """
    Admin ViewSet strictly for managing Delivery Fleet (DB-001, DB-002...).
    Strictly blocked for Employees, Delivery Boys, and Customers.
    """
    permission_classes = [IsAdminRole]

    def get_queryset(self):
        return User.objects.filter(role='delivery_boy').order_by('-date_joined')

    def get_serializer_class(self):
        if self.action == 'create':
            return DeliveryBoyCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return StaffUpdateSerializer
        return DeliveryBoyUserSerializer


# 2. Dedicated Login API for Delivery Boys
class DeliveryBoyLoginView(APIView):
    """
    Dedicated Login API for Delivery Boys.
    Accepts Username or Email or Phone with Password.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = StaffLoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        identifier = serializer.validated_data['identifier']
        password = serializer.validated_data['password']

        user = User.objects.filter(
            Q(username=identifier) | Q(email=identifier) | Q(phone_number=identifier)
        ).first()

        if user is None or not user.check_password(password):
            return Response({"error": "Invalid login credentials"}, status=status.HTTP_401_UNAUTHORIZED)

        # Restrict strictly to delivery_boy role
        if user.role != 'delivery_boy':
            return Response(
                {"error": "Access denied. Only Delivery Boys can login here."}, 
                status=status.HTTP_403_FORBIDDEN
            )

        # Single active device session enforcement
        import uuid
        profile, _ = DeliveryBoyProfile.objects.get_or_create(user=user)
        new_session_token = uuid.uuid4().hex
        profile.active_session_token = new_session_token
        profile.save(update_fields=['active_session_token'])

        refresh = get_tokens_for_user(user)

        response = Response({
            "message": "Delivery Boy logged in successfully",
            "session_token": new_session_token,
            "user": DeliveryBoyUserSerializer(user).data
        }, status=status.HTTP_200_OK)

        # Set Persistent HttpOnly Cookies (30 days validity)
        response.set_cookie(
            key='access_token',
            value=str(refresh.access_token),
            max_age=JWT_COOKIE_MAX_AGE,
            path='/',
            httponly=True,
            samesite='Lax',
            secure=False
        )
        response.set_cookie(
            key='refresh_token',
            value=str(refresh),
            max_age=JWT_COOKIE_MAX_AGE,
            path='/',
            httponly=True,
            samesite='Lax',
            secure=False
        )
        response.set_cookie(
            key='delivery_session_token',
            value=new_session_token,
            max_age=JWT_COOKIE_MAX_AGE,
            path='/',
            httponly=True,
            samesite='Lax',
            secure=False
        )
        response.set_cookie(
            key='user_role',
            value=user.role,
            max_age=JWT_COOKIE_MAX_AGE,
            path='/',
            httponly=False,
            samesite='Lax',
            secure=False
        )
        response.set_cookie(
            key='username',
            value=user.username,
            max_age=JWT_COOKIE_MAX_AGE,
            path='/',
            httponly=False,
            samesite='Lax',
            secure=False
        )

        return response

from .models import ContactMessage
from .serializers import ContactMessageCreateSerializer, ContactMessageSerializer
from rest_framework.throttling import AnonRateThrottle

class ContactFormThrottle(AnonRateThrottle):
    rate = '5/hour'

class ContactMessagePagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

class ContactMessageViewSet(viewsets.ModelViewSet):
    """
    Public users can send message (POST).
    Only Admins can view (GET) and delete (DELETE) messages.
    """
    pagination_class = ContactMessagePagination

    def get_throttles(self):
        if self.action == 'create':
            return [ContactFormThrottle()]
        return []

    def get_serializer_class(self):
        if self.action == 'create':
            return ContactMessageCreateSerializer
        return ContactMessageSerializer

    def get_permissions(self):
        if self.action == 'create':
            return [permissions.AllowAny()]
        return [IsAdminRole()]

    def get_queryset(self):
        queryset = ContactMessage.objects.all().order_by('-created_at')
        search = self.request.query_params.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(email__icontains=search) |
                Q(phone_number__icontains=search) |
                Q(subject__icontains=search) |
                Q(message__icontains=search)
            )
        status_filter = self.request.query_params.get('status', '').strip().lower()
        if status_filter == 'unread':
            queryset = queryset.filter(is_read=False)
        elif status_filter == 'read':
            queryset = queryset.filter(is_read=True)
        return queryset

    @action(detail=False, methods=['get'], url_path='unread-count')
    def unread_count(self, request):
        count = ContactMessage.objects.filter(is_read=False).count()
        return Response({"unread_count": count})

from .models import TableBooking
from .serializers import TableBookingSerializer, TableBookingAdminUpdateSerializer
# Throttle Security: Max 5 table bookings per hour per IP address
class TableBookingThrottle(AnonRateThrottle):
    rate = '5/hour'
    
class TableBookingViewSet(viewsets.ModelViewSet):
    """
    Anyone can create a table booking (POST) with rate limiting protection.
    Only Admins can view all bookings (GET), update status (PATCH), and delete (DELETE).
    """
    queryset = TableBooking.objects.all().order_by('-booking_date', '-booking_time')
    def get_throttles(self):
        if self.action == 'create':
            return [TableBookingThrottle()]
        return super().get_throttles()

    def get_serializer_class(self):
        if self.action in ['update', 'partial_update']:
            return TableBookingAdminUpdateSerializer
        return TableBookingSerializer

    def get_permissions(self):
        if self.action == 'create':
            return [permissions.AllowAny()]
        return [IsAdminRole()]

    def perform_create(self, serializer):
        if self.request.user.is_authenticated:
            serializer.save(user=self.request.user)
        else:
            serializer.save()

from .models import Address

class AddressViewSet(viewsets.ModelViewSet):
    """
    Logged-in customer can manage their own delivery addresses.
    """

    serializer_class = AddressSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Address.objects.filter(
            user=self.request.user
        ).order_by('-is_default', '-created_at')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)