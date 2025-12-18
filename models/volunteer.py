from datetime import datetime, timedelta
from flask import current_app

from app import db


class Volunteer(db.Model):
    """Volunteer profile with vetting status."""
    __tablename__ = 'volunteers'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    full_name = db.Column(db.String(255), nullable=False)
    photo_path = db.Column(db.String(500), nullable=True)
    service_area = db.Column(db.String(255), nullable=False)
    availability_notes = db.Column(db.Text, nullable=True)
    
    # Vetting fields
    status = db.Column(
        db.Enum('pending', 'approved', 'suspended', 'rejected'),
        default='pending',
        index=True
    )
    attestation_completed = db.Column(db.Boolean, default=False)
    attestation_timestamp = db.Column(db.DateTime, nullable=True)
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    rejection_reason = db.Column(db.Text, nullable=True)
    suspension_reason = db.Column(db.Text, nullable=True)
    
    # Stats
    total_deliveries = db.Column(db.Integer, default=0)
    average_rating = db.Column(db.Numeric(3, 2), nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    reviewer = db.relationship('User', foreign_keys=[reviewed_by])
    deliveries = db.relationship('Delivery', backref='volunteer', lazy='dynamic')
    id_uploads = db.relationship('VolunteerIdUpload', backref='volunteer', lazy='dynamic', cascade='all, delete-orphan')
    ratings_received = db.relationship('Rating', backref='volunteer', lazy='dynamic')
    
    @property
    def is_approved(self):
        return self.status == 'approved'
    
    @property
    def is_pending(self):
        return self.status == 'pending'
    
    @property
    def is_suspended(self):
        return self.status == 'suspended'
    
    @property
    def active_claims_count(self):
        """Count of currently active (claimed or in-progress) deliveries."""
        return self.deliveries.filter(
            Delivery.status.in_(['claimed', 'picked_up'])
        ).count()
    
    def can_claim_delivery(self, max_claims=None):
        """Check if volunteer can claim another delivery."""
        if not self.is_approved:
            return False
        if max_claims is None:
            max_claims = current_app.config.get('MAX_ACTIVE_CLAIMS_PER_VOLUNTEER', 2)
        return self.active_claims_count < max_claims
    
    @property
    def active_deliveries(self):
        """Get currently active deliveries."""
        return self.deliveries.filter(
            Delivery.status.in_(['claimed', 'picked_up'])
        ).all()
    
    @property
    def completed_deliveries(self):
        """Get completed deliveries."""
        return self.deliveries.filter(
            Delivery.status == 'completed'
        ).order_by(Delivery.completed_at.desc())
    
    def update_rating(self):
        """Recalculate average rating from all ratings."""
        from sqlalchemy import func
        avg = db.session.query(func.avg(Rating.score)).filter(
            Rating.volunteer_id == self.id
        ).scalar()
        self.average_rating = avg
        db.session.commit()
    
    def approve(self, admin_user):
        """Approve volunteer application."""
        self.status = 'approved'
        self.reviewed_by = admin_user.id
        self.reviewed_at = datetime.utcnow()
        self.rejection_reason = None
        db.session.commit()
    
    def reject(self, admin_user, reason=None):
        """Reject volunteer application."""
        self.status = 'rejected'
        self.reviewed_by = admin_user.id
        self.reviewed_at = datetime.utcnow()
        self.rejection_reason = reason
        db.session.commit()
    
    def suspend(self, admin_user, reason=None):
        """Suspend an approved volunteer."""
        self.status = 'suspended'
        self.reviewed_by = admin_user.id
        self.reviewed_at = datetime.utcnow()
        self.suspension_reason = reason
        db.session.commit()
    
    def __repr__(self):
        return f'<Volunteer {self.full_name} ({self.status})>'


class VolunteerIdUpload(db.Model):
    """Temporary storage for ID verification photos."""
    __tablename__ = 'volunteer_id_uploads'
    
    id = db.Column(db.Integer, primary_key=True)
    volunteer_id = db.Column(db.Integer, db.ForeignKey('volunteers.id'), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    
    @classmethod
    def create_for_volunteer(cls, volunteer_id, file_path, expiry_hours=None):
        """Create an ID upload record with expiry."""
        if expiry_hours is None:
            expiry_hours = current_app.config.get('ID_UPLOAD_EXPIRY_HOURS', 72)
        
        upload = cls(
            volunteer_id=volunteer_id,
            file_path=file_path,
            expires_at=datetime.utcnow() + timedelta(hours=expiry_hours)
        )
        return upload
    
    @property
    def is_expired(self):
        return datetime.utcnow() > self.expires_at
    
    def __repr__(self):
        return f'<VolunteerIdUpload {self.id} for volunteer {self.volunteer_id}>'


# Import at bottom to avoid circular imports
from models.delivery import Delivery
from models.rating import Rating
