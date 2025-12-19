from datetime import datetime

from app import db


class AuditLog(db.Model):
    """Audit log tracking relationships and actions (no sensitive data)."""
    __tablename__ = 'audit_log'
    
    id = db.Column(db.Integer, primary_key=True)
    volunteer_id = db.Column(db.Integer, nullable=True, index=True)
    recipient_id = db.Column(db.Integer, nullable=True, index=True)
    delivery_id = db.Column(db.Integer, nullable=True, index=True)
    admin_id = db.Column(db.Integer, nullable=True)
    action = db.Column(db.String(100), nullable=False, index=True)
    details = db.Column(db.JSON, nullable=True)  # Non-sensitive metadata
    ip_address = db.Column(db.String(45), nullable=True)  # IPv4 or IPv6
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    # Action constants
    # Volunteer actions
    VOLUNTEER_REGISTERED = 'volunteer_registered'
    VOLUNTEER_APPROVED = 'volunteer_approved'
    VOLUNTEER_REJECTED = 'volunteer_rejected'
    VOLUNTEER_SUSPENDED = 'volunteer_suspended'
    
    # Delivery actions
    DELIVERY_CREATED = 'delivery_created'
    DELIVERY_CLAIMED = 'delivery_claimed'
    DELIVERY_CANCELED = 'delivery_canceled'
    DELIVERY_PICKED_UP = 'delivery_picked_up'
    DELIVERY_COMPLETED = 'delivery_completed'
    
    # Communication
    MESSAGE_SENT = 'message_sent'
    ADDRESS_ACCESSED = 'address_accessed'
    RATING_SUBMITTED = 'rating_submitted'
    
    # Recipient actions
    RECIPIENT_REGISTERED = 'recipient_registered'
    RECIPIENT_DELETED = 'recipient_deleted'
    RECIPIENT_DATA_PURGED = 'recipient_data_purged'
    
    # Admin actions
    ADMIN_LOGIN = 'admin_login'
    ADMIN_VIEWED_RECIPIENT = 'admin_viewed_recipient'
    
    @classmethod
    def log(cls, action, volunteer_id=None, recipient_id=None, delivery_id=None,
            admin_id=None, details=None, ip_address=None):
        """Create an audit log entry."""
        entry = cls(
            action=action,
            volunteer_id=volunteer_id,
            recipient_id=recipient_id,
            delivery_id=delivery_id,
            admin_id=admin_id,
            details=details,
            ip_address=ip_address
        )
        db.session.add(entry)
        db.session.commit()
        return entry
    
    @classmethod
    def get_for_volunteer(cls, volunteer_id, limit=100):
        """Get audit entries for a specific volunteer."""
        return cls.query.filter(
            cls.volunteer_id == volunteer_id
        ).order_by(cls.timestamp.desc()).limit(limit).all()
    
    @classmethod
    def get_for_recipient(cls, recipient_id, limit=100):
        """Get audit entries for a specific recipient."""
        return cls.query.filter(
            cls.recipient_id == recipient_id
        ).order_by(cls.timestamp.desc()).limit(limit).all()
    
    @classmethod
    def get_for_delivery(cls, delivery_id):
        """Get audit entries for a specific delivery."""
        return cls.query.filter(
            cls.delivery_id == delivery_id
        ).order_by(cls.timestamp.asc()).all()
    
    @classmethod
    def get_recent(cls, limit=100, action_filter=None):
        """Get recent audit entries, optionally filtered by action type."""
        query = cls.query
        if action_filter:
            query = query.filter(cls.action == action_filter)
        return query.order_by(cls.timestamp.desc()).limit(limit).all()
    
    @classmethod
    def get_volunteers_for_recipient(cls, recipient_id):
        """Get list of volunteer IDs who have interacted with a recipient."""
        results = db.session.query(cls.volunteer_id).filter(
            cls.recipient_id == recipient_id,
            cls.volunteer_id.isnot(None)
        ).distinct().all()
        return [r[0] for r in results]
    
    def __repr__(self):
        return f'<AuditLog {self.action} at {self.timestamp}>'
