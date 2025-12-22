from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash

from app import db
from models.user import User
from models.recipient import Recipient
from models.volunteer import Volunteer
from services.encryption_service import get_encryption_service
from services.geocoding_service import GeocodingService
from services.audit_service import AuditService

bp = Blueprint('auth', __name__)


@bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login."""
    if current_user.is_authenticated:
        return redirect(url_for('auth.dashboard_redirect'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember = request.form.get('remember', False)
        
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            if not user.is_active:
                flash('Your account has been deactivated.', 'error')
                return render_template('auth/login.html')
            
            login_user(user, remember=remember)
            user.update_last_active()
            
            # Log admin logins
            if user.is_admin:
                AuditService.log_admin_login(user.id)
            
            # Redirect to intended page or role-appropriate dashboard
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('auth.dashboard_redirect'))
        
        flash('Invalid email or password.', 'error')
    
    return render_template('auth/login.html')


@bp.route('/logout')
@login_required
def logout():
    """User logout."""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))


@bp.route('/register', methods=['GET', 'POST'])
def register():
    """Registration - choose role."""
    if current_user.is_authenticated:
        return redirect(url_for('auth.dashboard_redirect'))
    
    return render_template('auth/register_role.html')


@bp.route('/register/recipient', methods=['GET', 'POST'])
def register_recipient():
    """Recipient registration with address geocoding."""
    if current_user.is_authenticated:
        return redirect(url_for('auth.dashboard_redirect'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        display_name = request.form.get('display_name', '').strip()
        address = request.form.get('address', '').strip()
        phone = request.form.get('phone', '').strip() or None
        notes = request.form.get('notes', '').strip() or None
        
        # Geocoding data from autocomplete
        address_place_id = request.form.get('address_place_id', '').strip()
        address_lat = request.form.get('address_lat', '').strip()
        address_lng = request.form.get('address_lng', '').strip()
        
        # Validation
        errors = []
        if not email or '@' not in email:
            errors.append('Valid email is required.')
        if len(password) < 8:
            errors.append('Password must be at least 8 characters.')
        if password != confirm_password:
            errors.append('Passwords do not match.')
        if not display_name:
            errors.append('Display name is required.')
        if not address:
            errors.append('Delivery address is required.')
        if User.query.filter_by(email=email).first():
            errors.append('An account with this email already exists.')
        
        # Validate address is within service area
        latitude = None
        longitude = None
        
        if address_place_id or address:
            validation = GeocodingService.validate_address_in_service_area(
                place_id=address_place_id,
                address=address
            )
            
            if not validation.get('valid'):
                errors.append(validation.get('error', 'Invalid address.'))
            else:
                latitude = validation.get('latitude')
                longitude = validation.get('longitude')
                # Use the formatted address from Google
                address = validation.get('address', address)
        else:
            errors.append('Please select your address from the dropdown.')
        
        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('auth/register_recipient.html')
        
        # Create user
        user = User(
            email=email,
            password_hash=generate_password_hash(password),
            role='recipient'
        )
        db.session.add(user)
        db.session.flush()  # Get user ID
        
        # Create recipient profile with encrypted data
        encryption_service = get_encryption_service()
        recipient = Recipient(
            user_id=user.id,
            display_name=display_name,
            address_encrypted=encryption_service.encrypt(address)
        )
        
        # Set fuzzy location for distance-based matching
        if latitude and longitude:
            recipient.set_location(latitude, longitude)
        
        if phone:
            recipient.phone_encrypted = encryption_service.encrypt(phone)
        if notes:
            recipient.notes_encrypted = encryption_service.encrypt(notes)
        
        db.session.add(recipient)
        db.session.commit()
        
        # Audit log
        AuditService.log_recipient_registered(recipient.id)
        
        flash('Account created successfully. Please log in.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/register_recipient.html')


@bp.route('/register/volunteer', methods=['GET', 'POST'])
def register_volunteer():
    """Volunteer registration - redirects to application."""
    if current_user.is_authenticated:
        return redirect(url_for('auth.dashboard_redirect'))
    
    # Volunteer registration is handled through the apply flow
    return redirect(url_for('volunteer.apply'))


@bp.route('/dashboard')
@login_required
def dashboard_redirect():
    """Redirect to appropriate dashboard based on role."""
    if current_user.is_admin:
        return redirect(url_for('admin.dashboard'))
    elif current_user.is_volunteer:
        # Check if volunteer is approved
        volunteer = current_user.volunteer_profile
        if volunteer and volunteer.is_pending:
            return redirect(url_for('volunteer.pending'))
        return redirect(url_for('volunteer.dashboard'))
    elif current_user.is_recipient:
        return redirect(url_for('recipient.dashboard'))
    
    # Fallback
    return redirect(url_for('index'))
