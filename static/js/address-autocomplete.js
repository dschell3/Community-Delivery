/**
 * Address Autocomplete Component using Google Places API
 * 
 * Usage:
 *   <input type="text" id="address" data-autocomplete="address">
 *   <input type="hidden" id="address_place_id" name="address_place_id">
 *   <input type="hidden" id="address_lat" name="address_lat">
 *   <input type="hidden" id="address_lng" name="address_lng">
 * 
 * For stores (with name extraction):
 *   <input type="text" id="store" data-autocomplete="store">
 *   <input type="hidden" id="store_name" name="store_name">
 *   <input type="hidden" id="store_place_id" name="store_place_id">
 *   ...
 */

// Service area configuration - set by template
window.SERVICE_AREA_CONFIG = window.SERVICE_AREA_CONFIG || {
    centerLat: 38.5816,
    centerLng: -121.4944,
    radiusMiles: 50
};


/**
 * Calculate distance between two points using Haversine formula
 * @returns {number} Distance in miles
 */
function calculateDistance(lat1, lng1, lat2, lng2) {
    const R = 3959; // Earth's radius in miles
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLng = (lng2 - lng1) * Math.PI / 180;
    const a = 
        Math.sin(dLat / 2) * Math.sin(dLat / 2) +
        Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
        Math.sin(dLng / 2) * Math.sin(dLng / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return R * c;
}


/**
 * Check if coordinates are within service area
 * @returns {object} { valid: boolean, distance: number }
 */
function isWithinServiceArea(lat, lng) {
    const config = window.SERVICE_AREA_CONFIG;
    const distance = calculateDistance(
        config.centerLat, config.centerLng,
        lat, lng
    );
    return {
        valid: distance <= config.radiusMiles,
        distance: Math.round(distance)
    };
}


class AddressAutocomplete {
    constructor(inputElement, options = {}) {
        this.input = inputElement;
        this.options = {
            // Bias results to Sacramento area
            bounds: {
                north: 39.5,
                south: 37.5,
                east: -120.5,
                west: -122.5
            },
            componentRestrictions: { country: 'us' },
            fields: ['place_id', 'formatted_address', 'geometry', 'name', 'types'],
            ...options
        };
        
        // Whether to validate service area (default true for addresses, can disable for stores)
        this.validateServiceArea = options.validateServiceArea !== false;
        
        this.autocomplete = null;
        this.placeData = null;
        
        // Find associated hidden fields
        const baseId = this.input.id;
        this.placeIdField = document.getElementById(`${baseId}_place_id`);
        this.latField = document.getElementById(`${baseId}_lat`);
        this.lngField = document.getElementById(`${baseId}_lng`);
        this.nameField = document.getElementById(`${baseId}_name`);
        this.typesField = document.getElementById(`${baseId}_types`);
        
        // Error display element
        this.errorElement = document.getElementById(`${baseId}_error`);
        
        this.init();
    }
    
    init() {
        // Initialize Google Places Autocomplete
        this.autocomplete = new google.maps.places.Autocomplete(
            this.input,
            this.options
        );
        
        // Listen for place selection
        this.autocomplete.addListener('place_changed', () => this.onPlaceChanged());
        
        // Clear hidden fields when user types (invalidates previous selection)
        this.input.addEventListener('input', () => this.clearPlaceData());
        
        // Prevent form submission on Enter (let autocomplete complete first)
        this.input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                // If autocomplete dropdown is open, prevent form submit
                const pacContainer = document.querySelector('.pac-container');
                if (pacContainer && pacContainer.style.display !== 'none') {
                    e.preventDefault();
                }
            }
        });
    }
    
    onPlaceChanged() {
        const place = this.autocomplete.getPlace();
        
        if (!place.geometry) {
            // User entered text that doesn't match a place
            this.clearPlaceData();
            this.showError('Please select an address from the dropdown.');
            return;
        }
        
        const lat = place.geometry.location.lat();
        const lng = place.geometry.location.lng();
        
        // Validate service area if enabled
        if (this.validateServiceArea) {
            const areaCheck = isWithinServiceArea(lat, lng);
            if (!areaCheck.valid) {
                this.clearPlaceData();
                this.showError(
                    `This address is approximately ${areaCheck.distance} miles away, ` +
                    `outside our ${window.SERVICE_AREA_CONFIG.radiusMiles}-mile service area. ` +
                    `Please enter an address closer to the Sacramento area.`
                );
                // Clear the input so user knows to try again
                this.input.value = '';
                this.input.focus();
                return;
            }
        }
        
        this.placeData = {
            placeId: place.place_id,
            name: place.name || '',
            address: place.formatted_address,
            lat: lat,
            lng: lng,
            types: place.types || []
        };
        
        // Populate hidden fields
        if (this.placeIdField) {
            this.placeIdField.value = this.placeData.placeId;
        }
        if (this.latField) {
            this.latField.value = this.placeData.lat;
        }
        if (this.lngField) {
            this.lngField.value = this.placeData.lng;
        }
        if (this.nameField) {
            this.nameField.value = this.placeData.name;
        }
        if (this.typesField) {
            this.typesField.value = JSON.stringify(this.placeData.types);
        }
        
        // Clear any previous error
        this.hideError();
        
        // Trigger custom event for additional handling
        const event = new CustomEvent('placeSelected', { 
            detail: this.placeData 
        });
        this.input.dispatchEvent(event);
    }
    
    clearPlaceData() {
        this.placeData = null;
        
        if (this.placeIdField) this.placeIdField.value = '';
        if (this.latField) this.latField.value = '';
        if (this.lngField) this.lngField.value = '';
        if (this.nameField) this.nameField.value = '';
        if (this.typesField) this.typesField.value = '';
    }
    
    showError(message) {
        if (this.errorElement) {
            this.errorElement.textContent = message;
            this.errorElement.style.display = 'block';
        }
        this.input.classList.add('input-error');
    }
    
    hideError() {
        if (this.errorElement) {
            this.errorElement.textContent = '';
            this.errorElement.style.display = 'none';
        }
        this.input.classList.remove('input-error');
    }
    
    hasValidPlace() {
        return this.placeData !== null;
    }
    
    getPlaceData() {
        return this.placeData;
    }
}


/**
 * Store Autocomplete - extends AddressAutocomplete with store-specific features
 */
class StoreAutocomplete extends AddressAutocomplete {
    constructor(inputElement, options = {}) {
        // For stores, bias toward establishments
        // Stores also need service area validation
        const storeOptions = {
            types: ['establishment'],
            validateServiceArea: true,  // Stores must also be in service area
            ...options
        };
        
        super(inputElement, storeOptions);
        
        // Grocery-like store types (no confirmation needed)
        this.acceptedTypes = new Set([
            'grocery_or_supermarket',
            'supermarket',
            'food',
            'store',
            'convenience_store',
            'drugstore',
            'department_store',
            'shopping_mall',
            'meal_delivery',
            'meal_takeaway'
        ]);
        
        // Find confirmation elements
        const baseId = this.input.id;
        this.confirmationModal = document.getElementById(`${baseId}_confirmation`);
        this.confirmButton = document.getElementById(`${baseId}_confirm_btn`);
        this.cancelButton = document.getElementById(`${baseId}_cancel_btn`);
        this.storeTypeDisplay = document.getElementById(`${baseId}_type_display`);
        
        this.pendingConfirmation = false;
        
        this.setupConfirmation();
    }
    
    setupConfirmation() {
        if (this.confirmButton) {
            this.confirmButton.addEventListener('click', () => {
                this.pendingConfirmation = false;
                this.hideConfirmation();
                // Trigger confirmed event
                const event = new CustomEvent('storeConfirmed', { 
                    detail: this.placeData 
                });
                this.input.dispatchEvent(event);
            });
        }
        
        if (this.cancelButton) {
            this.cancelButton.addEventListener('click', () => {
                this.pendingConfirmation = false;
                this.hideConfirmation();
                this.clearPlaceData();
                this.input.value = '';
                this.input.focus();
            });
        }
    }
    
    onPlaceChanged() {
        // Call parent which handles service area validation
        super.onPlaceChanged();
        
        // If no valid place data (e.g., outside service area), stop
        if (!this.placeData) return;
        
        // Check if this is a grocery-type store
        const placeTypes = new Set(this.placeData.types);
        const isGroceryType = [...placeTypes].some(t => this.acceptedTypes.has(t));
        
        if (!isGroceryType) {
            // Show confirmation dialog
            this.showConfirmation();
        }
    }
    
    showConfirmation() {
        if (this.confirmationModal) {
            this.pendingConfirmation = true;
            
            // Display the store name
            if (this.storeTypeDisplay) {
                this.storeTypeDisplay.textContent = this.placeData.name || 'This location';
            }
            
            this.confirmationModal.style.display = 'block';
        }
    }
    
    hideConfirmation() {
        if (this.confirmationModal) {
            this.confirmationModal.style.display = 'none';
        }
    }
    
    needsConfirmation() {
        return this.pendingConfirmation;
    }
}


/**
 * Initialize all autocomplete fields on page load
 */
function initAddressAutocomplete() {
    // Standard address autocomplete
    document.querySelectorAll('[data-autocomplete="address"]').forEach(input => {
        new AddressAutocomplete(input);
    });
    
    // Store autocomplete (with confirmation for non-grocery)
    document.querySelectorAll('[data-autocomplete="store"]').forEach(input => {
        new StoreAutocomplete(input);
    });
}


/**
 * Form validation helper - ensure addresses are selected from autocomplete
 */
function validateAddressFields(form) {
    let valid = true;
    
    form.querySelectorAll('[data-autocomplete]').forEach(input => {
        const placeIdField = document.getElementById(`${input.id}_place_id`);
        
        // If there's text in the input but no place_id, invalid
        if (input.value.trim() && (!placeIdField || !placeIdField.value)) {
            const instance = input._autocompleteInstance;
            if (instance) {
                instance.showError('Please select an address from the dropdown.');
            }
            valid = false;
        }
    });
    
    return valid;
}


// Initialize when Google Maps API is loaded
function initGoogleMapsCallback() {
    initAddressAutocomplete();
}

// Also try to init on DOMContentLoaded (if API already loaded)
document.addEventListener('DOMContentLoaded', function() {
    if (window.google && window.google.maps && window.google.maps.places) {
        initAddressAutocomplete();
    }
});