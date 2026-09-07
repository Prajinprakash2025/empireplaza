from rest_framework import serializers
from .models import SiteSetting


class SiteSettingSerializer(serializers.ModelSerializer):

    # Frontend variables -> Backend fields
    appName = serializers.CharField(
        source='restaurant_name',
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

    phone = serializers.CharField(
        source='phone_number',
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

    type_address = serializers.CharField(
        source='address_type',
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

    deliveryRadius = serializers.FloatField(
        source='delivery_radius',
        required=False,
        allow_null=True
    )

    footerDescription = serializers.CharField(
        source='footer_description',
        allow_blank=True,
        required=False,
        allow_null=True
    )

    # Automated Time & Manual Override
    openingTime = serializers.TimeField(
        source='opening_time',
        required=False,
        allow_null=True,
        format='%H:%M:%S',
        input_formats=['%H:%M:%S', '%H:%M']
    )

    closingTime = serializers.TimeField(
        source='closing_time',
        required=False,
        allow_null=True,
        format='%H:%M:%S',
        input_formats=['%H:%M:%S', '%H:%M']
    )

    isManuallyOpen = serializers.BooleanField(
        source='is_manually_open',
        required=False
    )

    isOpen = serializers.BooleanField(
        source='is_open',
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
            'email',
            'phone',
            'address',
            'type_address',
            'latitude',
            'longitude',
            'deliveryRadius',
            'footerDescription',
            'workingHours',
            'socials',
            'openingTime',
            'closingTime',
            'isManuallyOpen',
            'isOpen',
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

        return data

    # Frontend data -> Backend fields
    def update(self, instance, validated_data):

        working_hours = validated_data.pop(
            'workingHours',
            None
        )

        socials = validated_data.pop(
            'socials',
            None
        )

        # Update standard fields
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