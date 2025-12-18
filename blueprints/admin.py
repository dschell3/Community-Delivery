from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user

from app import db
from models.volunteer import Volunteer, VolunteerIdUpload
from models.recipient import Recipient
from models.delivery import Delivery
from models.audit import AuditLog
from services.audit_service import AuditService
from services.cleanup_service import delete_volunteer_id_uploads
from services.encryption_service import get_encryption_service

bp = Blueprint('admin', __name__)


def admin_required(f):
    """Decorator to require admin role."""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        if not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


@bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    """Admin dashboard - overview of system status."""
    # Pending volunteer applications
    pending_volunteers = Volunteer.query.filter(
        Volunteer.status == 'pending'
    ).count()
    
    # Active deliveries
    active_deliveries = Delivery.query.filter(
        Delivery.status.in_(['open', 'claimed', 'picked_up'])
    ).count()
    
    # Open deliveries (waiting for volunteers)
    open_deliveries = Delivery.query.filter(
        Delivery.status == 'open'
    ).count()
    
    # Recent activity
    recent_activity = AuditLog.get_recent(limit=20)
    
    # Stats
    total_volunteers = Volunteer.query.filter(
        Volunteer.status == 'approved'
    ).count()
    
    total_recipients = Recipient.query.filter(
        Recipient.deleted_at.is_(None)
    ).count()
    
    completed_deliveries = Delivery.query.filter(
        Delivery.status == 'completed'
    ).count()
    
    return render_template(
        'admin/dashboard.html',
        pending_volunteers=pending_volunteers,
        active_deliveries=active_deliveries,
        open_deliveries=open_deliveries,
        recent_activity=recent_activity,
        total_volunteers=total_volunteers,
        total_recipients=total_recipients,
        completed_deliveries=completed_deliveries
    )


@bp.route('/volunteers')
@login_required
@admin_required
def volunteer_list():
    """List all volunteers with status filters."""
    status_filter = request.args.get('status', 'all')
    
    query = Volunteer.query
    if status_filter != 'all':
        query = query.filter(Volunteer.status == status_filter)
    
    volunteers = query.order_by(Volunteer.created_at.desc()).all()
    
    return render_template(
        'admin/volunteer_list.html',
        volunteers=volunteers,
        status_filter=status_filter
    )


@bp.route('/volunteers/<int:id>')
@login_required
@admin_required
def volunteer_detail(id):
    """View volunteer profile, history, and ratings."""
    volunteer = Volunteer.query.get_or_404(id)
    
    # Get delivery history
    deliveries = Delivery.query.filter(
        Delivery.volunteer_id == volunteer.id
    ).order_by(Delivery.created_at.desc()).limit(20).all()
    
    # Get audit history
    audit_history = AuditLog.get_for_volunteer(volunteer.id, limit=50)
    
    # Get ratings
    ratings = volunteer.ratings_received.order_by(
        db.desc('created_at')
    ).limit(10).all()
    
    return render_template(
        'admin/volunteer_detail.html',
        volunteer=volunteer,
        deliveries=deliveries,
        audit_history=audit_history,
        ratings=ratings
    )


@bp.route('/volunteers/<int:id>/review')
@login_required
@admin_required
def volunteer_review(id):
    """Review volunteer application with ID verification."""
    volunteer = Volunteer.query.get_or_404(id)
    
    if volunteer.status != 'pending':
        flash('This volunteer has already been reviewed.', 'info')
        return redirect(url_for('admin.volunteer_detail', id=id))
    
    # Get ID upload
    id_upload = VolunteerIdUpload.query.filter(
        VolunteerIdUpload.volunteer_id == volunteer.id
    ).first()
    
    return render_template(
        'admin/volunteer_review.html',
        volunteer=volunteer,
        id_upload=id_upload
    )


@bp.route('/volunteers/<int:id>/approve', methods=['POST'])
@login_required
@admin_required
def volunteer_approve(id):
    """Approve a pending volunteer."""
    volunteer = Volunteer.query.get_or_404(id)
    
    if volunteer.status != 'pending':
        flash('This volunteer has already been reviewed.', 'warning')
        return redirect(url_for('admin.volunteer_detail', id=id))
    
    volunteer.approve(current_user)
    
    # Delete ID upload after review
    delete_volunteer_id_uploads(volunteer.id)
    
    # Audit log
    AuditService.log_volunteer_approved(volunteer.id, current_user.id)
    
    flash(f'{volunteer.full_name} has been approved.', 'success')
    return redirect(url_for('admin.volunteer_list', status='pending'))


@bp.route('/volunteers/<int:id>/reject', methods=['POST'])
@login_required
@admin_required
def volunteer_reject(id):
    """Reject a pending volunteer."""
    volunteer = Volunteer.query.get_or_404(id)
    
    if volunteer.status != 'pending':
        flash('This volunteer has already been reviewed.', 'warning')
        return redirect(url_for('admin.volunteer_detail', id=id))
    
    reason = request.form.get('reason', '').strip() or None
    
    volunteer.reject(current_user, reason)
    
    # Delete ID upload after review
    delete_volunteer_id_uploads(volunteer.id)
    
    # Audit log
    AuditService.log_volunteer_rejected(volunteer.id, current_user.id, reason)
    
    flash(f'{volunteer.full_name} has been rejected.', 'info')
    return redirect(url_for('admin.volunteer_list', status='pending'))


@bp.route('/volunteers/<int:id>/suspend', methods=['POST'])
@login_required
@admin_required
def volunteer_suspend(id):
    """Suspend an approved volunteer."""
    volunteer = Volunteer.query.get_or_404(id)
    
    if volunteer.status != 'approved':
        flash('Only approved volunteers can be suspended.', 'warning')
        return redirect(url_for('admin.volunteer_detail', id=id))
    
    reason = request.form.get('reason', '').strip() or None
    
    volunteer.suspend(current_user, reason)
    
    # Audit log
    AuditService.log_volunteer_suspended(volunteer.id, current_user.id, reason)
    
    flash(f'{volunteer.full_name} has been suspended.', 'warning')
    return redirect(url_for('admin.volunteer_detail', id=id))


@bp.route('/volunteers/<int:id>/reinstate', methods=['POST'])
@login_required
@admin_required
def volunteer_reinstate(id):
    """Reinstate a suspended volunteer."""
    volunteer = Volunteer.query.get_or_404(id)
    
    if volunteer.status != 'suspended':
        flash('Only suspended volunteers can be reinstated.', 'warning')
        return redirect(url_for('admin.volunteer_detail', id=id))
    
    volunteer.status = 'approved'
    volunteer.suspension_reason = None
    volunteer.reviewed_by = current_user.id
    volunteer.reviewed_at = db.func.now()
    db.session.commit()
    
    flash(f'{volunteer.full_name} has been reinstated.', 'success')
    return redirect(url_for('admin.volunteer_detail', id=id))


@bp.route('/audit-log')
@login_required
@admin_required
def audit_log():
    """View audit log with filters."""
    action_filter = request.args.get('action')
    volunteer_id = request.args.get('volunteer_id', type=int)
    recipient_id = request.args.get('recipient_id', type=int)
    
    query = AuditLog.query
    
    if action_filter:
        query = query.filter(AuditLog.action == action_filter)
    if volunteer_id:
        query = query.filter(AuditLog.volunteer_id == volunteer_id)
    if recipient_id:
        query = query.filter(AuditLog.recipient_id == recipient_id)
    
    entries = query.order_by(AuditLog.timestamp.desc()).limit(100).all()
    
    # Get action types for filter dropdown
    action_types = [
        AuditLog.VOLUNTEER_REGISTERED,
        AuditLog.VOLUNTEER_APPROVED,
        AuditLog.VOLUNTEER_REJECTED,
        AuditLog.VOLUNTEER_SUSPENDED,
        AuditLog.DELIVERY_CREATED,
        AuditLog.DELIVERY_CLAIMED,
        AuditLog.DELIVERY_CANCELED,
        AuditLog.DELIVERY_PICKED_UP,
        AuditLog.DELIVERY_COMPLETED,
        AuditLog.MESSAGE_SENT,
        AuditLog.ADDRESS_ACCESSED,
        AuditLog.RATING_SUBMITTED,
        AuditLog.RECIPIENT_REGISTERED,
        AuditLog.RECIPIENT_DELETED,
    ]
    
    return render_template(
        'admin/audit_log.html',
        entries=entries,
        action_types=action_types,
        current_action=action_filter,
        current_volunteer_id=volunteer_id,
        current_recipient_id=recipient_id
    )


@bp.route('/recipients/<int:id>')
@login_required
@admin_required
def recipient_detail(id):
    """View recipient profile (for investigating issues)."""
    recipient = Recipient.query.get_or_404(id)
    
    # Log admin viewing recipient
    AuditService.log_admin_viewed_recipient(current_user.id, recipient.id)
    
    encryption_service = get_encryption_service()
    
    # Decrypt address only if needed for investigation
    show_address = request.args.get('show_address') == 'true'
    address = recipient.get_address(encryption_service) if show_address else None
    
    # Get delivery history
    deliveries = Delivery.query.filter(
        Delivery.recipient_id == recipient.id
    ).order_by(Delivery.created_at.desc()).limit(20).all()
    
    # Get audit history
    audit_history = AuditLog.get_for_recipient(recipient.id, limit=50)
    
    return render_template(
        'admin/recipient_detail.html',
        recipient=recipient,
        address=address,
        show_address=show_address,
        deliveries=deliveries,
        audit_history=audit_history
    )
