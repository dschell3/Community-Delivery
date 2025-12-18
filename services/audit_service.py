from flask import request
from models.audit import AuditLog


class AuditService:
    """Centralized audit logging service."""
    
    @staticmethod
    def get_client_ip():
        """Get client IP address from request."""
        if request:
            # Handle proxies (X-Forwarded-For header)
            if request.headers.get('X-Forwarded-For'):
                return request.headers.get('X-Forwarded-For').split(',')[0].strip()
            return request.remote_addr
        return None
    
    @classmethod
    def log_volunteer_registered(cls, volunteer_id):
        """Log volunteer registration."""
        return AuditLog.log(
            action=AuditLog.VOLUNTEER_REGISTERED,
            volunteer_id=volunteer_id,
            ip_address=cls.get_client_ip()
        )
    
    @classmethod
    def log_volunteer_approved(cls, volunteer_id, admin_id):
        """Log volunteer approval."""
        return AuditLog.log(
            action=AuditLog.VOLUNTEER_APPROVED,
            volunteer_id=volunteer_id,
            admin_id=admin_id,
            ip_address=cls.get_client_ip()
        )
    
    @classmethod
    def log_volunteer_rejected(cls, volunteer_id, admin_id, reason=None):
        """Log volunteer rejection."""
        return AuditLog.log(
            action=AuditLog.VOLUNTEER_REJECTED,
            volunteer_id=volunteer_id,
            admin_id=admin_id,
            details={'reason': reason} if reason else None,
            ip_address=cls.get_client_ip()
        )
    
    @classmethod
    def log_volunteer_suspended(cls, volunteer_id, admin_id, reason=None):
        """Log volunteer suspension."""
        return AuditLog.log(
            action=AuditLog.VOLUNTEER_SUSPENDED,
            volunteer_id=volunteer_id,
            admin_id=admin_id,
            details={'reason': reason} if reason else None,
            ip_address=cls.get_client_ip()
        )
    
    @classmethod
    def log_delivery_created(cls, delivery_id, recipient_id):
        """Log new delivery request."""
        return AuditLog.log(
            action=AuditLog.DELIVERY_CREATED,
            delivery_id=delivery_id,
            recipient_id=recipient_id,
            ip_address=cls.get_client_ip()
        )
    
    @classmethod
    def log_delivery_claimed(cls, delivery_id, volunteer_id, recipient_id):
        """Log delivery claim."""
        return AuditLog.log(
            action=AuditLog.DELIVERY_CLAIMED,
            delivery_id=delivery_id,
            volunteer_id=volunteer_id,
            recipient_id=recipient_id,
            ip_address=cls.get_client_ip()
        )
    
    @classmethod
    def log_delivery_canceled(cls, delivery_id, volunteer_id=None, recipient_id=None, 
                               canceled_by=None, reason=None):
        """Log delivery cancellation."""
        return AuditLog.log(
            action=AuditLog.DELIVERY_CANCELED,
            delivery_id=delivery_id,
            volunteer_id=volunteer_id,
            recipient_id=recipient_id,
            details={'canceled_by': canceled_by, 'reason': reason},
            ip_address=cls.get_client_ip()
        )
    
    @classmethod
    def log_delivery_picked_up(cls, delivery_id, volunteer_id, recipient_id):
        """Log groceries picked up from store."""
        return AuditLog.log(
            action=AuditLog.DELIVERY_PICKED_UP,
            delivery_id=delivery_id,
            volunteer_id=volunteer_id,
            recipient_id=recipient_id,
            ip_address=cls.get_client_ip()
        )
    
    @classmethod
    def log_delivery_completed(cls, delivery_id, volunteer_id, recipient_id):
        """Log delivery completion."""
        return AuditLog.log(
            action=AuditLog.DELIVERY_COMPLETED,
            delivery_id=delivery_id,
            volunteer_id=volunteer_id,
            recipient_id=recipient_id,
            ip_address=cls.get_client_ip()
        )
    
    @classmethod
    def log_message_sent(cls, delivery_id, sender_id, volunteer_id=None, recipient_id=None):
        """Log message sent."""
        return AuditLog.log(
            action=AuditLog.MESSAGE_SENT,
            delivery_id=delivery_id,
            volunteer_id=volunteer_id,
            recipient_id=recipient_id,
            details={'sender_id': sender_id},
            ip_address=cls.get_client_ip()
        )
    
    @classmethod
    def log_address_accessed(cls, delivery_id, volunteer_id, recipient_id):
        """Log when a volunteer accesses a recipient's address."""
        return AuditLog.log(
            action=AuditLog.ADDRESS_ACCESSED,
            delivery_id=delivery_id,
            volunteer_id=volunteer_id,
            recipient_id=recipient_id,
            ip_address=cls.get_client_ip()
        )
    
    @classmethod
    def log_rating_submitted(cls, delivery_id, volunteer_id, recipient_id, score):
        """Log rating submission."""
        return AuditLog.log(
            action=AuditLog.RATING_SUBMITTED,
            delivery_id=delivery_id,
            volunteer_id=volunteer_id,
            recipient_id=recipient_id,
            details={'score': score},
            ip_address=cls.get_client_ip()
        )
    
    @classmethod
    def log_recipient_registered(cls, recipient_id):
        """Log recipient registration."""
        return AuditLog.log(
            action=AuditLog.RECIPIENT_REGISTERED,
            recipient_id=recipient_id,
            ip_address=cls.get_client_ip()
        )
    
    @classmethod
    def log_recipient_deleted(cls, recipient_id):
        """Log recipient account deletion."""
        return AuditLog.log(
            action=AuditLog.RECIPIENT_DELETED,
            recipient_id=recipient_id,
            ip_address=cls.get_client_ip()
        )
    
    @classmethod
    def log_recipient_data_purged(cls, recipient_id):
        """Log recipient data purge (inactive account)."""
        return AuditLog.log(
            action=AuditLog.RECIPIENT_DATA_PURGED,
            recipient_id=recipient_id
        )
    
    @classmethod
    def log_admin_login(cls, admin_id):
        """Log admin login."""
        return AuditLog.log(
            action=AuditLog.ADMIN_LOGIN,
            admin_id=admin_id,
            ip_address=cls.get_client_ip()
        )
    
    @classmethod
    def log_admin_viewed_recipient(cls, admin_id, recipient_id):
        """Log admin viewing recipient details."""
        return AuditLog.log(
            action=AuditLog.ADMIN_VIEWED_RECIPIENT,
            admin_id=admin_id,
            recipient_id=recipient_id,
            ip_address=cls.get_client_ip()
        )
