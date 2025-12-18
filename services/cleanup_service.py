import os
from datetime import datetime, timedelta
from flask import current_app

from app import db
from models.volunteer import VolunteerIdUpload
from models.recipient import Recipient, RecipientTombstone
from models.user import User
from services.audit_service import AuditService


def cleanup_expired_uploads():
    """Remove expired ID upload files and database records."""
    expired = VolunteerIdUpload.query.filter(
        VolunteerIdUpload.expires_at < datetime.utcnow()
    ).all()
    
    count = 0
    for upload in expired:
        # Delete physical file if it exists
        if os.path.exists(upload.file_path):
            try:
                os.remove(upload.file_path)
            except OSError as e:
                current_app.logger.error(f"Failed to delete file {upload.file_path}: {e}")
        
        # Delete database record
        db.session.delete(upload)
        count += 1
    
    db.session.commit()
    current_app.logger.info(f"Cleaned up {count} expired ID uploads")
    return count


def delete_volunteer_id_uploads(volunteer_id):
    """Delete all ID uploads for a volunteer (after review)."""
    uploads = VolunteerIdUpload.query.filter(
        VolunteerIdUpload.volunteer_id == volunteer_id
    ).all()
    
    for upload in uploads:
        if os.path.exists(upload.file_path):
            try:
                os.remove(upload.file_path)
            except OSError as e:
                current_app.logger.error(f"Failed to delete file {upload.file_path}: {e}")
        
        db.session.delete(upload)
    
    db.session.commit()
    return len(uploads)


def purge_inactive_accounts(months=None):
    """Purge inactive recipient accounts per retention policy."""
    if months is None:
        months = current_app.config.get('INACTIVE_ACCOUNT_PURGE_MONTHS', 18)
    
    cutoff_date = datetime.utcnow() - timedelta(days=months * 30)
    
    # Find inactive recipients
    inactive_recipients = db.session.query(Recipient).join(User).filter(
        User.last_active < cutoff_date,
        Recipient.deleted_at.is_(None)
    ).all()
    
    count = 0
    for recipient in inactive_recipients:
        # Create tombstone for audit trail
        tombstone = RecipientTombstone.create_from_recipient(recipient)
        db.session.add(tombstone)
        
        # Soft delete and purge sensitive data
        recipient.deleted_at = datetime.utcnow()
        recipient.address_encrypted = '[PURGED]'
        recipient.phone_encrypted = None
        recipient.notes_encrypted = None
        
        # Audit log
        AuditService.log_recipient_data_purged(recipient.id)
        
        count += 1
    
    db.session.commit()
    current_app.logger.info(f"Purged {count} inactive accounts")
    return count


def delete_recipient_account(recipient):
    """Delete a recipient account (user-initiated)."""
    from services.delivery_service import DeliveryService
    
    # Force cancel any active deliveries
    DeliveryService.force_cancel_for_deletion(recipient)
    
    # Create tombstone for audit trail
    tombstone = RecipientTombstone.create_from_recipient(recipient)
    db.session.add(tombstone)
    
    # Soft delete and purge sensitive data
    recipient.deleted_at = datetime.utcnow()
    recipient.address_encrypted = '[PURGED]'
    recipient.phone_encrypted = None
    recipient.notes_encrypted = None
    
    # Deactivate user account
    recipient.user.is_active = False
    
    # Audit log
    AuditService.log_recipient_deleted(recipient.id)
    
    db.session.commit()
    
    return True
