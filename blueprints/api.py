from flask import Blueprint, jsonify, request, abort
from flask_login import login_required, current_user

from app import db
from models.delivery import Delivery
from models.message import Message
from services.audit_service import AuditService

bp = Blueprint('api', __name__)


def get_delivery_access(delivery_id):
    """Check if current user has access to a delivery's messages."""
    delivery = Delivery.query.get_or_404(delivery_id)
    
    # Check if user is involved in this delivery
    if current_user.is_recipient:
        if delivery.recipient_id != current_user.recipient_profile.id:
            abort(403)
    elif current_user.is_volunteer:
        if delivery.volunteer_id != current_user.volunteer_profile.id:
            abort(403)
    elif current_user.is_admin:
        pass  # Admins can view any delivery
    else:
        abort(403)
    
    return delivery


@bp.route('/messages/<int:delivery_id>', methods=['GET'])
@login_required
def get_messages(delivery_id):
    """Get messages for a delivery (polling endpoint)."""
    delivery = get_delivery_access(delivery_id)
    
    # Optional: get messages after a specific ID
    after_id = request.args.get('after', type=int)
    
    messages = Message.get_for_delivery(delivery_id, after_id=after_id)
    
    # Mark messages as read
    Message.mark_all_read(delivery_id, current_user.id)
    
    return jsonify({
        'delivery_id': delivery_id,
        'messages': [msg.to_dict() for msg in messages],
        'status': delivery.status
    })


@bp.route('/messages/<int:delivery_id>', methods=['POST'])
@login_required
def send_message(delivery_id):
    """Send a message in a delivery conversation."""
    delivery = get_delivery_access(delivery_id)
    
    # Can only message on active deliveries
    if delivery.status not in ['claimed', 'picked_up']:
        return jsonify({
            'error': 'Cannot send messages on this delivery'
        }), 400
    
    data = request.get_json()
    if not data or not data.get('content'):
        return jsonify({
            'error': 'Message content is required'
        }), 400
    
    content = data['content'].strip()
    if not content:
        return jsonify({
            'error': 'Message cannot be empty'
        }), 400
    
    if len(content) > 1000:
        return jsonify({
            'error': 'Message too long (max 1000 characters)'
        }), 400
    
    # Create message
    message = Message(
        delivery_id=delivery_id,
        sender_id=current_user.id,
        content=content
    )
    db.session.add(message)
    db.session.commit()
    
    # Determine volunteer and recipient IDs for audit
    volunteer_id = None
    recipient_id = None
    
    if current_user.is_volunteer:
        volunteer_id = current_user.volunteer_profile.id
        recipient_id = delivery.recipient_id
    elif current_user.is_recipient:
        recipient_id = current_user.recipient_profile.id
        volunteer_id = delivery.volunteer_id
    
    # Audit log
    AuditService.log_message_sent(
        delivery_id,
        current_user.id,
        volunteer_id=volunteer_id,
        recipient_id=recipient_id
    )
    
    return jsonify({
        'message': message.to_dict()
    }), 201


@bp.route('/messages/<int:delivery_id>/unread', methods=['GET'])
@login_required
def get_unread_count(delivery_id):
    """Get unread message count for a delivery."""
    delivery = get_delivery_access(delivery_id)
    
    count = Message.get_unread_count(delivery_id, current_user.id)
    
    return jsonify({
        'delivery_id': delivery_id,
        'unread_count': count
    })


@bp.route('/deliveries/<int:delivery_id>/status', methods=['GET'])
@login_required
def get_delivery_status(delivery_id):
    """Get current delivery status (for polling)."""
    delivery = get_delivery_access(delivery_id)
    
    response = {
        'delivery_id': delivery_id,
        'status': delivery.status,
        'volunteer_id': delivery.volunteer_id
    }
    
    # Include volunteer info if claimed
    if delivery.volunteer_id and delivery.volunteer:
        response['volunteer'] = {
            'name': delivery.volunteer.full_name,
            'photo': delivery.volunteer.photo_path
        }
    
    return jsonify(response)
