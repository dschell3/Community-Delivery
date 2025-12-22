from datetime import datetime
from flask import current_app

from app import db
from models.delivery import Delivery
from models.recipient import Recipient
from models.volunteer import Volunteer
from services.audit_service import AuditService
from services.encryption_service import get_encryption_service
from services.geocoding_service import GeocodingService


class DeliveryService:
    """Business logic for delivery operations."""
    
    @staticmethod
    def create_delivery(recipient, store_name, pickup_address, order_name, 
                        pickup_time, estimated_items=None, 
                        store_lat=None, store_lng=None, store_place_id=None):
        """Create a new delivery request."""
        delivery = Delivery(
            recipient_id=recipient.id,
            store_name=store_name,
            pickup_address=pickup_address,
            order_name=order_name,
            pickup_time=pickup_time,
            estimated_items=estimated_items,
            status='open'
        )
        
        # Set store location if provided
        if store_lat is not None and store_lng is not None:
            delivery.set_store_location(store_lat, store_lng, store_place_id)
        
        db.session.add(delivery)
        db.session.commit()
        
        # Audit log
        AuditService.log_delivery_created(delivery.id, recipient.id)
        
        return delivery
    
    @staticmethod
    def get_available_deliveries(volunteer):
        """
        Get deliveries available to a specific volunteer based on their service area.
        Both the store AND recipient must be within the volunteer's service radius.
        """
        return Delivery.get_available_for_volunteer(volunteer)
    
    @staticmethod
    def claim_delivery(delivery, volunteer):
        """Volunteer claims a delivery."""
        if not delivery.can_be_claimed:
            raise ValueError("Delivery is not available for claiming")
        
        max_claims = current_app.config.get('MAX_ACTIVE_CLAIMS_PER_VOLUNTEER', 2)
        if not volunteer.can_claim_delivery(max_claims):
            raise ValueError(f"You already have {max_claims} active deliveries")
        
        # Verify delivery is still within volunteer's service area
        if volunteer.has_service_location:
            # Check store distance
            if delivery.store_latitude and delivery.store_longitude:
                store_distance = GeocodingService.calculate_distance(
                    float(volunteer.service_center_lat),
                    float(volunteer.service_center_lng),
                    float(delivery.store_latitude),
                    float(delivery.store_longitude)
                )
                if store_distance > volunteer.service_radius_miles:
                    raise ValueError("Store is outside your service area")
            
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
                    raise ValueError("Recipient is outside your service area")
        
        delivery.volunteer_id = volunteer.id
        delivery.status = 'claimed'
        delivery.claimed_at = datetime.utcnow()
        db.session.commit()
        
        # Audit log
        AuditService.log_delivery_claimed(
            delivery.id, 
            volunteer.id, 
            delivery.recipient_id
        )
        
        # Send notification to recipient
        try:
            from services.notification_service import NotificationService
            NotificationService.notify_delivery_claimed(delivery)
        except Exception as e:
            current_app.logger.error(f"Failed to send claim notification: {e}")
        
        return delivery
    
    @staticmethod
    def mark_picked_up(delivery, volunteer):
        """Mark groceries as picked up from store."""
        if delivery.volunteer_id != volunteer.id:
            raise ValueError("This delivery is not assigned to you")
        
        if delivery.status != 'claimed':
            raise ValueError("Delivery must be claimed before marking picked up")
        
        delivery.status = 'picked_up'
        delivery.picked_up_at = datetime.utcnow()
        db.session.commit()
        
        # Audit log
        AuditService.log_delivery_picked_up(
            delivery.id,
            volunteer.id,
            delivery.recipient_id
        )
        
        # Send notification to recipient
        try:
            from services.notification_service import NotificationService
            NotificationService.notify_delivery_picked_up(delivery)
        except Exception as e:
            current_app.logger.error(f"Failed to send pickup notification: {e}")
        
        return delivery
    
    @staticmethod
    def complete_delivery(delivery, volunteer):
        """Mark delivery as completed (volunteer side)."""
        if delivery.volunteer_id != volunteer.id:
            raise ValueError("This delivery is not assigned to you")
        
        if delivery.status not in ['claimed', 'picked_up']:
            raise ValueError("Delivery cannot be completed in current state")
        
        delivery.status = 'completed'
        delivery.completed_at = datetime.utcnow()
        
        # Update volunteer stats
        volunteer.total_deliveries += 1
        
        db.session.commit()
        
        # Audit log
        AuditService.log_delivery_completed(
            delivery.id,
            volunteer.id,
            delivery.recipient_id
        )
        
        # Send notification to recipient
        try:
            from services.notification_service import NotificationService
            NotificationService.notify_delivery_completed(delivery)
        except Exception as e:
            current_app.logger.error(f"Failed to send completion notification: {e}")
        
        return delivery
    
    @staticmethod
    def cancel_delivery_by_recipient(delivery, recipient, reason=None):
        """Recipient cancels their delivery request."""
        if delivery.recipient_id != recipient.id:
            raise ValueError("This is not your delivery request")
        
        if not delivery.can_be_canceled:
            raise ValueError("Delivery cannot be canceled in current state")
        
        was_claimed = delivery.status in ['claimed', 'picked_up']
        volunteer_id = delivery.volunteer_id
        volunteer = delivery.volunteer  # Get volunteer before clearing
        
        delivery.status = 'canceled'
        delivery.canceled_at = datetime.utcnow()
        delivery.canceled_by = 'recipient'
        delivery.cancellation_reason = reason
        delivery.volunteer_id = None
        delivery.claimed_at = None
        delivery.picked_up_at = None
        
        db.session.commit()
        
        # Audit log
        AuditService.log_delivery_canceled(
            delivery.id,
            volunteer_id=volunteer_id,
            recipient_id=recipient.id,
            canceled_by='recipient',
            reason=reason
        )
        
        # Notify volunteer if delivery was claimed
        if was_claimed and volunteer:
            try:
                from services.notification_service import NotificationService
                NotificationService.notify_volunteer_delivery_canceled(volunteer, delivery, reason='recipient')
            except Exception as e:
                current_app.logger.error(f"Failed to send cancellation notification: {e}")
        
        return delivery
    
    @staticmethod
    def release_claim(delivery, volunteer, reason=None):
        """Volunteer releases their claim on a delivery (only before pickup)."""
        if delivery.volunteer_id != volunteer.id:
            raise ValueError("This delivery is not assigned to you")
        
        # Only allow release before pickup - after pickup, contact admin
        if delivery.status != 'claimed':
            raise ValueError("Cannot release delivery after pickup. Please contact an administrator for assistance.")
        
        recipient_id = delivery.recipient_id
        
        # Return to pool with boosted priority
        delivery.volunteer_id = None
        delivery.status = 'open'
        delivery.claimed_at = None
        delivery.picked_up_at = None
        delivery.priority += 5
        
        db.session.commit()
        
        # Audit log
        AuditService.log_delivery_canceled(
            delivery.id,
            volunteer_id=volunteer.id,
            recipient_id=recipient_id,
            canceled_by='volunteer',
            reason=reason
        )
        
        return delivery
    
    @staticmethod
    def get_recipient_address(delivery, volunteer):
        """Get recipient address for a claimed delivery (with audit logging)."""
        if delivery.volunteer_id != volunteer.id:
            raise ValueError("This delivery is not assigned to you")
        
        if delivery.status not in ['claimed', 'picked_up']:
            raise ValueError("Address only available for active deliveries")
        
        recipient = delivery.recipient
        encryption_service = get_encryption_service()
        
        # Audit log address access
        AuditService.log_address_accessed(
            delivery.id,
            volunteer.id,
            recipient.id
        )
        
        return {
            'address': recipient.get_address(encryption_service),
            'notes': recipient.get_notes(encryption_service),
            'display_name': recipient.display_name
        }
    
    @staticmethod
    def force_cancel_for_deletion(recipient):
        """Force cancel any active deliveries for a recipient being deleted."""
        active_deliveries = Delivery.query.filter(
            Delivery.recipient_id == recipient.id,
            Delivery.status.in_(['open', 'claimed', 'picked_up'])
        ).all()
        
        for delivery in active_deliveries:
            volunteer_id = delivery.volunteer_id
            volunteer = delivery.volunteer  # Get volunteer before clearing
            
            delivery.status = 'canceled'
            delivery.canceled_at = datetime.utcnow()
            delivery.canceled_by = 'system'
            delivery.cancellation_reason = 'Recipient account deleted'
            delivery.volunteer_id = None
            delivery.claimed_at = None
            delivery.picked_up_at = None
            
            # Audit log
            AuditService.log_delivery_canceled(
                delivery.id,
                volunteer_id=volunteer_id,
                recipient_id=recipient.id,
                canceled_by='system',
                reason='Recipient account deleted'
            )
            
            # Notify volunteer if delivery was claimed
            if volunteer:
                try:
                    from services.notification_service import NotificationService
                    NotificationService.notify_volunteer_delivery_canceled(volunteer, delivery, reason='account_deleted')
                except Exception as e:
                    current_app.logger.error(f"Failed to send deletion notification: {e}")
        
        db.session.commit()
        return len(active_deliveries)
