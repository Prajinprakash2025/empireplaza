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

def trigger_order_event(event_name: str, data: dict):
    """
    Safely trigger real-time order events via Pusher.
    Wrapped in try-except so real-time notification issues never break DB transactions.
    """
    try:
        client = get_pusher_client()
        if client:
            client.trigger('orders-channel', event_name, data)
            logger.info(f"Pusher event '{event_name}' dispatched successfully.")
    except Exception as e:
        logger.warning(f"Pusher trigger '{event_name}' error: {e}")
