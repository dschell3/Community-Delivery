from datetime import datetime
from flask import current_app

from app import db


class Recipient(db.Model):
    """Recipient profile with encrypted sensitive data."""
    __tablename__ = 'recipients'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    display_name = db.Column(db.String(100), nullable=False)
    address_encrypted = db.Column(db.Text, nullable=False)
    phone_encrypted = db.Column(db.String(255), nullable=True)
    general_area = db.Column(db.String(100), nullable=True)  # Non-sensitive area for matching
    notes_encrypted = db.Column(db.Text, nullable=True)  # Delivery instructions
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    deleted_at = db.Column(db.DateTime, nullable=True, index=True)
    
    # Relationships
    deliveries = db.relationship('Delivery', backref='recipient', lazy='dynamic')
    ratings_given = db.relationship('Rating', backref='recipient', lazy='dynamic')
    
    @property
    def is_deleted(self):
        return self.deleted_at is not None
    
    def get_address(self, encryption_service):
        """Decrypt and return address."""
        if self.address_encrypted == '[PURGED]':
            return None
        return encryption_service.decrypt(self.address_encrypted)
    
    def set_address(self, address, encryption_service):
        """Encrypt and store address."""
        self.address_encrypted = encryption_service.encrypt(address)
    
    def get_phone(self, encryption_service):
        """Decrypt and return phone."""
        if not self.phone_encrypted:
            return None
        return encryption_service.decrypt(self.phone_encrypted)
    
    def set_phone(self, phone, encryption_service):
        """Encrypt and store phone."""
        if phone:
            self.phone_encrypted = encryption_service.encrypt(phone)
        else:
            self.phone_encrypted = None
    
    def get_notes(self, encryption_service):
        """Decrypt and return delivery notes."""
        if not self.notes_encrypted:
            return None
        return encryption_service.decrypt(self.notes_encrypted)
    
    def set_notes(self, notes, encryption_service):
        """Encrypt and store delivery notes."""
        if notes:
            self.notes_encrypted = encryption_service.encrypt(notes)
        else:
            self.notes_encrypted = None
    
    @property
    def active_delivery(self):
        """Get current active delivery request if any."""
        return self.deliveries.filter(
            Delivery.status.in_(['open', 'claimed', 'picked_up'])
        ).first()
    
    def __repr__(self):
        return f'<Recipient {self.display_name}>'


class RecipientTombstone(db.Model):
    """Preserved record of deleted recipients for audit purposes."""
    __tablename__ = 'recipient_tombstones'
    
    id = db.Column(db.Integer, primary_key=True)  # Original recipient ID
    volunteer_ids = db.Column(db.JSON, nullable=False)  # Array of volunteer IDs who had access
    last_active_date = db.Column(db.Date, nullable=False)
    deleted_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    @classmethod
    def create_from_recipient(cls, recipient):
        """Create tombstone from a recipient being deleted."""
        from models.delivery import Delivery
        
        # Get all volunteer IDs who interacted with this recipient
        volunteer_ids = db.session.query(Delivery.volunteer_id).filter(
            Delivery.recipient_id == recipient.id,
            Delivery.volunteer_id.isnot(None)
        ).distinct().all()
        volunteer_ids = [v[0] for v in volunteer_ids]
        
        last_active = recipient.user.last_active or recipient.created_at
        
        tombstone = cls(
            id=recipient.id,
            volunteer_ids=volunteer_ids,
            last_active_date=last_active.date()
        )
        return tombstone
    
    def __repr__(self):
        return f'<RecipientTombstone {self.id}>'


# Import at bottom to avoid circular imports
from models.delivery import Delivery
