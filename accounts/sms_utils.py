import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

def send_2factor_otp(phone_number: str, otp_code: str) -> bool:
    """
    Sends a 6-digit OTP SMS via 2Factor.in API using pre-approved OTP1 template.
    """
    api_key = getattr(settings, 'TWOFACTOR_API_KEY', 'b6e4bcf9-bdc3-11f1-af74-0200cd936042')
    if not api_key:
        logger.warning("TWOFACTOR_API_KEY not configured. Skipping SMS.")
        return False

    # Clean phone number: strip non-digits and take last 10 digits
    clean_phone = ''.join(filter(str.isdigit, str(phone_number)))[-10:]
    if len(clean_phone) != 10:
        logger.error(f"Invalid phone number for SMS OTP: {phone_number}")
        return False

    url = f"https://2factor.in/API/V1/{api_key}/SMS/{clean_phone}/{otp_code}/OTP1"

    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        if data.get("Status") == "Success":
            logger.info(f"2Factor OTP SMS sent successfully to {clean_phone}. Details: {data.get('Details')}")
            return True
        else:
            logger.error(f"2Factor error response for {clean_phone}: {data.get('Details')}")
            return False
    except Exception as e:
        logger.error(f"Failed to connect to 2Factor API for {clean_phone}: {e}")
        return False
