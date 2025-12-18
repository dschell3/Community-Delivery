from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from app import db


class User(UserMixin, db.Model):
    """Base user model for authentication."""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum('admin', 'volunteer', 'recipient'), nullable=False, index=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_active = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    recipient_profile = db.relationship('Recipient', backref='user', uselist=False, cascade='all, delete-orphan')
    volunteer_profile = db.relationship('Volunteer', backref='user', uselist=False, cascade='all, delete-orphan', foreign_keys='Volunteer.user_id')
    sent_messages = db.relationship('Message', backref='sender', lazy='dynamic')
    
    def set_password(self, password):
        """Hash and set password."""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Verify password."""
        return check_password_hash(self.password_hash, password)
    
    def update_last_active(self):
        """Update last active timestamp."""
        self.last_active = datetime.utcnow()
        db.session.commit()
    
    @property
    def is_admin(self):
        return self.role == 'admin'
    
    @property
    def is_volunteer(self):
        return self.role == 'volunteer'
    
    @property
    def is_recipient(self):
        return self.role == 'recipient'
    
    @property
    def display_name(self):
        """Get appropriate display name based on role."""
        if self.is_recipient and self.recipient_profile:
            return self.recipient_profile.display_name
        elif self.is_volunteer and self.volunteer_profile:
            return self.volunteer_profile.full_name
        return self.email.split('@')[0]
    
    def __repr__(self):
        return f'<User {self.email} ({self.role})>'
