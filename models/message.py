from datetime import datetime

from app import db


class Message(db.Model):
    """In-app messaging tied to deliveries."""
    __tablename__ = 'messages'
    
    id = db.Column(db.Integer, primary_key=True)
    delivery_id = db.Column(db.Integer, db.ForeignKey('deliveries.id'), nullable=False, index=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    read_at = db.Column(db.DateTime, nullable=True)
    
    @property
    def is_read(self):
        return self.read_at is not None
    
    def mark_read(self):
        """Mark message as read."""
        if not self.read_at:
            self.read_at = datetime.utcnow()
            db.session.commit()
    
    @classmethod
    def get_for_delivery(cls, delivery_id, after_id=None, limit=50):
        """Get messages for a delivery, optionally after a specific message ID."""
        query = cls.query.filter(cls.delivery_id == delivery_id)
        
        if after_id:
            query = query.filter(cls.id > after_id)
        
        return query.order_by(cls.sent_at.asc()).limit(limit).all()
    
    @classmethod
    def get_unread_count(cls, delivery_id, user_id):
        """Get count of unread messages for a user in a delivery."""
        return cls.query.filter(
            cls.delivery_id == delivery_id,
            cls.sender_id != user_id,
            cls.read_at.is_(None)
        ).count()
    
    @classmethod
    def mark_all_read(cls, delivery_id, user_id):
        """Mark all messages in a delivery as read for a user."""
        cls.query.filter(
            cls.delivery_id == delivery_id,
            cls.sender_id != user_id,
            cls.read_at.is_(None)
        ).update({cls.read_at: datetime.utcnow()})
        db.session.commit()
    
    def to_dict(self):
        """Convert to dictionary for JSON response."""
        return {
            'id': self.id,
            'delivery_id': self.delivery_id,
            'sender_id': self.sender_id,
            'sender_name': self.sender.display_name if self.sender else 'Unknown',
            'content': self.content,
            'sent_at': self.sent_at.isoformat(),
            'is_read': self.is_read
        }
    
    def __repr__(self):
        return f'<Message {self.id} in delivery {self.delivery_id}>'
