# Project Structure

```
community-delivery/
│
├── app.py                      # Application factory and entry point
├── config.py                   # Configuration classes
├── requirements.txt            # Python dependencies
├── schema.sql                  # Database schema
├── .env.example                # Environment variable template
├── README.md                   # Project documentation
│
├── blueprints/                 # Route blueprints (organized by role)
│   ├── __init__.py
│   ├── auth.py                 # /login, /logout, /register
│   ├── recipient.py            # /recipient/* routes
│   ├── volunteer.py            # /volunteer/* routes
│   ├── admin.py                # /admin/* routes
│   └── api.py                  # /api/* routes (messaging)
│
├── models/                     # SQLAlchemy models
│   ├── __init__.py
│   ├── user.py                 # User, Role
│   ├── recipient.py            # Recipient, RecipientTombstone
│   ├── volunteer.py            # Volunteer, VolunteerIdUpload
│   ├── delivery.py             # Delivery
│   ├── message.py              # Message
│   ├── rating.py               # Rating
│   └── audit.py                # AuditLog
│
├── services/                   # Business logic layer
│   ├── __init__.py
│   ├── auth_service.py         # Authentication logic
│   ├── delivery_service.py     # Delivery claiming, completion logic
│   ├── encryption_service.py   # Address/phone encryption/decryption
│   ├── audit_service.py        # Audit logging
│   ├── notification_service.py # Email notifications (future)
│   └── cleanup_service.py      # Expired uploads, inactive accounts
│
├── templates/                  # Jinja2 templates
│   ├── base.html               # Base layout
│   ├── landing.html            # Public landing page
│   │
│   ├── auth/
│   │   ├── login.html
│   │   ├── register.html
│   │   └── register_role.html  # Role selection
│   │
│   ├── recipient/
│   │   ├── dashboard.html
│   │   ├── request_new.html
│   │   ├── request_detail.html
│   │   ├── complete.html       # Rating form
│   │   └── settings.html
│   │
│   ├── volunteer/
│   │   ├── apply.html          # Application + ID upload
│   │   ├── pending.html        # "Application under review" page
│   │   ├── dashboard.html
│   │   ├── request_detail.html
│   │   └── settings.html
│   │
│   ├── admin/
│   │   ├── dashboard.html
│   │   ├── volunteer_list.html
│   │   ├── volunteer_detail.html
│   │   ├── volunteer_review.html  # ID verification view
│   │   ├── audit_log.html
│   │   └── recipient_detail.html
│   │
│   ├── messages/
│   │   └── _chat.html          # Partial for message display
│   │
│   └── errors/
│       ├── 404.html
│       ├── 403.html
│       └── 500.html
│
├── static/
│   ├── css/
│   │   └── style.css
│   ├── js/
│   │   ├── messages.js         # Polling logic for chat
│   │   └── forms.js            # Form validation
│   └── images/
│       └── logo.png
│
├── uploads/                    # Temporary file storage (gitignored)
│   └── id_photos/              # Volunteer ID uploads (auto-cleaned)
│
├── migrations/                 # Flask-Migrate database migrations
│
└── tests/                      # Test suite
    ├── __init__.py
    ├── conftest.py             # Pytest fixtures
    ├── test_auth.py
    ├── test_delivery.py
    ├── test_encryption.py
    └── test_audit.py
```

## Key Files Explained

### `app.py`
Application factory pattern - creates and configures the Flask app:
```python
def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    
    # Register blueprints
    from blueprints import auth, recipient, volunteer, admin, api
    app.register_blueprint(auth.bp)
    app.register_blueprint(recipient.bp, url_prefix='/recipient')
    app.register_blueprint(volunteer.bp, url_prefix='/volunteer')
    app.register_blueprint(admin.bp, url_prefix='/admin')
    app.register_blueprint(api.bp, url_prefix='/api')
    
    return app
```

### `services/encryption_service.py`
Handles all encryption/decryption of sensitive data:
```python
from cryptography.fernet import Fernet

class EncryptionService:
    def __init__(self, key):
        self.cipher = Fernet(key.encode())
    
    def encrypt(self, plaintext):
        return self.cipher.encrypt(plaintext.encode()).decode()
    
    def decrypt(self, ciphertext):
        return self.cipher.decrypt(ciphertext.encode()).decode()
```

### `services/audit_service.py`
Centralized audit logging:
```python
def log_action(volunteer_id=None, recipient_id=None, delivery_id=None, 
               admin_id=None, action=None, details=None, ip_address=None):
    entry = AuditLog(
        volunteer_id=volunteer_id,
        recipient_id=recipient_id,
        delivery_id=delivery_id,
        admin_id=admin_id,
        action=action,
        details=details,
        ip_address=ip_address
    )
    db.session.add(entry)
    db.session.commit()
```

### `static/js/messages.js`
Polling implementation for messaging:
```javascript
const POLL_INTERVAL = 10000; // 10 seconds

function pollMessages(deliveryId, lastMessageId) {
    fetch(`/api/messages/${deliveryId}?after=${lastMessageId}`)
        .then(response => response.json())
        .then(data => {
            if (data.messages.length > 0) {
                appendMessages(data.messages);
                lastMessageId = data.messages[data.messages.length - 1].id;
            }
            setTimeout(() => pollMessages(deliveryId, lastMessageId), POLL_INTERVAL);
        })
        .catch(error => {
            console.error('Polling error:', error);
            setTimeout(() => pollMessages(deliveryId, lastMessageId), POLL_INTERVAL);
        });
}
```
