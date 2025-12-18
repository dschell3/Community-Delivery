# Community Delivery Network

A coordination platform connecting immigrants with local volunteers for grocery pickup and delivery. Designed to minimize exposure risk for vulnerable community members while maintaining accountability and trust.

**This platform does not handle payments.** Recipients place and pay for their own grocery orders (pickup option), and volunteers simply deliver the items.

---

## Privacy & Trust Model

### Core Principles

1. **Recipient anonymity** — Recipients provide minimal identifying information. Real names are not required.
2. **Information revealed only when necessary** — Volunteers see recipient addresses only after claiming a delivery, and lose access upon completion.
3. **Volunteer accountability** — Volunteers are vetted before approval and their actions are logged.
4. **Audit without surveillance** — Logs track relationships and actions, not sensitive data.

### Recipient Data

| Field | Purpose | Visibility |
|-------|---------|------------|
| Display name (alias) | Shown to volunteers | Volunteers (on claim) |
| Delivery address | Delivery location | Volunteers (claim → completion only) |
| Phone/contact | Day-of coordination | Never directly shared; in-app messaging only |
| Pickup details | Store, order name, pickup time | Volunteers (on claim) |

### Volunteer Data

| Field | Purpose | Visibility |
|-------|---------|------------|
| Full name | Accountability | Admins; Recipients (on claim) |
| Photo | Identification at delivery | Recipients (on claim) |
| Email | Account access, notifications | Admins only |
| ID verification | Vetting (reviewed, not stored) | Admin only (temporary) |
| Self-attestation | Confirm not law enforcement | Stored as boolean |

### Vetting Process

1. Volunteer submits application (name, email, photo, service area, availability)
2. Volunteer uploads government ID and completes self-attestation checkbox
3. Admin reviews application and ID via admin dashboard
4. Admin approves or rejects; ID image is deleted after decision
5. Approved volunteers can claim deliveries

### Address Access Lifecycle

```
Request Posted → Volunteer Claims → ADDRESS REVEALED → Delivery Complete → ADDRESS HIDDEN
                                  ↓
                            (max 2 active claims per volunteer)
                                  ↓
                            Cancel → Address hidden, request returns to pool
```

### Data Retention

- **Active recipients**: Full data retained (address encrypted at rest)
- **Recipient-initiated deletion**: Address purged; tombstone record retained (recipient_id, associated volunteer_ids, last_active_date)
- **Auto-purge**: Accounts inactive 18+ months treated as deletion request
- **Delivery in progress during deletion**: Force-cancel, volunteer loses access immediately

### Audit Log

The audit log tracks **relationships and actions**, not sensitive data:

```
volunteer_id | recipient_id | action              | timestamp
-------------|--------------|---------------------|-------------------
5            | 12           | claimed_delivery    | 2025-01-15 09:30:00
5            | 12           | marked_complete     | 2025-01-15 11:45:00
```

If a volunteer is later reported, admins can identify which recipients they interacted with without the log itself containing addresses.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLIENT BROWSERS                         │
│                    (Recipients / Volunteers / Admins)           │
└─────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                         FLASK APPLICATION                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │    Auth     │  │   Routes    │  │  Templates  │             │
│  │  (sessions) │  │  (Blueprints)│  │  (Jinja2)   │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │  Messaging  │  │ File Upload │  │ Encryption  │             │
│  │  (polling)  │  │ (temp IDs)  │  │  (addresses)│             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
└─────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                          MySQL DATABASE                         │
│                                                                 │
│   users ──── volunteers ──── deliveries ──── recipients        │
│              (pending/approved)    │                            │
│                                    ├── messages                 │
│                                    └── audit_log                │
│                                                                 │
│   ratings                                                       │
└─────────────────────────────────────────────────────────────────┘
```

### Key Architectural Decisions

- **Polling for messages**: Frontend polls `/api/messages/<delivery_id>` every 10 seconds during active deliveries. Acceptable latency for coordination windows spanning 30-60 minutes.
- **Temporary file storage**: Volunteer ID photos stored temporarily during admin review, then deleted regardless of approval decision.
- **Address encryption**: Recipient addresses encrypted at rest using Fernet (symmetric encryption). Key stored in environment variable.
- **Single-tenant**: Each deployment is a separate instance with its own database. No multi-community logic in the data model.

> **Note for production deployments**: For true real-time messaging, consider upgrading hosting to support WebSockets (Flask-SocketIO) or using a service like Pusher. The polling approach is suitable for prototyping and small-scale use.

---

## Database Schema

See `schema.sql` for full implementation. Summary:

### Core Tables

**users**
- Base authentication table for all user types
- Fields: id, email, password_hash, role (admin/volunteer/recipient), created_at, last_active

**recipients**
- Extends users for recipient-specific data
- Fields: user_id (FK), display_name, address_encrypted, phone_encrypted, created_at
- Address and phone encrypted at rest

**volunteers**  
- Extends users for volunteer-specific data
- Fields: user_id (FK), full_name, photo_path, service_area, availability_notes, status (pending/approved/suspended), attestation_completed, reviewed_by, reviewed_at

**deliveries**
- Core coordination record
- Fields: id, recipient_id (FK), volunteer_id (FK, nullable), store_name, pickup_address, order_name, pickup_time, status (open/claimed/in_progress/completed/canceled), created_at, claimed_at, completed_at

**messages**
- In-app messaging tied to deliveries
- Fields: id, delivery_id (FK), sender_id (FK), content, sent_at

**ratings**
- Recipient ratings of volunteers
- Fields: id, delivery_id (FK), volunteer_id (FK), recipient_id (FK), score (1-5), comment, created_at

**audit_log**
- Relationship and action tracking (no sensitive data)
- Fields: id, volunteer_id, recipient_id, action, timestamp

---

## Routes Overview

### Public Routes

| Route | Method | Description |
|-------|--------|-------------|
| `/` | GET | Landing page |
| `/register` | GET, POST | User registration (role selection) |
| `/login` | GET, POST | User login |
| `/logout` | GET | End session |

### Recipient Routes

| Route | Method | Description |
|-------|--------|-------------|
| `/recipient/dashboard` | GET | View active/past delivery requests |
| `/recipient/request/new` | GET, POST | Create new delivery request |
| `/recipient/request/<id>` | GET | View request details, message volunteer |
| `/recipient/request/<id>/cancel` | POST | Cancel open request |
| `/recipient/request/<id>/complete` | POST | Mark delivered, leave rating |
| `/recipient/settings` | GET, POST | Update profile, contact info |
| `/recipient/delete-account` | POST | Initiate account deletion |

### Volunteer Routes

| Route | Method | Description |
|-------|--------|-------------|
| `/volunteer/apply` | GET, POST | Application form + ID upload + attestation |
| `/volunteer/dashboard` | GET | View available requests in service area, active claims |
| `/volunteer/request/<id>` | GET | View request details (address revealed if claimed) |
| `/volunteer/request/<id>/claim` | POST | Claim a delivery |
| `/volunteer/request/<id>/cancel` | POST | Release claim, return to pool |
| `/volunteer/request/<id>/complete` | POST | Mark delivery complete |
| `/volunteer/settings` | GET, POST | Update availability, service area |

### Messaging (Polling API)

| Route | Method | Description |
|-------|--------|-------------|
| `/api/messages/<delivery_id>` | GET | Fetch messages (polled every 10s) |
| `/api/messages/<delivery_id>` | POST | Send a message |

### Admin Routes

| Route | Method | Description |
|-------|--------|-------------|
| `/admin/dashboard` | GET | Overview: pending applications, active deliveries, flagged items |
| `/admin/volunteers` | GET | List all volunteers with status filters |
| `/admin/volunteers/<id>` | GET | View volunteer profile, history, ratings |
| `/admin/volunteers/<id>/approve` | POST | Approve pending volunteer |
| `/admin/volunteers/<id>/reject` | POST | Reject pending volunteer |
| `/admin/volunteers/<id>/suspend` | POST | Suspend active volunteer |
| `/admin/audit-log` | GET | View audit log (filterable by volunteer, date range) |
| `/admin/recipients/<id>` | GET | View recipient profile (for investigating issues) |

---

## Setup Instructions

### Prerequisites

- Python 3.10+
- MySQL 8.0+
- Git

### Local Development

```bash
# Clone repository
git clone <repository-url>
cd community-delivery

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your values:
#   - DATABASE_URL
#   - SECRET_KEY
#   - ENCRYPTION_KEY (generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

# Initialize database
flask db init
flask db migrate
flask db upgrade

# Create initial admin user
flask create-admin --email admin@example.com --password <secure-password>

# Run development server
flask run
```

### Deployment on Render

1. Create a new Web Service connected to your repository
2. Set build command: `pip install -r requirements.txt`
3. Set start command: `gunicorn app:app`
4. Add environment variables (DATABASE_URL, SECRET_KEY, ENCRYPTION_KEY)
5. Create a MySQL database (Render offers managed MySQL, or use PlanetScale free tier)
6. Update DATABASE_URL to point to your production database

### For Other Communities

To deploy this for your own community:

1. Fork this repository
2. Follow deployment instructions above
3. Customize branding in `templates/` and `static/`
4. Update contact information and any region-specific content
5. Create your admin account
6. Share volunteer application link with your vetting organization
7. Share recipient registration link through trusted community channels

---

## Security Considerations

- **HTTPS required** in production (Render provides this automatically)
- **Address encryption key** must be kept secure; rotation requires re-encryption of all addresses
- **Session security**: Use secure, HTTP-only cookies
- **ID photos**: Ensure temp directory is not publicly accessible; implement cleanup job
- **Rate limiting**: Consider adding rate limiting to prevent abuse (Flask-Limiter)
- **SQL injection**: Use parameterized queries (SQLAlchemy handles this)
- **CSRF protection**: Enable Flask-WTF CSRF protection on all forms

---

## Future Enhancements

- [ ] Real-time messaging via WebSockets
- [ ] SMS notifications (Twilio integration)
- [ ] Mobile-optimized PWA
- [ ] Volunteer scheduling/calendar integration
- [ ] Multi-language support (Spanish priority)
- [ ] Delivery route optimization for volunteers with multiple claims
- [ ] Integration with grocery store APIs for order status

---

## License

[Choose appropriate open-source license - suggest MIT or AGPLv3]

---

## Contributing

Contributions welcome. Please read CONTRIBUTING.md before submitting PRs.

For security issues, please email [security contact] rather than opening a public issue.
