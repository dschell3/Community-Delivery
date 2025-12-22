from datetime import datetime

from app import db


class Delivery(db.Model):
    """Core delivery coordination record."""
    __tablename__ = 'deliveries'
    
    id = db.Column(db.Integer, primary_key=True)
    recipient_id = db.Column(db.Integer, db.ForeignKey('recipients.id'), nullable=False)
    volunteer_id = db.Column(db.Integer, db.ForeignKey('volunteers.id'), nullable=True)
    
    # Store/Pickup details
    store_name = db.Column(db.String(255), nullable=False)
    pickup_address = db.Column(db.String(500), nullable=False)  # Store address (not sensitive)
    store_place_id = db.Column(db.String(255), nullable=True)   # Google Place ID for reference
    store_latitude = db.Column(db.Numeric(8, 5), nullable=True, index=True)
    store_longitude = db.Column(db.Numeric(9, 5), nullable=True, index=True)
    
    order_name = db.Column(db.String(255), nullable=False)  # Name the order is under
    pickup_time = db.Column(db.DateTime, nullable=False)
    estimated_items = db.Column(db.String(100), nullable=True)  # "About 10 items", "2 bags"
    
    # Status tracking
    status = db.Column(
        db.Enum('open', 'claimed', 'picked_up', 'completed', 'canceled'),
        default='open',
        index=True
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    claimed_at = db.Column(db.DateTime, nullable=True)
    picked_up_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    canceled_at = db.Column(db.DateTime, nullable=True)
    canceled_by = db.Column(
        db.Enum('recipient', 'volunteer', 'admin', 'system'),
        nullable=True
    )
    cancellation_reason = db.Column(db.Text, nullable=True)
    
    # Priority for re-queued deliveries
    priority = db.Column(db.Integer, default=0, index=True)  # Higher = shows first
    
    # Relationships
    messages = db.relationship('Message', backref='delivery', lazy='dynamic', cascade='all, delete-orphan')
    rating = db.relationship('Rating', backref='delivery', uselist=False, cascade='all, delete-orphan')
    
    @property
    def is_open(self):
        return self.status == 'open'
    
    @property
    def is_claimed(self):
        return self.status == 'claimed'
    
    @property
    def is_picked_up(self):
        return self.status == 'picked_up'
    
    @property
    def is_completed(self):
        return self.status == 'completed'
    
    @property
    def is_canceled(self):
        return self.status == 'canceled'
    
    @property
    def is_active(self):
        """Is this delivery currently in progress?"""
        return self.status in ['open', 'claimed', 'picked_up']
    
    @property
    def can_be_claimed(self):
        return self.status == 'open'
    
    @property
    def can_be_canceled(self):
        return self.status in ['open', 'claimed', 'picked_up']
    
    def set_store_location(self, latitude, longitude, place_id=None):
        """Set the store's location."""
        if latitude is not None and longitude is not None:
            self.store_latitude = float(latitude)
            self.store_longitude = float(longitude)
        if place_id:
            self.store_place_id = place_id
    
    def claim(self, volunteer):
        """Claim this delivery for a volunteer."""
        if not self.can_be_claimed:
            raise ValueError("Delivery cannot be claimed in current state")
        if not volunteer.can_claim_delivery():
            raise ValueError("Volunteer cannot claim more deliveries")
        
        self.volunteer_id = volunteer.id
        self.status = 'claimed'
        self.claimed_at = datetime.utcnow()
        db.session.commit()
    
    def mark_picked_up(self):
        """Mark groceries as picked up from store."""
        if self.status != 'claimed':
            raise ValueError("Delivery must be claimed before marking picked up")
        
        self.status = 'picked_up'
        self.picked_up_at = datetime.utcnow()
        db.session.commit()
    
    def complete(self):
        """Mark delivery as completed."""
        if self.status not in ['claimed', 'picked_up']:
            raise ValueError("Delivery must be claimed or picked up to complete")
        
        self.status = 'completed'
        self.completed_at = datetime.utcnow()
        
        # Update volunteer stats
        if self.volunteer:
            self.volunteer.total_deliveries += 1
        
        db.session.commit()
    
    def cancel(self, canceled_by, reason=None, return_to_pool=True):
        """Cancel this delivery."""
        if not self.can_be_canceled:
            raise ValueError("Delivery cannot be canceled in current state")
        
        old_status = self.status
        self.status = 'canceled'
        self.canceled_at = datetime.utcnow()
        self.canceled_by = canceled_by
        self.cancellation_reason = reason
        
        # Clear volunteer assignment
        self.volunteer_id = None
        self.claimed_at = None
        self.picked_up_at = None
        
        db.session.commit()
        
        # Optionally re-open as new delivery with high priority
        if return_to_pool and old_status in ['claimed', 'picked_up']:
            self.reopen_with_priority()
    
    def reopen_with_priority(self):
        """Reopen a canceled delivery with higher priority."""
        self.status = 'open'
        self.priority = self.priority + 10  # Boost priority
        self.canceled_at = None
        self.canceled_by = None
        self.cancellation_reason = None
        db.session.commit()
    
    def release_claim(self, reason=None):
        """Volunteer releases their claim, returning delivery to pool."""
        if self.status not in ['claimed', 'picked_up']:
            raise ValueError("No claim to release")
        
        self.volunteer_id = None
        self.status = 'open'
        self.claimed_at = None
        self.picked_up_at = None
        self.priority = self.priority + 5  # Boost priority
        db.session.commit()
    
    @classmethod
    def get_available_for_volunteer(cls, volunteer):
        """Get available deliveries within volunteer's service area."""
        from services.geocoding_service import GeocodingService
        
        if not volunteer.has_service_location:
            # Volunteer hasn't set up service area yet
            return []
        
        # Get all open deliveries
        open_deliveries = cls.query.filter(cls.status == 'open').all()
        
        # Filter by distance to both store and recipient
        available = []
        for delivery in open_deliveries:
            # Check store distance
            if delivery.store_latitude and delivery.store_longitude:
                store_distance = GeocodingService.calculate_distance(
                    float(volunteer.service_center_lat),
                    float(volunteer.service_center_lng),
                    float(delivery.store_latitude),
                    float(delivery.store_longitude)
                )
                if store_distance > volunteer.service_radius_miles:
                    continue
            
            # Check recipient distance
            recipient = delivery.recipient
            if recipient.latitude and recipient.longitude:
                recipient_distance = GeocodingService.calculate_distance(
                    float(volunteer.service_center_lat),
                    float(volunteer.service_center_lng),
                    float(recipient.latitude),
                    float(recipient.longitude)
                )
                if recipient_distance > volunteer.service_radius_miles:
                    continue
            
            available.append(delivery)
        
        # Sort by priority (descending) then created_at (ascending)
        available.sort(key=lambda d: (-d.priority, d.created_at))
        
        return available
    
    def __repr__(self):
        return f'<Delivery {self.id} ({self.status})>'


# Import at bottom to avoid circular imports  
from models.recipient import Recipient
