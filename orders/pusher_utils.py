import pusher
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

_pusher_client = None

def get_pusher_client():
    global _pusher_client
    if _pusher_client is None:
        try:
            app_id = getattr(settings, 'PUSHER_APP_ID', '')
            key = getattr(settings, 'PUSHER_KEY', '')
            secret = getattr(settings, 'PUSHER_SECRET', '')
            cluster = getattr(settings, 'PUSHER_CLUSTER', 'ap2')

            if app_id and key and secret:
                _pusher_client = pusher.Pusher(
                    app_id=str(app_id),
                    key=str(key),
                    secret=str(secret),
                    cluster=str(cluster),
                    ssl=True
                )
        except Exception as e:
            logger.error(f"Failed to initialize Pusher client: {e}")
            return None
    return _pusher_client


def sanitize_order_payload(data: dict) -> dict:
    """
    F03 FIX: Redacts customer PII before broadcasting on shared/public channels.
    Strips raw customer phone number, full street address, and exact coordinates.
    Authorized clients fetch complete order records through authenticated REST API endpoints.
    """
    if not isinstance(data, dict):
        return data

    sanitized = dict(data)

    # Redact customer phone
    if 'customer_phone' in sanitized and sanitized['customer_phone']:
        phone = str(sanitized['customer_phone'])
        sanitized['customer_phone'] = f"******{phone[-4:]}" if len(phone) >= 4 else "******"

    # Redact customer street address
    if 'delivery_address' in sanitized and sanitized['delivery_address']:
        parts = str(sanitized['delivery_address']).split(',')
        sanitized['delivery_address'] = parts[-2].strip() if len(parts) >= 2 else "Delivery Address Protected"

    # Redact customer GPS coordinates from public stream
    if 'delivery_latitude' in sanitized:
        sanitized['delivery_latitude'] = None
    if 'delivery_longitude' in sanitized:
        sanitized['delivery_longitude'] = None

    if 'special_instructions' in sanitized:
        sanitized['special_instructions'] = ''

    return sanitized


def trigger_order_event(event_name: str, data: dict, channel_name: str = 'orders-channel'):
    """
    Safely trigger real-time order events via Pusher.
    Wrapped in try-except so real-time notification issues never break DB transactions.
    Automatically sanitizes customer PII for shared channels.
    """
    try:
        client = get_pusher_client()
        if client:
            payload = sanitize_order_payload(data) if channel_name == 'orders-channel' else data
            client.trigger(channel_name, event_name, payload)
            logger.info(f"Pusher event '{event_name}' dispatched successfully to '{channel_name}'.")
    except Exception as e:
        logger.warning(f"Pusher trigger '{event_name}' error: {e}")
