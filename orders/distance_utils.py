import math
import urllib.request
import urllib.parse
import json
from decimal import Decimal


def calculate_haversine_distance_km(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance between two GPS coordinates
    in decimal degrees, multiplied by a road route factor (~1.2x).
    """
    if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
        return 0.0

    try:
        lat1, lon1, lat2, lon2 = float(lat1), float(lon1), float(lat2), float(lon2)
        if (lat1 == 0.0 and lon1 == 0.0) or (lat2 == 0.0 and lon2 == 0.0):
            return 0.0
    except (ValueError, TypeError):
        return 0.0

    # Radius of earth in kilometers
    R = 6371.0

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    aerial_km = R * c

    # Road route winding factor (~1.2x in Kerala/Indian road networks)
    road_km = round(aerial_km * 1.2, 1)
    return max(road_km, 0.5)


def calculate_delivery_fee(distance_km, items_subtotal=Decimal('0.00'), site_settings=None):
    """
    Calculates delivery fee based on calculated distance and SiteSetting rules:
    - Free delivery if items_subtotal >= free_delivery_threshold (if configured)
    - Base charge for distance <= base_delivery_distance
    - Base charge + (extra_km * per_km_charge) for distance > base_delivery_distance
    """
    # Guard against accidental argument order swap (e.g. dist_km, site_settings, subtotal)
    if site_settings is not None and hasattr(items_subtotal, 'delivery_radius'):
        real_settings = items_subtotal
        real_subtotal = site_settings if isinstance(site_settings, (int, float, Decimal, str)) else Decimal('0.00')
        site_settings = real_settings
        items_subtotal = real_subtotal

    if not isinstance(items_subtotal, Decimal):
        try:
            items_subtotal = Decimal(str(items_subtotal or '0.00'))
        except Exception:
            items_subtotal = Decimal('0.00')

    if not site_settings:
        return Decimal('30.00')

    # 1. Free delivery threshold check
    free_threshold = getattr(site_settings, 'free_delivery_threshold', None)
    if free_threshold is not None and items_subtotal >= free_threshold:
        return Decimal('0.00')

    base_charge = Decimal(str(getattr(site_settings, 'base_delivery_charge', 20.00) or 20.00))
    base_dist = float(getattr(site_settings, 'base_delivery_distance', 1.0) or 1.0)
    per_km = Decimal(str(getattr(site_settings, 'per_km_charge', 10.00) or 10.00))

    if distance_km <= 0.0:
        # Fallback to base charge if location was not provided
        return base_charge

    if distance_km <= base_dist:
        return base_charge

    extra_km = Decimal(str(round(distance_km - base_dist, 1)))
    extra_charge = extra_km * per_km
    total_fee = base_charge + extra_charge
    return round(total_fee, 2)


def geocode_address(address_line="", city="", pincode=""):
    """
    Attempt to find lat/lng coordinates for an address using OSM Nominatim.
    Falls back gracefully if network or rate limit.
    """
    queries = []
    pincode_clean = str(pincode or "").strip()
    city_clean = str(city or "").strip()
    addr_clean = str(address_line or "").strip()

    if pincode_clean:
        queries.append(f"{pincode_clean}, India")
    if city_clean and pincode_clean:
        queries.append(f"{city_clean} {pincode_clean}, Kerala, India")
    if addr_clean and city_clean:
        queries.append(f"{addr_clean}, {city_clean}, Kerala, India")
    elif city_clean:
        queries.append(f"{city_clean}, Kerala, India")

    for q in queries:
        try:
            url = f"https://nominatim.openstreetmap.org/search?format=json&q={urllib.parse.quote(q)}&limit=1"
            req = urllib.request.Request(
                url,
                headers={'User-Agent': 'GrandPlaza-Delivery-Service/1.0 (info@grandeplaza.com)'}
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                if data and len(data) > 0:
                    return float(data[0]['lat']), float(data[0]['lon'])
        except Exception:
            continue

    return None, None
