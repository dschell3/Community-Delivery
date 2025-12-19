"""
Email notification service using Resend.

This service is optional - if RESEND_API_KEY is not configured,
notifications will be logged but not sent.
"""
import resend
from flask import current_app, render_template_string


class NotificationService:
    """Service for sending email notifications via Resend."""
    
    # Email templates
    TEMPLATES = {
        'delivery_claimed': {
            'subject': 'Good news! A volunteer has claimed your delivery',
            'body': '''
Hello {{ recipient_name }},

Great news! {{ volunteer_name }} has claimed your delivery request and will be picking up your groceries soon.

Delivery Details:
- Store: {{ store_name }}
- Pickup Time: {{ pickup_time }}

You can message your volunteer through the app to coordinate.

Log in to view details: {{ app_url }}/recipient/request/{{ delivery_id }}

Thank you for using Community Delivery Network!
'''
        },
        'delivery_picked_up': {
            'subject': 'Your groceries have been picked up!',
            'body': '''
Hello {{ recipient_name }},

{{ volunteer_name }} has picked up your groceries from {{ store_name }} and is on the way to you!

You can message your volunteer if you need to provide any last-minute instructions.

Log in to track: {{ app_url }}/recipient/request/{{ delivery_id }}

Thank you for using Community Delivery Network!
'''
        },
        'delivery_completed': {
            'subject': 'Delivery completed - Please rate your experience',
            'body': '''
Hello {{ recipient_name }},

Your delivery from {{ store_name }} has been completed by {{ volunteer_name }}.

We'd love to hear about your experience! Please take a moment to rate your volunteer:

{{ app_url }}/recipient/request/{{ delivery_id }}/complete

Your feedback helps us maintain a trusted community of volunteers.

Thank you for using Community Delivery Network!
'''
        },
        'delivery_canceled_notify_volunteer': {
            'subject': 'Delivery request has been canceled',
            'body': '''
Hello {{ volunteer_name }},

The delivery you claimed has been canceled by the recipient.

Canceled Delivery:
- Store: {{ store_name }}
- Was scheduled for: {{ pickup_time }}

This delivery has been removed from your active deliveries. 

Check the dashboard for other available deliveries: {{ app_url }}/volunteer/dashboard

Thank you for your willingness to help!
'''
        },
        'delivery_canceled_account_deleted': {
            'subject': 'Delivery canceled - Recipient account closed',
            'body': '''
Hello {{ volunteer_name }},

A delivery you claimed has been automatically canceled because the recipient closed their account.

Canceled Delivery:
- Store: {{ store_name }}
- Was scheduled for: {{ pickup_time }}

We apologize for any inconvenience. This delivery has been removed from your active deliveries.

If you had already picked up the groceries, please contact an administrator immediately for assistance.

Check the dashboard for other available deliveries: {{ app_url }}/volunteer/dashboard

Thank you for your understanding.
'''
        },
        'volunteer_approved': {
            'subject': 'Welcome! Your volunteer application has been approved',
            'body': '''
Hello {{ volunteer_name }},

Congratulations! Your application to volunteer with Community Delivery Network has been approved.

You can now:
- Browse available delivery requests in your area
- Claim deliveries that fit your schedule
- Help community members receive their groceries

Get started now: {{ app_url }}/volunteer/dashboard

Thank you for joining our community of helpers!
'''
        },
        'volunteer_rejected': {
            'subject': 'Update on your volunteer application',
            'body': '''
Hello {{ volunteer_name }},

Thank you for your interest in volunteering with Community Delivery Network.

After reviewing your application, we are unable to approve it at this time.

{% if reason %}
Reason: {{ reason }}
{% endif %}

If you believe this was made in error or have questions, please contact the organization administrator.

Thank you for your understanding.
'''
        },
        'volunteer_suspended': {
            'subject': 'Your volunteer account has been suspended',
            'body': '''
Hello {{ volunteer_name }},

Your volunteer account with Community Delivery Network has been suspended.

{% if reason %}
Reason: {{ reason }}
{% endif %}

Any active deliveries you had claimed have been returned to the pool for other volunteers.

If you have questions about this suspension, please contact the organization administrator.
'''
        }
    }
    
    @classmethod
    def is_configured(cls):
        """Check if Resend is configured."""
        return bool(current_app.config.get('RESEND_API_KEY'))
    
    @classmethod
    def get_app_url(cls):
        """Get the application URL for links in emails."""
        return current_app.config.get('APP_URL', 'http://localhost:5000')
    
    @classmethod
    def get_from_email(cls):
        """Get the from email address."""
        return current_app.config.get('NOTIFICATION_FROM_EMAIL', 'Community Delivery <noreply@yourdomain.com>')
    
    @classmethod
    def render_template(cls, template_name, **context):
        """Render an email template with context."""
        template = cls.TEMPLATES.get(template_name)
        if not template:
            raise ValueError(f"Unknown template: {template_name}")
        
        # Add app_url to context
        context['app_url'] = cls.get_app_url()
        
        subject = render_template_string(template['subject'], **context)
        body = render_template_string(template['body'], **context)
        
        return subject, body
    
    @classmethod
    def send_email(cls, to_email, subject, body):
        """Send an email via Resend."""
        if not cls.is_configured():
            current_app.logger.info(f"[NOTIFICATION - NOT SENT - Resend not configured] To: {to_email}, Subject: {subject}")
            return False
        
        try:
            # Set API key
            resend.api_key = current_app.config['RESEND_API_KEY']
            
            # Send email
            result = resend.Emails.send({
                "from": cls.get_from_email(),
                "to": [to_email],
                "subject": subject,
                "text": body
            })
            
            if result and result.get('id'):
                current_app.logger.info(f"[NOTIFICATION SENT] To: {to_email}, Subject: {subject}, ID: {result['id']}")
                return True
            else:
                current_app.logger.error(f"[NOTIFICATION FAILED] No ID returned, To: {to_email}")
                return False
                
        except Exception as e:
            current_app.logger.error(f"[NOTIFICATION ERROR] {str(e)}, To: {to_email}")
            return False
    
    # Convenience methods for specific notifications
    
    @classmethod
    def notify_delivery_claimed(cls, delivery):
        """Notify recipient that their delivery has been claimed."""
        recipient = delivery.recipient
        volunteer = delivery.volunteer
        
        subject, body = cls.render_template(
            'delivery_claimed',
            recipient_name=recipient.display_name,
            volunteer_name=volunteer.full_name,
            store_name=delivery.store_name,
            pickup_time=delivery.pickup_time.strftime('%B %d, %Y at %I:%M %p'),
            delivery_id=delivery.id
        )
        
        return cls.send_email(recipient.user.email, subject, body)
    
    @classmethod
    def notify_delivery_picked_up(cls, delivery):
        """Notify recipient that groceries have been picked up."""
        recipient = delivery.recipient
        volunteer = delivery.volunteer
        
        subject, body = cls.render_template(
            'delivery_picked_up',
            recipient_name=recipient.display_name,
            volunteer_name=volunteer.full_name,
            store_name=delivery.store_name,
            delivery_id=delivery.id
        )
        
        return cls.send_email(recipient.user.email, subject, body)
    
    @classmethod
    def notify_delivery_completed(cls, delivery):
        """Notify recipient that delivery is complete and ask for rating."""
        recipient = delivery.recipient
        volunteer = delivery.volunteer
        
        subject, body = cls.render_template(
            'delivery_completed',
            recipient_name=recipient.display_name,
            volunteer_name=volunteer.full_name,
            store_name=delivery.store_name,
            delivery_id=delivery.id
        )
        
        return cls.send_email(recipient.user.email, subject, body)
    
    @classmethod
    def notify_volunteer_delivery_canceled(cls, volunteer, delivery, reason='recipient'):
        """Notify volunteer that a delivery they claimed was canceled."""
        if reason == 'account_deleted':
            template = 'delivery_canceled_account_deleted'
        else:
            template = 'delivery_canceled_notify_volunteer'
        
        subject, body = cls.render_template(
            template,
            volunteer_name=volunteer.full_name,
            store_name=delivery.store_name,
            pickup_time=delivery.pickup_time.strftime('%B %d, %Y at %I:%M %p')
        )
        
        return cls.send_email(volunteer.user.email, subject, body)
    
    @classmethod
    def notify_volunteer_approved(cls, volunteer):
        """Notify volunteer that their application was approved."""
        subject, body = cls.render_template(
            'volunteer_approved',
            volunteer_name=volunteer.full_name
        )
        
        return cls.send_email(volunteer.user.email, subject, body)
    
    @classmethod
    def notify_volunteer_rejected(cls, volunteer, reason=None):
        """Notify volunteer that their application was rejected."""
        subject, body = cls.render_template(
            'volunteer_rejected',
            volunteer_name=volunteer.full_name,
            reason=reason
        )
        
        return cls.send_email(volunteer.user.email, subject, body)
    
    @classmethod
    def notify_volunteer_suspended(cls, volunteer, reason=None):
        """Notify volunteer that their account was suspended."""
        subject, body = cls.render_template(
            'volunteer_suspended',
            volunteer_name=volunteer.full_name,
            reason=reason
        )
        
        return cls.send_email(volunteer.user.email, subject, body)