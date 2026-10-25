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
    F03 FIX: Redacts customer PII and rider GPS before broadcasting on shared/public channels.
    Strips raw customer/rider phone numbers, full street address, and live GPS coordinates.
    Authorized clients fetch complete telemetry through authenticated REST API endpoints.
    """
    if not isinstance(data, dict):
        return data

    sanitized = dict(data)

    # 0. Redact Customer Name from public real-time events (I04 fix)
    if 'customer_name' in sanitized:
        sanitized.pop('customer_name', None)

    # 1. Mask Customer & Rider Phone Numbers
    if 'customer_phone' in sanitized and sanitized['customer_phone']:
        phone = str(sanitized['customer_phone'])
        sanitized['customer_phone'] = f"******{phone[-4:]}" if len(phone) >= 4 else "******"

    if 'phone' in sanitized and sanitized['phone']:
        phone = str(sanitized['phone'])
        sanitized['phone'] = f"******{phone[-4:]}" if len(phone) >= 4 else "******"

    if isinstance(sanitized.get('delivery_boy'), dict):
        db = dict(sanitized['delivery_boy'])
        if db.get('phone'):
            phone = str(db['phone'])
            db['phone'] = f"******{phone[-4:]}" if len(phone) >= 4 else "******"
        db['latitude'] = None
        db['longitude'] = None
        sanitized['delivery_boy'] = db

    # 2. Redact Delivery Address
    if 'delivery_address' in sanitized and sanitized['delivery_address']:
        parts = str(sanitized['delivery_address']).split(',')
        sanitized['delivery_address'] = parts[-2].strip() if len(parts) >= 2 else "Delivery Address Protected"

    # 3. Redact ALL GPS Coordinates from Public Streams (Customer & Rider)
    for coord_key in ['latitude', 'longitude', 'delivery_latitude', 'delivery_longitude']:
        if coord_key in sanitized:
            sanitized[coord_key] = None

    if 'active_order_ids' in sanitized:
        sanitized['active_order_ids'] = []

    if 'special_instructions' in sanitized:
        sanitized['special_instructions'] = ''

    return sanitized


def trigger_order_event(event_name: str, data: dict, channel_name: str = 'orders-channel'):
    """
    Safely trigger real-time order events via Pusher.
    Wrapped in try-except so real-time notification issues never break DB transactions.
    Automatically sanitizes customer PII and rider GPS telemetry for shared channels.
    """
    try:
        client = get_pusher_client()
        if client:
            payload = sanitize_order_payload(data) if channel_name == 'orders-channel' else data
            client.trigger(channel_name, event_name, payload)
            logger.info(f"Pusher event '{event_name}' dispatched successfully to '{channel_name}'.")
    except Exception as e:
        logger.warning(f"Pusher trigger '{event_name}' error: {e}")
