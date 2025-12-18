from datetime import datetime

from app import db


class Rating(db.Model):
    """Recipient ratings of volunteers."""
    __tablename__ = 'ratings'
    
    id = db.Column(db.Integer, primary_key=True)
    delivery_id = db.Column(db.Integer, db.ForeignKey('deliveries.id'), unique=True, nullable=False)
    volunteer_id = db.Column(db.Integer, db.ForeignKey('volunteers.id'), nullable=False, index=True)
    recipient_id = db.Column(db.Integer, db.ForeignKey('recipients.id'), nullable=False, index=True)
    score = db.Column(db.SmallInteger, nullable=False)  # 1-5 stars
    comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        db.CheckConstraint('score >= 1 AND score <= 5', name='chk_score'),
    )
    
    @classmethod
    def create_rating(cls, delivery, score, comment=None):
        """Create a rating for a completed delivery."""
        if delivery.status != 'completed':
            raise ValueError("Can only rate completed deliveries")
        
        if delivery.rating:
            raise ValueError("Delivery already has a rating")
        
        if not 1 <= score <= 5:
            raise ValueError("Score must be between 1 and 5")
        
        rating = cls(
            delivery_id=delivery.id,
            volunteer_id=delivery.volunteer_id,
            recipient_id=delivery.recipient_id,
            score=score,
            comment=comment
        )
        db.session.add(rating)
        db.session.commit()
        
        # Update volunteer's average rating
        delivery.volunteer.update_rating()
        
        return rating
    
    @classmethod
    def get_for_volunteer(cls, volunteer_id, limit=None):
        """Get ratings for a volunteer."""
        query = cls.query.filter(cls.volunteer_id == volunteer_id).order_by(cls.created_at.desc())
        if limit:
            query = query.limit(limit)
        return query.all()
    
    @classmethod
    def get_average_for_volunteer(cls, volunteer_id):
        """Calculate average rating for a volunteer."""
        from sqlalchemy import func
        return db.session.query(func.avg(cls.score)).filter(
            cls.volunteer_id == volunteer_id
        ).scalar()
    
    def __repr__(self):
        return f'<Rating {self.score}/5 for volunteer {self.volunteer_id}>'
