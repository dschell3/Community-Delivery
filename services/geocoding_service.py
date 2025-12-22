"""
Geocoding service for address validation, autocomplete, and distance calculations.
Uses Google Places API.
"""
import math
import requests
from flask import current_app


class GeocodingService:
    """Service for geocoding addresses and calculating distances."""
    
    GOOGLE_PLACES_AUTOCOMPLETE_URL = "https://maps.googleapis.com/maps/api/place/autocomplete/json"
    GOOGLE_PLACE_DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"
    GOOGLE_GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
    
    # Earth's radius in miles
    EARTH_RADIUS_MILES = 3959
    
    @classmethod
    def get_api_key(cls):
        """Get the Google Places API key."""
        key = current_app.config.get('GOOGLE_PLACES_API_KEY')
        if not key:
            raise ValueError("GOOGLE_PLACES_API_KEY not configured")
        return key
    
    @classmethod
    def get_service_area_center(cls):
        """Get the configured service area center point."""
        return (
            current_app.config.get('SERVICE_AREA_CENTER_LAT', 38.5816),
            current_app.config.get('SERVICE_AREA_CENTER_LNG', -121.4944)
        )
    
    @classmethod
    def get_service_area_radius(cls):
        """Get the configured service area radius in miles."""
        return current_app.config.get('SERVICE_AREA_RADIUS_MILES', 50)
    
    @classmethod
    def calculate_distance(cls, lat1, lng1, lat2, lng2):
        """
        Calculate distance between two points using Haversine formula.
        Returns distance in miles.
        """
        # Convert to radians
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lng = math.radians(lng2 - lng1)
        
        # Haversine formula
        a = math.sin(delta_lat / 2) ** 2 + \
            math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lng / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return cls.EARTH_RADIUS_MILES * c
    
    @classmethod
    def is_within_service_area(cls, latitude, longitude):
        """Check if a location is within the service area."""
        center_lat, center_lng = cls.get_service_area_center()
        radius = cls.get_service_area_radius()
        
        distance = cls.calculate_distance(center_lat, center_lng, latitude, longitude)
        return distance <= radius
    
    @classmethod
    def get_place_details(cls, place_id):
        """
        Get detailed information about a place from Google Places API.
        Returns dict with: name, address, latitude, longitude, types, place_id
        """
        try:
            response = requests.get(
                cls.GOOGLE_PLACE_DETAILS_URL,
                params={
                    'place_id': place_id,
                    'fields': 'name,formatted_address,geometry,types,place_id',
                    'key': cls.get_api_key()
                },
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get('status') != 'OK':
                current_app.logger.error(f"Place details error: {data.get('status')}")
                return None
            
            result = data.get('result', {})
            geometry = result.get('geometry', {}).get('location', {})
            
            return {
                'name': result.get('name', ''),
                'address': result.get('formatted_address', ''),
                'latitude': geometry.get('lat'),
                'longitude': geometry.get('lng'),
                'types': result.get('types', []),
                'place_id': result.get('place_id')
            }
            
        except requests.RequestException as e:
            current_app.logger.error(f"Google Places API error: {e}")
            return None
    
    @classmethod
    def geocode_address(cls, address):
        """
        Geocode an address string to coordinates.
        Returns dict with: address, latitude, longitude
        """
        try:
            center_lat, center_lng = cls.get_service_area_center()
            
            response = requests.get(
                cls.GOOGLE_GEOCODE_URL,
                params={
                    'address': address,
                    'key': cls.get_api_key(),
                    # Bias results toward Sacramento
                    'bounds': f"{center_lat - 1},{center_lng - 1}|{center_lat + 1},{center_lng + 1}"
                },
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get('status') != 'OK' or not data.get('results'):
                return None
            
            result = data['results'][0]
            location = result.get('geometry', {}).get('location', {})
            
            return {
                'address': result.get('formatted_address', address),
                'latitude': location.get('lat'),
                'longitude': location.get('lng')
            }
            
        except requests.RequestException as e:
            current_app.logger.error(f"Google Geocoding API error: {e}")
            return None
    
    @classmethod
    def validate_address_in_service_area(cls, place_id=None, address=None):
        """
        Validate that an address/place is within the service area.
        
        Args:
            place_id: Google Place ID (preferred)
            address: Address string (fallback)
        
        Returns:
            dict with: valid, address, latitude, longitude, error (if any)
        """
        location_data = None
        
        # Try place_id first
        if place_id:
            location_data = cls.get_place_details(place_id)
        
        # Fall back to address geocoding
        if not location_data and address:
            location_data = cls.geocode_address(address)
        
        if not location_data:
            return {
                'valid': False,
                'error': 'Could not find this address. Please try a different address.'
            }
        
        lat = location_data.get('latitude')
        lng = location_data.get('longitude')
        
        if lat is None or lng is None:
            return {
                'valid': False,
                'error': 'Could not determine location for this address.'
            }
        
        # Check if within service area
        if not cls.is_within_service_area(lat, lng):
            radius = cls.get_service_area_radius()
            return {
                'valid': False,
                'error': f'This address is outside our service area ({radius} miles from Sacramento).'
            }
        
        return {
            'valid': True,
            'name': location_data.get('name', ''),
            'address': location_data.get('address', address),
            'latitude': lat,
            'longitude': lng,
            'types': location_data.get('types', []),
            'place_id': location_data.get('place_id', place_id)
        }
    
    @classmethod
    def is_grocery_type(cls, place_types):
        """
        Check if place types indicate a grocery/food store.
        Returns True if any accepted type is present.
        """
        accepted_types = current_app.config.get('ACCEPTED_STORE_TYPES', {
            'grocery_or_supermarket',
            'supermarket', 
            'food',
            'store',
            'convenience_store',
            'drugstore',
            'department_store',
            'shopping_mall',
            'meal_delivery',
            'meal_takeaway',
        })
        
        return bool(set(place_types) & accepted_types)
    
    @classmethod
    def validate_store_address(cls, place_id=None, address=None):
        """
        Validate a store address for delivery requests.
        
        Returns:
            dict with: valid, needs_confirmation, name, address, latitude, longitude, error
        """
        result = cls.validate_address_in_service_area(place_id=place_id, address=address)
        
        if not result.get('valid'):
            return result
        
        # Check if it's a grocery-type store
        place_types = result.get('types', [])
        needs_confirmation = not cls.is_grocery_type(place_types)
        
        result['needs_confirmation'] = needs_confirmation
        return result
    
    @classmethod
    def get_fuzzy_coordinates(cls, latitude, longitude, decimals=2):
        """
        Round coordinates for privacy-preserving storage.
        2 decimal places ≈ 0.7 mile accuracy.
        """
        if latitude is None or longitude is None:
            return None, None
        
        return round(float(latitude), decimals), round(float(longitude), decimals)
