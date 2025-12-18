"""Tests for delivery workflow."""
import pytest
from datetime import datetime, timedelta

from app import db
from models.delivery import Delivery


def test_create_delivery_request(auth_client, sample_recipient, app):
    """Test recipient can create a delivery request."""
    auth_client.login(sample_recipient['email'], sample_recipient['password'])
    
    pickup_time = (datetime.now() + timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M')
    
    response = auth_client.client.post('/recipient/request/new', data={
        'store_name': 'Test Store',
        'pickup_address': '123 Store St',
        'order_name': 'Test Order',
        'pickup_time': pickup_time,
        'estimated_items': '5 items'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b'Delivery request created' in response.data or b'Test Store' in response.data
    
    # Verify delivery was created
    with app.app_context():
        delivery = Delivery.query.filter_by(store_name='Test Store').first()
        assert delivery is not None
        assert delivery.status == 'open'


def test_volunteer_can_view_available_deliveries(auth_client, sample_volunteer, sample_recipient, app):
    """Test volunteer can see available deliveries."""
    # Create a delivery first
    with app.app_context():
        delivery = Delivery(
            recipient_id=sample_recipient['recipient_id'],
            store_name='Available Store',
            pickup_address='456 Store Ave',
            order_name='Pickup Order',
            pickup_time=datetime.now() + timedelta(hours=1),
            status='open'
        )
        db.session.add(delivery)
        db.session.commit()
    
    auth_client.login(sample_volunteer['email'], sample_volunteer['password'])
    response = auth_client.client.get('/volunteer/dashboard')
    
    assert response.status_code == 200
    assert b'Available Store' in response.data


def test_volunteer_can_claim_delivery(auth_client, sample_volunteer, sample_recipient, app):
    """Test volunteer can claim an open delivery."""
    # Create a delivery
    with app.app_context():
        delivery = Delivery(
            recipient_id=sample_recipient['recipient_id'],
            store_name='Claimable Store',
            pickup_address='789 Store Blvd',
            order_name='Claim Order',
            pickup_time=datetime.now() + timedelta(hours=1),
            status='open'
        )
        db.session.add(delivery)
        db.session.commit()
        delivery_id = delivery.id
    
    auth_client.login(sample_volunteer['email'], sample_volunteer['password'])
    response = auth_client.client.post(f'/volunteer/request/{delivery_id}/claim', follow_redirects=True)
    
    assert response.status_code == 200
    
    # Verify delivery was claimed
    with app.app_context():
        delivery = Delivery.query.get(delivery_id)
        assert delivery.status == 'claimed'
        assert delivery.volunteer_id == sample_volunteer['volunteer_id']


def test_volunteer_claim_limit(auth_client, sample_volunteer, sample_recipient, app):
    """Test volunteer cannot exceed claim limit."""
    # Create 3 deliveries and claim 2
    with app.app_context():
        for i in range(3):
            delivery = Delivery(
                recipient_id=sample_recipient['recipient_id'],
                store_name=f'Store {i}',
                pickup_address=f'{i} Store St',
                order_name=f'Order {i}',
                pickup_time=datetime.now() + timedelta(hours=1),
                status='open'
            )
            db.session.add(delivery)
        db.session.commit()
        
        # Get delivery IDs
        deliveries = Delivery.query.all()
        delivery_ids = [d.id for d in deliveries]
    
    auth_client.login(sample_volunteer['email'], sample_volunteer['password'])
    
    # Claim first two
    auth_client.client.post(f'/volunteer/request/{delivery_ids[0]}/claim', follow_redirects=True)
    auth_client.client.post(f'/volunteer/request/{delivery_ids[1]}/claim', follow_redirects=True)
    
    # Try to claim third (should fail due to limit)
    response = auth_client.client.post(f'/volunteer/request/{delivery_ids[2]}/claim', follow_redirects=True)
    
    assert b'already have' in response.data.lower() or b'maximum' in response.data.lower()


def test_delivery_completion_flow(auth_client, sample_volunteer, sample_recipient, app):
    """Test full delivery completion flow."""
    # Create and claim a delivery
    with app.app_context():
        delivery = Delivery(
            recipient_id=sample_recipient['recipient_id'],
            volunteer_id=sample_volunteer['volunteer_id'],
            store_name='Complete Store',
            pickup_address='999 Store Way',
            order_name='Complete Order',
            pickup_time=datetime.now() + timedelta(hours=1),
            status='claimed',
            claimed_at=datetime.now()
        )
        db.session.add(delivery)
        db.session.commit()
        delivery_id = delivery.id
    
    auth_client.login(sample_volunteer['email'], sample_volunteer['password'])
    
    # Mark as picked up
    response = auth_client.client.post(f'/volunteer/request/{delivery_id}/pickup', follow_redirects=True)
    assert response.status_code == 200
    
    with app.app_context():
        delivery = Delivery.query.get(delivery_id)
        assert delivery.status == 'picked_up'
    
    # Mark as complete
    response = auth_client.client.post(f'/volunteer/request/{delivery_id}/complete', follow_redirects=True)
    assert response.status_code == 200
    
    with app.app_context():
        delivery = Delivery.query.get(delivery_id)
        assert delivery.status == 'completed'


def test_recipient_can_cancel_delivery(auth_client, sample_recipient, app):
    """Test recipient can cancel their delivery."""
    with app.app_context():
        delivery = Delivery(
            recipient_id=sample_recipient['recipient_id'],
            store_name='Cancel Store',
            pickup_address='111 Cancel St',
            order_name='Cancel Order',
            pickup_time=datetime.now() + timedelta(hours=1),
            status='open'
        )
        db.session.add(delivery)
        db.session.commit()
        delivery_id = delivery.id
    
    auth_client.login(sample_recipient['email'], sample_recipient['password'])
    response = auth_client.client.post(f'/recipient/request/{delivery_id}/cancel', follow_redirects=True)
    
    assert response.status_code == 200
    
    with app.app_context():
        delivery = Delivery.query.get(delivery_id)
        assert delivery.status == 'canceled'
