from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user

from app import db
from models.delivery import Delivery
from models.rating import Rating
from services.delivery_service import DeliveryService
from services.encryption_service import get_encryption_service
from services.cleanup_service import delete_recipient_account
from services.audit_service import AuditService

bp = Blueprint('recipient', __name__)


def recipient_required(f):
    """Decorator to require recipient role."""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        if not current_user.is_recipient:
            abort(403)
        if not current_user.recipient_profile:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


@bp.route('/dashboard')
@login_required
@recipient_required
def dashboard():
    """Recipient dashboard - view active and past deliveries."""
    recipient = current_user.recipient_profile
    
    active_deliveries = Delivery.query.filter(
        Delivery.recipient_id == recipient.id,
        Delivery.status.in_(['open', 'claimed', 'picked_up'])
    ).order_by(Delivery.created_at.desc()).all()
    
    past_deliveries = Delivery.query.filter(
        Delivery.recipient_id == recipient.id,
        Delivery.status.in_(['completed', 'canceled'])
    ).order_by(Delivery.completed_at.desc()).limit(10).all()
    
    return render_template(
        'recipient/dashboard.html',
        active_deliveries=active_deliveries,
        past_deliveries=past_deliveries
    )


@bp.route('/request/new', methods=['GET', 'POST'])
@login_required
@recipient_required
def request_new():
    """Create a new delivery request."""
    recipient = current_user.recipient_profile
    
    # Check if there's already an active request
    active = Delivery.query.filter(
        Delivery.recipient_id == recipient.id,
        Delivery.status.in_(['open', 'claimed', 'picked_up'])
    ).first()
    
    if active:
        flash('You already have an active delivery request.', 'warning')
        return redirect(url_for('recipient.request_detail', id=active.id))
    
    if request.method == 'POST':
        store_name = request.form.get('store_name', '').strip()
        pickup_address = request.form.get('pickup_address', '').strip()
        order_name = request.form.get('order_name', '').strip()
        pickup_time_str = request.form.get('pickup_time', '')
        estimated_items = request.form.get('estimated_items', '').strip() or None
        
        # Validation
        errors = []
        if not store_name:
            errors.append('Store name is required.')
        if not pickup_address:
            errors.append('Store address is required.')
        if not order_name:
            errors.append('Order name is required.')
        if not pickup_time_str:
            errors.append('Pickup time is required.')
        
        pickup_time = None
        if pickup_time_str:
            try:
                pickup_time = datetime.fromisoformat(pickup_time_str)
                if pickup_time < datetime.now():
                    errors.append('Pickup time must be in the future.')
            except ValueError:
                errors.append('Invalid pickup time format.')
        
        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('recipient/request_new.html')
        
        # Create delivery
        delivery = DeliveryService.create_delivery(
            recipient=recipient,
            store_name=store_name,
            pickup_address=pickup_address,
            order_name=order_name,
            pickup_time=pickup_time,
            estimated_items=estimated_items
        )
        
        flash('Delivery request created successfully.', 'success')
        return redirect(url_for('recipient.request_detail', id=delivery.id))
    
    return render_template('recipient/request_new.html')


@bp.route('/request/<int:id>')
@login_required
@recipient_required
def request_detail(id):
    """View delivery request details and message volunteer."""
    recipient = current_user.recipient_profile
    
    delivery = Delivery.query.get_or_404(id)
    if delivery.recipient_id != recipient.id:
        abort(403)
    
    # Get messages if delivery is claimed
    messages = []
    if delivery.volunteer_id:
        from models.message import Message
        messages = Message.get_for_delivery(delivery.id)
        Message.mark_all_read(delivery.id, current_user.id)
    
    return render_template(
        'recipient/request_detail.html',
        delivery=delivery,
        messages=messages
    )


@bp.route('/request/<int:id>/cancel', methods=['POST'])
@login_required
@recipient_required
def request_cancel(id):
    """Cancel a delivery request."""
    recipient = current_user.recipient_profile
    
    delivery = Delivery.query.get_or_404(id)
    if delivery.recipient_id != recipient.id:
        abort(403)
    
    if not delivery.can_be_canceled:
        flash('This delivery cannot be canceled.', 'error')
        return redirect(url_for('recipient.request_detail', id=id))
    
    reason = request.form.get('reason', '').strip() or None
    
    try:
        DeliveryService.cancel_delivery_by_recipient(delivery, recipient, reason)
        flash('Delivery request canceled.', 'info')
    except ValueError as e:
        flash(str(e), 'error')
    
    return redirect(url_for('recipient.dashboard'))


@bp.route('/request/<int:id>/complete', methods=['GET', 'POST'])
@login_required
@recipient_required
def request_complete(id):
    """Mark delivery as received and leave rating."""
    recipient = current_user.recipient_profile
    
    delivery = Delivery.query.get_or_404(id)
    if delivery.recipient_id != recipient.id:
        abort(403)
    
    # Can only rate completed deliveries
    if delivery.status != 'completed':
        flash('This delivery has not been marked as complete by the volunteer yet.', 'warning')
        return redirect(url_for('recipient.request_detail', id=id))
    
    # Check if already rated
    if delivery.rating:
        flash('You have already rated this delivery.', 'info')
        return redirect(url_for('recipient.dashboard'))
    
    if request.method == 'POST':
        score = request.form.get('score', type=int)
        comment = request.form.get('comment', '').strip() or None
        
        if not score or not 1 <= score <= 5:
            flash('Please select a rating from 1 to 5.', 'error')
            return render_template('recipient/complete.html', delivery=delivery)
        
        try:
            Rating.create_rating(delivery, score, comment)
            AuditService.log_rating_submitted(
                delivery.id,
                delivery.volunteer_id,
                recipient.id,
                score
            )
            flash('Thank you for your feedback!', 'success')
        except ValueError as e:
            flash(str(e), 'error')
        
        return redirect(url_for('recipient.dashboard'))
    
    return render_template('recipient/complete.html', delivery=delivery)


@bp.route('/settings', methods=['GET', 'POST'])
@login_required
@recipient_required
def settings():
    """Update recipient profile settings."""
    recipient = current_user.recipient_profile
    encryption_service = get_encryption_service()
    
    if request.method == 'POST':
        display_name = request.form.get('display_name', '').strip()
        address = request.form.get('address', '').strip()
        phone = request.form.get('phone', '').strip() or None
        general_area = request.form.get('general_area', '').strip() or None
        notes = request.form.get('notes', '').strip() or None
        
        # Validation
        errors = []
        if not display_name:
            errors.append('Display name is required.')
        if not address:
            errors.append('Delivery address is required.')
        
        if errors:
            for error in errors:
                flash(error, 'error')
        else:
            recipient.display_name = display_name
            recipient.set_address(address, encryption_service)
            recipient.set_phone(phone, encryption_service)
            recipient.general_area = general_area
            recipient.set_notes(notes, encryption_service)
            
            db.session.commit()
            flash('Settings updated successfully.', 'success')
    
    # Decrypt current values for display
    current_address = recipient.get_address(encryption_service)
    current_phone = recipient.get_phone(encryption_service)
    current_notes = recipient.get_notes(encryption_service)
    
    return render_template(
        'recipient/settings.html',
        recipient=recipient,
        current_address=current_address,
        current_phone=current_phone,
        current_notes=current_notes
    )


@bp.route('/delete-account', methods=['GET', 'POST'])
@login_required
@recipient_required
def delete_account():
    """Delete recipient account."""
    recipient = current_user.recipient_profile
    
    if request.method == 'POST':
        confirm = request.form.get('confirm', '')
        
        if confirm != 'DELETE':
            flash('Please type DELETE to confirm account deletion.', 'error')
            return render_template('recipient/delete_account.html')
        
        try:
            delete_recipient_account(recipient)
            flash('Your account has been deleted.', 'info')
            return redirect(url_for('auth.logout'))
        except Exception as e:
            flash('An error occurred while deleting your account.', 'error')
    
    return render_template('recipient/delete_account.html')
