from rest_framework import serializers
from django.contrib.auth import get_user_model

User = get_user_model()

class SendOTPSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=15)
    role = serializers.CharField(max_length=20, required=False, default='user')
    username = serializers.CharField(max_length=150, required=False) # Fallback for django username

class VerifyOTPSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=15)
    otp = serializers.CharField(max_length=6)

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'phone_number', 'role', 'address', 'is_verified']

class AdminUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'role']

class AdminLoginSerializer(serializers.Serializer):
    username = serializers.CharField(required=True)
    password = serializers.CharField(write_only=True)