from rest_framework import serializers
from .models import SiteSetting


class SiteSettingSerializer(serializers.ModelSerializer):

    # Frontend variables -> Backend fields (Support both camelCase and snake_case)
    appName = serializers.CharField(
        source='restaurant_name',
        required=False,
        allow_blank=True,
        allow_null=True
    )
    restaurant_name = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True
    )

    email = serializers.EmailField(
        source='email_address',
        required=False,
        allow_blank=True,
        allow_null=True
    )
    email_address = serializers.EmailField(
        required=False,
        allow_blank=True,
        allow_null=True
    )

    phone = serializers.CharField(
        source='phone_number',
        required=False,
        allow_blank=True,
        allow_null=True
    )
    phone_number = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True
    )

    address = serializers.CharField(
        source='physical_address',
        required=False,
        allow_blank=True,
        allow_null=True
    )
    physical_address = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True
    )

    type_address = serializers.CharField(
        source='address_type',
        required=False,
        allow_blank=True,
        allow_null=True
    )
    address_type = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True
    )

    # Coordinates
    latitude = serializers.DecimalField(
        max_digits=9,
        decimal_places=6,
        required=False,
        allow_null=True
    )

    longitude = serializers.DecimalField(
        max_digits=9,
        decimal_places=6,
        required=False,
        allow_null=True
    )

    # Delivery Radius (Support both camelCase and snake_case)
    deliveryRadius = serializers.FloatField(
        required=False,
        allow_null=True
    )
    delivery_radius = serializers.FloatField(
        required=False,
        allow_null=True
    )

    # Delivery Rates & Fees
    baseDeliveryCharge = serializers.DecimalField(
        max_digits=6,
        decimal_places=2,
        required=False,
        allow_null=True
    )
    base_delivery_charge = serializers.DecimalField(
        max_digits=6,
        decimal_places=2,
        required=False,
        allow_null=True
    )

    baseDeliveryDistance = serializers.FloatField(
        required=False,
        allow_null=True
    )
    base_delivery_distance = serializers.FloatField(
        required=False,
        allow_null=True
    )

    perKmCharge = serializers.DecimalField(
        max_digits=6,
        decimal_places=2,
        required=False,
        allow_null=True
    )
    per_km_charge = serializers.DecimalField(
        max_digits=6,
        decimal_places=2,
        required=False,
        allow_null=True
    )

    freeDeliveryThreshold = serializers.DecimalField(
        max_digits=8,
        decimal_places=2,
        required=False,
        allow_null=True
    )
    free_delivery_threshold = serializers.DecimalField(
        max_digits=8,
        decimal_places=2,
        required=False,
        allow_null=True
    )

    footerDescription = serializers.CharField(
        source='footer_description',
        allow_blank=True,
        required=False,
        allow_null=True
    )
    footer_description = serializers.CharField(
        allow_blank=True,
        required=False,
        allow_null=True
    )

    # Automated Time & Manual Override
    openingTime = serializers.TimeField(
        required=False,
        allow_null=True,
        format='%H:%M:%S',
        input_formats=['%H:%M:%S', '%H:%M']
    )
    opening_time = serializers.TimeField(
        required=False,
        allow_null=True,
        format='%H:%M:%S',
        input_formats=['%H:%M:%S', '%H:%M']
    )

    closingTime = serializers.TimeField(
        required=False,
        allow_null=True,
        format='%H:%M:%S',
        input_formats=['%H:%M:%S', '%H:%M']
    )
    closing_time = serializers.TimeField(
        required=False,
        allow_null=True,
        format='%H:%M:%S',
        input_formats=['%H:%M:%S', '%H:%M']
    )

    isManuallyOpen = serializers.BooleanField(
        required=False
    )
    is_manually_open = serializers.BooleanField(
        required=False
    )

    isCodEnabled = serializers.BooleanField(
        required=False
    )
    is_cod_enabled = serializers.BooleanField(
        required=False
    )

    isOpen = serializers.BooleanField(
        source='is_open',
        read_only=True
    )
    is_open = serializers.BooleanField(
        read_only=True
    )

    # Working Hours
    workingHours = serializers.DictField(
        child=serializers.CharField(
            allow_blank=True,
            allow_null=True
        ),
        write_only=True,
        required=False,
        allow_null=True
    )

    # Social Media
    socials = serializers.DictField(
        child=serializers.CharField(
            allow_blank=True,
            allow_null=True
        ),
        write_only=True,
        required=False,
        allow_null=True
    )

    class Meta:
        model = SiteSetting

        fields = [
            'appName',
            'restaurant_name',
            'email',
            'email_address',
            'phone',
            'phone_number',
            'address',
            'physical_address',
            'type_address',
            'address_type',
            'latitude',
            'longitude',
            'deliveryRadius',
            'delivery_radius',
            'baseDeliveryCharge',
            'base_delivery_charge',
            'baseDeliveryDistance',
            'base_delivery_distance',
            'perKmCharge',
            'per_km_charge',
            'freeDeliveryThreshold',
            'free_delivery_threshold',
            'footerDescription',
            'footer_description',
            'workingHours',
            'socials',
            'openingTime',
            'opening_time',
            'closingTime',
            'closing_time',
            'isManuallyOpen',
            'is_manually_open',
            'isOpen',
            'is_open',
            'isCodEnabled',
            'is_cod_enabled',
        ]

    # Backend data -> Frontend React format
    def to_representation(self, instance):
        data = super().to_representation(instance)

        data['workingHours'] = {
            'weekdays': (
                instance.working_hours_mon_sat
                if instance.working_hours_mon_sat
                else ""
            ),
            'sunday': (
                instance.working_hours_sunday
                if instance.working_hours_sunday
                else ""
            )
        }

        data['socials'] = {
            'instagram': (
                instance.instagram_url
                if instance.instagram_url
                else ""
            ),
            'facebook': (
                instance.facebook_url
                if instance.facebook_url
                else ""
            ),
            'twitter': (
                instance.twitter_url
                if instance.twitter_url
                else ""
            ),
            'whatsapp': (
                instance.whatsapp_url
                if instance.whatsapp_url
                else ""
            )
        }

        base_ch = float(instance.base_delivery_charge or 0.0)
        base_dist = float(instance.base_delivery_distance or 1.0)
        per_km = float(instance.per_km_charge or 0.0)
        free_thresh = float(instance.free_delivery_threshold) if instance.free_delivery_threshold is not None else None
        radius_val = float(instance.delivery_radius or 0.0)
        is_open_val = bool(instance.is_open)
        is_manual_val = bool(instance.is_manually_open)
        is_cod_val = bool(instance.is_cod_enabled)
        op_time = str(instance.opening_time) if instance.opening_time else None
        cl_time = str(instance.closing_time) if instance.closing_time else None

        # Expose both formats simultaneously for 100% frontend compatibility
        data['base_delivery_charge'] = base_ch
        data['baseDeliveryCharge'] = base_ch

        data['base_delivery_distance'] = base_dist
        data['baseDeliveryDistance'] = base_dist

        data['per_km_charge'] = per_km
        data['perKmCharge'] = per_km

        data['free_delivery_threshold'] = free_thresh
        data['freeDeliveryThreshold'] = free_thresh

        data['delivery_radius'] = radius_val
        data['deliveryRadius'] = radius_val

        data['is_open'] = is_open_val
        data['isOpen'] = is_open_val

        data['is_manually_open'] = is_manual_val
        data['isManuallyOpen'] = is_manual_val

        data['is_cod_enabled'] = is_cod_val
        data['isCodEnabled'] = is_cod_val

        data['opening_time'] = op_time
        data['openingTime'] = op_time

        data['closing_time'] = cl_time
        data['closingTime'] = cl_time

        return data

    # Frontend data -> Backend fields
    def update(self, instance, validated_data):

        working_hours = validated_data.pop('workingHours', None)
        socials = validated_data.pop('socials', None)

        # Handle delivery radius (either camelCase or snake_case)
        if 'delivery_radius' in validated_data:
            instance.delivery_radius = float(validated_data.pop('delivery_radius') or 0.0)
        elif 'deliveryRadius' in validated_data:
            instance.delivery_radius = float(validated_data.pop('deliveryRadius') or 0.0)

        # Handle base delivery charge
        if 'base_delivery_charge' in validated_data:
            instance.base_delivery_charge = validated_data.pop('base_delivery_charge')
        elif 'baseDeliveryCharge' in validated_data:
            instance.base_delivery_charge = validated_data.pop('baseDeliveryCharge')

        # Handle base distance
        if 'base_delivery_distance' in validated_data:
            instance.base_delivery_distance = float(validated_data.pop('base_delivery_distance') or 1.0)
        elif 'baseDeliveryDistance' in validated_data:
            instance.base_delivery_distance = float(validated_data.pop('baseDeliveryDistance') or 1.0)

        # Handle per KM charge
        if 'per_km_charge' in validated_data:
            instance.per_km_charge = validated_data.pop('per_km_charge')
        elif 'perKmCharge' in validated_data:
            instance.per_km_charge = validated_data.pop('perKmCharge')

        # Handle free delivery threshold
        if 'free_delivery_threshold' in validated_data:
            instance.free_delivery_threshold = validated_data.pop('free_delivery_threshold')
        elif 'freeDeliveryThreshold' in validated_data:
            instance.free_delivery_threshold = validated_data.pop('freeDeliveryThreshold')

        # Handle opening & closing times
        if 'opening_time' in validated_data:
            instance.opening_time = validated_data.pop('opening_time')
        elif 'openingTime' in validated_data:
            instance.opening_time = validated_data.pop('openingTime')

        if 'closing_time' in validated_data:
            instance.closing_time = validated_data.pop('closing_time')
        elif 'closingTime' in validated_data:
            instance.closing_time = validated_data.pop('closingTime')

        # Handle manual open
        if 'is_manually_open' in validated_data:
            instance.is_manually_open = validated_data.pop('is_manually_open')
        elif 'isManuallyOpen' in validated_data:
            instance.is_manually_open = validated_data.pop('isManuallyOpen')

        # Handle COD
        if 'is_cod_enabled' in validated_data:
            instance.is_cod_enabled = validated_data.pop('is_cod_enabled')
        elif 'isCodEnabled' in validated_data:
            instance.is_cod_enabled = validated_data.pop('isCodEnabled')

        # Handle restaurant name / appName
        if 'restaurant_name' in validated_data:
            instance.restaurant_name = validated_data.pop('restaurant_name')
        elif 'appName' in validated_data:
            instance.restaurant_name = validated_data.pop('appName')

        # Handle email
        if 'email_address' in validated_data:
            instance.email_address = validated_data.pop('email_address')
        elif 'email' in validated_data:
            instance.email_address = validated_data.pop('email')

        # Handle phone
        if 'phone_number' in validated_data:
            instance.phone_number = validated_data.pop('phone_number')
        elif 'phone' in validated_data:
            instance.phone_number = validated_data.pop('phone')

        # Handle address
        if 'physical_address' in validated_data:
            instance.physical_address = validated_data.pop('physical_address')
        elif 'address' in validated_data:
            instance.physical_address = validated_data.pop('address')

        # Handle address type
        if 'address_type' in validated_data:
            instance.address_type = validated_data.pop('address_type')
        elif 'type_address' in validated_data:
            instance.address_type = validated_data.pop('type_address')

        # Handle footer description
        if 'footer_description' in validated_data:
            instance.footer_description = validated_data.pop('footer_description')
        elif 'footerDescription' in validated_data:
            instance.footer_description = validated_data.pop('footerDescription')

        # Update any remaining standard fields (e.g. latitude, longitude)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # Update working hours
        if working_hours:
            instance.working_hours_mon_sat = working_hours.get(
                'weekdays',
                instance.working_hours_mon_sat
            )
            instance.working_hours_sunday = working_hours.get(
                'sunday',
                instance.working_hours_sunday
            )

        # Update social media
        if socials:
            instance.instagram_url = socials.get(
                'instagram',
                instance.instagram_url
            )
            instance.facebook_url = socials.get(
                'facebook',
                instance.facebook_url
            )
            instance.twitter_url = socials.get(
                'twitter',
                instance.twitter_url
            )
            instance.whatsapp_url = socials.get(
                'whatsapp',
                instance.whatsapp_url
            )

        instance.save()

        return instance