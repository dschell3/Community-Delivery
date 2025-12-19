import os
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, current_app
from flask_login import login_required, current_user, login_user
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash

from app import db
from models.user import User
from models.volunteer import Volunteer, VolunteerIdUpload
from models.delivery import Delivery
from services.delivery_service import DeliveryService
from services.audit_service import AuditService

bp = Blueprint('volunteer', __name__)


def volunteer_required(f):
    """Decorator to require approved volunteer role."""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        if not current_user.is_volunteer:
            abort(403)
        if not current_user.volunteer_profile:
            abort(403)
        if not current_user.volunteer_profile.is_approved:
            return redirect(url_for('volunteer.pending'))
        return f(*args, **kwargs)
    return decorated_function


def allowed_file(filename):
    """Check if file extension is allowed."""
    allowed = current_app.config.get('ALLOWED_EXTENSIONS', {'png', 'jpg', 'jpeg'})
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed


@bp.route('/apply', methods=['GET', 'POST'])
def apply():
    """Volunteer application form."""
    if current_user.is_authenticated:
        if current_user.is_volunteer:
            if current_user.volunteer_profile.is_pending:
                return redirect(url_for('volunteer.pending'))
            return redirect(url_for('volunteer.dashboard'))
        return redirect(url_for('auth.dashboard_redirect'))
    
    if request.method == 'POST':
        # Account info
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        # Profile info
        full_name = request.form.get('full_name', '').strip()
        service_area = request.form.get('service_area', '').strip()
        availability_notes = request.form.get('availability_notes', '').strip() or None
        
        # Attestation
        attestation = request.form.get('attestation') == 'on'
        
        # Files
        photo = request.files.get('photo')
        id_photo = request.files.get('id_photo')
        
        # Validation
        errors = []
        if not email or '@' not in email:
            errors.append('Valid email is required.')
        if len(password) < 8:
            errors.append('Password must be at least 8 characters.')
        if password != confirm_password:
            errors.append('Passwords do not match.')
        if not full_name:
            errors.append('Full name is required.')
        if not service_area:
            errors.append('Service area is required.')
        if not attestation:
            errors.append('You must confirm the attestation.')
        if User.query.filter_by(email=email).first():
            errors.append('An account with this email already exists.')
        
        # File validation
        if not photo or not photo.filename:
            errors.append('Profile photo is required.')
        elif not allowed_file(photo.filename):
            errors.append('Profile photo must be PNG, JPG, or JPEG.')
        
        if not id_photo or not id_photo.filename:
            errors.append('ID photo is required for verification.')
        elif not allowed_file(id_photo.filename):
            errors.append('ID photo must be PNG, JPG, or JPEG.')
        
        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('volunteer/apply.html')
        
        # Create user
        user = User(
            email=email,
            password_hash=generate_password_hash(password),
            role='volunteer'
        )
        db.session.add(user)
        db.session.flush()
        
        # Save profile photo
        photo_filename = secure_filename(f"volunteer_{user.id}_{photo.filename}")
        photo_path = os.path.join(
            current_app.config['UPLOAD_FOLDER'],
            'volunteer_photos',
            photo_filename
        )
        photo.save(photo_path)
        
        # Create volunteer profile
        volunteer = Volunteer(
            user_id=user.id,
            full_name=full_name,
            photo_path=photo_path,
            service_area=service_area,
            availability_notes=availability_notes,
            status='pending',
            attestation_completed=True,
            attestation_timestamp=datetime.utcnow()
        )
        db.session.add(volunteer)
        db.session.flush()
        
        # Save ID photo (temporary)
        id_filename = secure_filename(f"id_{volunteer.id}_{id_photo.filename}")
        id_path = os.path.join(
            current_app.config['UPLOAD_FOLDER'],
            'id_photos',
            id_filename
        )
        id_photo.save(id_path)
        
        # Create ID upload record
        id_upload = VolunteerIdUpload.create_for_volunteer(volunteer.id, id_path)
        db.session.add(id_upload)
        
        db.session.commit()
        
        # Audit log
        AuditService.log_volunteer_registered(volunteer.id)
        
        # Auto-login and redirect to pending page
        login_user(user)
        flash('Application submitted successfully! Your application is under review.', 'success')
        return redirect(url_for('volunteer.pending'))
    
    return render_template('volunteer/apply.html')


@bp.route('/pending')
@login_required
def pending():
    """Show pending application status."""
    if not current_user.is_volunteer or not current_user.volunteer_profile:
        return redirect(url_for('auth.dashboard_redirect'))
    
    volunteer = current_user.volunteer_profile
    
    if volunteer.is_approved:
        return redirect(url_for('volunteer.dashboard'))
    
    if volunteer.status == 'rejected':
        return render_template('volunteer/rejected.html', volunteer=volunteer)
    
    if volunteer.status == 'suspended':
        return render_template('volunteer/suspended.html', volunteer=volunteer)
    
    return render_template('volunteer/pending.html', volunteer=volunteer)


@bp.route('/dashboard')
@login_required
@volunteer_required
def dashboard():
    """Volunteer dashboard - view available and active deliveries."""
    volunteer = current_user.volunteer_profile
    
    # Get available deliveries in service area
    available_deliveries = DeliveryService.get_available_deliveries(
        service_area=volunteer.service_area
    )
    
    # Get volunteer's active deliveries
    active_deliveries = Delivery.query.filter(
        Delivery.volunteer_id == volunteer.id,
        Delivery.status.in_(['claimed', 'picked_up'])
    ).order_by(Delivery.pickup_time.asc()).all()
    
    # Get recent completed deliveries
    completed_deliveries = Delivery.query.filter(
        Delivery.volunteer_id == volunteer.id,
        Delivery.status == 'completed'
    ).order_by(Delivery.completed_at.desc()).limit(5).all()
    
    max_claims = current_app.config.get('MAX_ACTIVE_CLAIMS_PER_VOLUNTEER', 2)
    can_claim = volunteer.active_claims_count < max_claims
    
    return render_template(
        'volunteer/dashboard.html',
        volunteer=volunteer,
        available_deliveries=available_deliveries,
        active_deliveries=active_deliveries,
        completed_deliveries=completed_deliveries,
        can_claim=can_claim,
        max_claims=max_claims
    )


@bp.route('/request/<int:id>')
@login_required
@volunteer_required
def request_detail(id):
    """View delivery request details."""
    volunteer = current_user.volunteer_profile
    
    delivery = Delivery.query.get_or_404(id)
    
    # Check access - must be open or assigned to this volunteer
    if delivery.status == 'open':
        # Anyone can view open deliveries
        address_info = None
    elif delivery.volunteer_id == volunteer.id:
        # Get address if this is volunteer's delivery
        address_info = DeliveryService.get_recipient_address(delivery, volunteer)
    else:
        abort(403)
    
    # Get messages if claimed
    messages = []
    if delivery.volunteer_id == volunteer.id and delivery.status in ['claimed', 'picked_up']:
        from models.message import Message
        messages = Message.get_for_delivery(delivery.id)
        Message.mark_all_read(delivery.id, current_user.id)
    
    return render_template(
        'volunteer/request_detail.html',
        delivery=delivery,
        address_info=address_info,
        messages=messages,
        is_my_delivery=delivery.volunteer_id == volunteer.id
    )


@bp.route('/request/<int:id>/claim', methods=['POST'])
@login_required
@volunteer_required
def request_claim(id):
    """Claim a delivery."""
    volunteer = current_user.volunteer_profile
    
    delivery = Delivery.query.get_or_404(id)
    
    try:
        DeliveryService.claim_delivery(delivery, volunteer)
        flash('Delivery claimed! Check the details for pickup information.', 'success')
    except ValueError as e:
        flash(str(e), 'error')
    
    return redirect(url_for('volunteer.request_detail', id=id))


@bp.route('/request/<int:id>/pickup', methods=['POST'])
@login_required
@volunteer_required
def request_pickup(id):
    """Mark groceries as picked up from store."""
    volunteer = current_user.volunteer_profile
    
    delivery = Delivery.query.get_or_404(id)
    
    try:
        DeliveryService.mark_picked_up(delivery, volunteer)
        flash('Marked as picked up. Head to the delivery address!', 'success')
    except ValueError as e:
        flash(str(e), 'error')
    
    return redirect(url_for('volunteer.request_detail', id=id))


@bp.route('/request/<int:id>/complete', methods=['POST'])
@login_required
@volunteer_required
def request_complete(id):
    """Mark delivery as completed."""
    volunteer = current_user.volunteer_profile
    
    delivery = Delivery.query.get_or_404(id)
    
    try:
        DeliveryService.complete_delivery(delivery, volunteer)
        flash('Delivery completed! Thank you for your help.', 'success')
    except ValueError as e:
        flash(str(e), 'error')
    
    return redirect(url_for('volunteer.dashboard'))


@bp.route('/request/<int:id>/release', methods=['POST'])
@login_required
@volunteer_required
def request_release(id):
    """Release claim on a delivery."""
    volunteer = current_user.volunteer_profile
    
    delivery = Delivery.query.get_or_404(id)
    
    reason = request.form.get('reason', '').strip() or None
    
    try:
        DeliveryService.release_claim(delivery, volunteer, reason)
        flash('Delivery released back to the pool.', 'info')
    except ValueError as e:
        flash(str(e), 'error')
    
    return redirect(url_for('volunteer.dashboard'))


@bp.route('/settings', methods=['GET', 'POST'])
@login_required
@volunteer_required
def settings():
    """Update volunteer profile settings."""
    volunteer = current_user.volunteer_profile
    
    if request.method == 'POST':
        service_area = request.form.get('service_area', '').strip()
        availability_notes = request.form.get('availability_notes', '').strip() or None
        
        if not service_area:
            flash('Service area is required.', 'error')
        else:
            volunteer.service_area = service_area
            volunteer.availability_notes = availability_notes
            
            # Handle photo update
            photo = request.files.get('photo')
            if photo and photo.filename and allowed_file(photo.filename):
                photo_filename = secure_filename(f"volunteer_{current_user.id}_{photo.filename}")
                photo_path = os.path.join(
                    current_app.config['UPLOAD_FOLDER'],
                    'volunteer_photos',
                    photo_filename
                )
                photo.save(photo_path)
                volunteer.photo_path = photo_path
            
            db.session.commit()
            flash('Settings updated successfully.', 'success')
    
    return render_template('volunteer/settings.html', volunteer=volunteer)