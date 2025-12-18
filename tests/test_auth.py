"""Tests for authentication routes."""
import pytest


def test_index_page(client):
    """Test landing page loads."""
    response = client.get('/')
    assert response.status_code == 200
    assert b'Community Delivery' in response.data


def test_login_page(client):
    """Test login page loads."""
    response = client.get('/login')
    assert response.status_code == 200
    assert b'Login' in response.data


def test_register_page(client):
    """Test register page loads."""
    response = client.get('/register')
    assert response.status_code == 200
    assert b'Join Our Community' in response.data


def test_login_with_valid_credentials(auth_client, sample_recipient):
    """Test login with valid credentials."""
    response = auth_client.login(sample_recipient['email'], sample_recipient['password'])
    assert response.status_code == 200
    assert b'Dashboard' in response.data or b'Welcome' in response.data


def test_login_with_invalid_credentials(auth_client):
    """Test login with invalid credentials."""
    response = auth_client.login('wrong@email.com', 'wrongpassword')
    assert b'Invalid email or password' in response.data


def test_logout(auth_client, sample_recipient):
    """Test logout."""
    auth_client.login(sample_recipient['email'], sample_recipient['password'])
    response = auth_client.logout()
    assert response.status_code == 200
    assert b'logged out' in response.data.lower()


def test_protected_route_requires_login(client):
    """Test that protected routes require authentication."""
    response = client.get('/recipient/dashboard')
    assert response.status_code == 302  # Redirect to login


def test_recipient_dashboard_accessible_after_login(auth_client, sample_recipient):
    """Test recipient can access dashboard after login."""
    auth_client.login(sample_recipient['email'], sample_recipient['password'])
    response = auth_client.client.get('/recipient/dashboard')
    assert response.status_code == 200


def test_volunteer_dashboard_requires_approval(auth_client):
    """Test pending volunteer cannot access dashboard."""
    user_id, volunteer_id = auth_client.create_volunteer(
        'pending@test.com', 'password123', 'Pending Vol', status='pending'
    )
    auth_client.login('pending@test.com', 'password123')
    response = auth_client.client.get('/volunteer/dashboard')
    assert response.status_code == 302  # Redirects to pending page


def test_admin_dashboard_requires_admin_role(auth_client, sample_recipient):
    """Test non-admin cannot access admin dashboard."""
    auth_client.login(sample_recipient['email'], sample_recipient['password'])
    response = auth_client.client.get('/admin/dashboard')
    assert response.status_code == 403


def test_admin_can_access_admin_dashboard(auth_client, sample_admin):
    """Test admin can access admin dashboard."""
    auth_client.login(sample_admin['email'], sample_admin['password'])
    response = auth_client.client.get('/admin/dashboard')
    assert response.status_code == 200
