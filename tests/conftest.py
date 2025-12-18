import pytest
from app import create_app, db
from models.user import User
from models.recipient import Recipient
from models.volunteer import Volunteer
from werkzeug.security import generate_password_hash


@pytest.fixture
def app():
    """Create application for testing."""
    app = create_app('testing')
    
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Create test CLI runner."""
    return app.test_cli_runner()


@pytest.fixture
def auth_client(client, app):
    """Create authenticated test client helper."""
    class AuthClient:
        def __init__(self, client, app):
            self.client = client
            self.app = app
        
        def login(self, email, password):
            return self.client.post('/login', data={
                'email': email,
                'password': password
            }, follow_redirects=True)
        
        def logout(self):
            return self.client.get('/logout', follow_redirects=True)
        
        def create_user(self, email, password, role='recipient'):
            with self.app.app_context():
                user = User(
                    email=email,
                    password_hash=generate_password_hash(password),
                    role=role
                )
                db.session.add(user)
                db.session.commit()
                return user.id
        
        def create_recipient(self, email, password, display_name='Test User'):
            with self.app.app_context():
                user = User(
                    email=email,
                    password_hash=generate_password_hash(password),
                    role='recipient'
                )
                db.session.add(user)
                db.session.flush()
                
                recipient = Recipient(
                    user_id=user.id,
                    display_name=display_name,
                    address_encrypted='encrypted_test_address',
                    general_area='Test Area'
                )
                db.session.add(recipient)
                db.session.commit()
                return user.id, recipient.id
        
        def create_volunteer(self, email, password, full_name='Test Volunteer', status='approved'):
            with self.app.app_context():
                user = User(
                    email=email,
                    password_hash=generate_password_hash(password),
                    role='volunteer'
                )
                db.session.add(user)
                db.session.flush()
                
                volunteer = Volunteer(
                    user_id=user.id,
                    full_name=full_name,
                    service_area='Test Area',
                    status=status,
                    attestation_completed=True
                )
                db.session.add(volunteer)
                db.session.commit()
                return user.id, volunteer.id
        
        def create_admin(self, email, password):
            return self.create_user(email, password, role='admin')
    
    return AuthClient(client, app)


@pytest.fixture
def sample_recipient(auth_client):
    """Create a sample recipient for testing."""
    user_id, recipient_id = auth_client.create_recipient(
        'recipient@test.com', 'password123', 'Test Recipient'
    )
    return {'user_id': user_id, 'recipient_id': recipient_id, 'email': 'recipient@test.com', 'password': 'password123'}


@pytest.fixture
def sample_volunteer(auth_client):
    """Create a sample approved volunteer for testing."""
    user_id, volunteer_id = auth_client.create_volunteer(
        'volunteer@test.com', 'password123', 'Test Volunteer'
    )
    return {'user_id': user_id, 'volunteer_id': volunteer_id, 'email': 'volunteer@test.com', 'password': 'password123'}


@pytest.fixture
def sample_admin(auth_client):
    """Create a sample admin for testing."""
    user_id = auth_client.create_admin('admin@test.com', 'password123')
    return {'user_id': user_id, 'email': 'admin@test.com', 'password': 'password123'}
