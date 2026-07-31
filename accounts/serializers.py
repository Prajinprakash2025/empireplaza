from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import CustomUser, DeliveryBoyProfile


User = get_user_model()

class SendOTPSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=15)
    role = serializers.CharField(max_length=20, required=False, default='user')
    username = serializers.CharField(max_length=150, required=False)

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
        fields = ['id', 'employee_id', 'username', 'phone_number', 'role', 'address']

# Unified Login Serializer for Admin & Employee
class StaffLoginSerializer(serializers.Serializer):
    identifier = serializers.CharField(required=False, allow_blank=True)
    username = serializers.CharField(required=False, allow_blank=True)
    email = serializers.CharField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, required=True)

    def validate(self, attrs):
        identifier = attrs.get('identifier') or attrs.get('username') or attrs.get('email')
        if not identifier:
            raise serializers.ValidationError({"identifier": "Please provide username, email, or identifier."})
        attrs['identifier'] = identifier
        return attrs

class StaffCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ['id', 'employee_id', 'username', 'email', 'phone_number', 'password', 'role', 'address']

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            phone_number=validated_data['phone_number'],
            password=validated_data['password'],
            role=validated_data.get('role', 'employee'),
            address=validated_data.get('address', '')
        )
        return user

class StaffUpdateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = User
        fields = ['username', 'email', 'phone_number', 'role', 'address', 'password']
        extra_kwargs = {
            'username': {'required': False},
            'phone_number': {'required': False},
            'email': {'required': False},
            'role': {'required': False},
            'address': {'required': False},
        }

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class DeliveryBoyProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryBoyProfile
        fields = ['vehicle_number', 'is_on_duty', 'is_busy', 'current_latitude', 'current_longitude']


class DeliveryBoyUserSerializer(serializers.ModelSerializer):
    delivery_profile = DeliveryBoyProfileSerializer(read_only=True)

    class Meta:
        model = CustomUser
        fields = ['id', 'employee_id', 'username', 'email', 'phone_number', 'role', 'address', 'delivery_profile']


class DeliveryBoyCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True)
    vehicle_number = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = CustomUser
        fields = ['id', 'employee_id', 'username', 'email', 'phone_number', 'password', 'address', 'vehicle_number']

    def create(self, validated_data):
        vehicle_num = validated_data.pop('vehicle_number', '')
        user = CustomUser.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            phone_number=validated_data['phone_number'],
            password=validated_data['password'],
            role='delivery_boy',
            address=validated_data.get('address', '')
        )
        # Create DeliveryBoyProfile automatically
        DeliveryBoyProfile.objects.create(user=user, vehicle_number=vehicle_num)
        return user

from .models import ContactMessage  

class ContactMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactMessage
        fields = ['id', 'name', 'email', 'phone_number', 'subject', 'message', 'is_read', 'created_at']
        read_only_fields = ['id', 'is_read', 'created_at']


from .models import TableBooking  # <--- ഇമ്പോർട്ട് ചെയ്യുക

class TableBookingSerializer(serializers.ModelSerializer):
    class Meta:
        model = TableBooking
        fields = [
            'id', 'customer_name', 'phone_number', 'email', 
            'number_of_guests', 'booking_date', 'booking_time', 
            'special_request', 'status', 'created_at'
        ]
        read_only_fields = ['id', 'status', 'created_at']


class TableBookingAdminUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = TableBooking
        fields = ['status']