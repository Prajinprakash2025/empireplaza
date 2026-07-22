import random
from django.utils import timezone
from django.db.models import Q
from django.contrib.auth import get_user_model
from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import SendOTPSerializer, VerifyOTPSerializer, UserSerializer, AdminLoginSerializer, AdminUserSerializer

User = get_user_model()

class SendOTPView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = SendOTPSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        phone_number = serializer.validated_data['phone_number']
        role = serializer.validated_data.get('role', 'user')
        username = serializer.validated_data.get('username', f"user_{phone_number}")

        # Generate a random 6-digit OTP
        otp_code = str(random.randint(100000, 999999))
        
        # Get or create the user
        user, created = User.objects.get_or_create(
            phone_number=phone_number,
            defaults={
                'username': username,
                'role': role
            }
        )
        
        # Update user's role if they register with a different role initially
        if created and role != 'user':
            user.role = role

        # Save OTP details to database
        user.otp = otp_code
        user.otp_created_at = timezone.now()
        user.is_verified = False
        user.save()

        # In production: Send SMS here.
        # For development: Print to console and return in API response
        print(f"--- OTP for {phone_number} is {otp_code} ---")
        
        return Response({
            "message": "OTP sent successfully",
            "otp_development_only": otp_code  # Remove this field in production!
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

        # Check if OTP matches
        if user.otp != otp:
            return Response({"error": "Invalid OTP"}, status=status.HTTP_400_BAD_REQUEST)

        # Check if OTP has expired
        if user.is_otp_expired():
            return Response({"error": "OTP has expired. Please request a new one"}, status=status.HTTP_400_BAD_REQUEST)

        # Mark user as verified and clear OTP fields
        user.is_verified = True
        user.otp = None
        user.otp_created_at = None
        user.save()

        # Generate JWT Tokens (Access & Refresh)
        refresh = RefreshToken.for_user(user)
        
        return Response({
            "message": "OTP verified successfully",
            "user": UserSerializer(user).data,
            "tokens": {
                "refresh": str(refresh),
                "access": str(refresh.access_token),
            }
        }, status=status.HTTP_200_OK)
    

class AdminLoginView(APIView):
    """
    API endpoint for Admin login using Username and Password ONLY.
    Returns JWT access & refresh tokens if credentials are valid and user is an admin.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = AdminLoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        username = serializer.validated_data.get('username')
        password = serializer.validated_data.get('password')

        # Find user ONLY by username
        user = User.objects.filter(username=username).first()

        # Verify user exists and password is correct
        if user is None or not user.check_password(password):
            return Response(
                {"error": "Invalid username or password"}, 
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Check if the user has admin role or is a superuser
        if user.role != 'admin' and not user.is_superuser:
            return Response(
                {"error": "Access denied. Only Admins can login here."}, 
                status=status.HTTP_403_FORBIDDEN
            )

        # Auto-update role to 'admin' if superuser created via terminal
        if user.is_superuser and user.role != 'admin':
            user.role = 'admin'
            user.save()

        # Generate JWT Tokens
        refresh = RefreshToken.for_user(user)

        return Response({
            "message": "Admin logged in successfully",
            "user": AdminUserSerializer(user).data,
            "tokens": {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            }
        }, status=status.HTTP_200_OK)