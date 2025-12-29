#!/usr/bin/env python3
"""
Seed script for demo deployment.
Creates realistic demo data for showcasing the application.

Run with: python seed_demo.py
"""
import os
import sys
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

# Ensure we can import from the app
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from models.user import User
from models.recipient import Recipient
from models.volunteer import Volunteer
from models.delivery import Delivery
from models.rating import Rating
from services.encryption_service import EncryptionService


def seed_demo_data():
    """Populate database with demo data."""
    
    app = create_app('production')
    
    with app.app_context():
        # Check if data already exists
        if User.query.first():
            print("Database already contains data. Skipping seed.")
            return
        
        print("Seeding demo data...")
        
        # Initialize encryption service
        encryption_service = EncryptionService()
        
        # ===========================================
        # ADMIN USER
        # ===========================================
        admin = User(
            email='admin@demo.aquiestamos.org',
            password_hash=generate_password_hash('demo2025'),
            role='admin',
            is_active=True
        )
        db.session.add(admin)
        db.session.flush()
        print(f"  Created admin: {admin.email}")
        
        # ===========================================
        # VOLUNTEERS
        # ===========================================
        volunteers_data = [
            {
                'email': 'carlos.v@demo.aquiestamos.org',
                'full_name': 'Carlos Mendoza (Demo Volunteer)',
                'service_center_address': 'Midtown Sacramento, CA',
                'service_center_lat': 38.5767,
                'service_center_lng': -121.4823,
                'service_radius_miles': 15,
                'status': 'approved',
                'total_deliveries': 12,
                'average_rating': 4.8
            },
            {
                'email': 'sarah.v@demo.aquiestamos.org',
                'full_name': 'Sarah Chen (Demo Volunteer)',
                'service_center_address': 'Elk Grove, CA',
                'service_center_lat': 38.4088,
                'service_center_lng': -121.3716,
                'service_radius_miles': 10,
                'status': 'approved',
                'total_deliveries': 8,
                'average_rating': 5.0
            },
            {
                'email': 'pending.v@demo.aquiestamos.org',
                'full_name': 'New Applicant (Demo Pending)',
                'service_center_address': 'Roseville, CA',
                'service_center_lat': 38.7521,
                'service_center_lng': -121.2880,
                'service_radius_miles': 10,
                'status': 'pending',
                'total_deliveries': 0,
                'average_rating': None
            }
        ]
        
        volunteer_objects = []
        for v_data in volunteers_data:
            user = User(
                email=v_data['email'],
                password_hash=generate_password_hash('demo2025'),
                role='volunteer',
                is_active=True
            )
            db.session.add(user)
            db.session.flush()
            
            volunteer = Volunteer(
                user_id=user.id,
                full_name=v_data['full_name'],
                service_center_address=v_data['service_center_address'],
                service_center_lat=v_data['service_center_lat'],
                service_center_lng=v_data['service_center_lng'],
                service_radius_miles=v_data['service_radius_miles'],
                status=v_data['status'],
                attestation_completed=True,
                total_deliveries=v_data['total_deliveries'],
                average_rating=v_data['average_rating'],
                reviewed_by=admin.id if v_data['status'] == 'approved' else None,
                reviewed_at=datetime.utcnow() - timedelta(days=30) if v_data['status'] == 'approved' else None
            )
            db.session.add(volunteer)
            db.session.flush()
            volunteer_objects.append(volunteer)
            print(f"  Created volunteer: {v_data['full_name']} ({v_data['status']})")
        
        # ===========================================
        # RECIPIENTS
        # ===========================================
        # Note: Using obviously fake addresses in Sacramento area
        # Real addresses should NEVER be committed to code
        recipients_data = [
            {
                'email': 'maria.r@demo.aquiestamos.org',
                'display_name': 'Maria G. (Demo)',
                'address': '1234 Demo Street, Sacramento, CA 95814',
                'latitude': 38.58,  # Fuzzy - 2 decimal places
                'longitude': -121.49,
                'phone': '555-0101',
                'notes': 'Gate code: #1234 (DEMO)'
            },
            {
                'email': 'jose.r@demo.aquiestamos.org',
                'display_name': 'José R. (Demo)',
                'address': '5678 Example Ave, Sacramento, CA 95820',
                'latitude': 38.54,
                'longitude': -121.45,
                'phone': '555-0102',
                'notes': 'Second floor apartment - please call when arriving'
            },
            {
                'email': 'ana.r@demo.aquiestamos.org',
                'display_name': 'Ana L. (Demo)',
                'address': '9012 Sample Blvd, Elk Grove, CA 95624',
                'latitude': 38.41,
                'longitude': -121.37,
                'phone': None,
                'notes': None
            }
        ]
        
        recipient_objects = []
        for r_data in recipients_data:
            user = User(
                email=r_data['email'],
                password_hash=generate_password_hash('demo2025'),
                role='recipient',
                is_active=True
            )
            db.session.add(user)
            db.session.flush()
            
            recipient = Recipient(
                user_id=user.id,
                display_name=r_data['display_name'],
                address_encrypted=encryption_service.encrypt(r_data['address']),
                latitude=r_data['latitude'],
                longitude=r_data['longitude']
            )
            
            if r_data['phone']:
                recipient.phone_encrypted = encryption_service.encrypt(r_data['phone'])
            if r_data['notes']:
                recipient.notes_encrypted = encryption_service.encrypt(r_data['notes'])
            
            db.session.add(recipient)
            db.session.flush()
            recipient_objects.append(recipient)
            print(f"  Created recipient: {r_data['display_name']}")
        
        # ===========================================
        # DELIVERIES
        # ===========================================
        now = datetime.utcnow()
        
        deliveries_data = [
            # Open delivery - available to claim
            {
                'recipient': recipient_objects[0],
                'volunteer': None,
                'store_name': 'Safeway - Arden Way',
                'pickup_address': '2501 Arden Way, Sacramento, CA 95825',
                'store_lat': 38.6018,
                'store_lng': -121.4078,
                'order_name': 'Maria G.',
                'pickup_time': now + timedelta(hours=3),
                'estimated_items': 'About 15 items',
                'status': 'open'
            },
            # Another open delivery
            {
                'recipient': recipient_objects[2],
                'volunteer': None,
                'store_name': 'Walmart - Elk Grove',
                'pickup_address': '8465 Elk Grove Blvd, Elk Grove, CA 95758',
                'store_lat': 38.4085,
                'store_lng': -121.4015,
                'order_name': 'Ana L.',
                'pickup_time': now + timedelta(hours=5),
                'estimated_items': '2 bags',
                'status': 'open'
            },
            # Claimed delivery - in progress
            {
                'recipient': recipient_objects[1],
                'volunteer': volunteer_objects[0],  # Carlos
                'store_name': 'Target - South Sacramento',
                'pickup_address': '7500 Stockton Blvd, Sacramento, CA 95823',
                'store_lat': 38.4847,
                'store_lng': -121.4427,
                'order_name': 'José R.',
                'pickup_time': now + timedelta(hours=1),
                'estimated_items': '8-10 items',
                'status': 'claimed',
                'claimed_at': now - timedelta(hours=1)
            },
            # Completed delivery (yesterday)
            {
                'recipient': recipient_objects[0],
                'volunteer': volunteer_objects[1],  # Sarah
                'store_name': 'Costco - Sacramento',
                'pickup_address': '3360 El Camino Ave, Sacramento, CA 95821',
                'store_lat': 38.6173,
                'store_lng': -121.4089,
                'order_name': 'Maria G.',
                'pickup_time': now - timedelta(days=1, hours=2),
                'estimated_items': 'Large order - 25+ items',
                'status': 'completed',
                'claimed_at': now - timedelta(days=1, hours=4),
                'picked_up_at': now - timedelta(days=1, hours=3),
                'completed_at': now - timedelta(days=1, hours=1)
            },
            # Another completed delivery (last week)
            {
                'recipient': recipient_objects[1],
                'volunteer': volunteer_objects[0],  # Carlos
                'store_name': 'Raley\'s - Land Park',
                'pickup_address': '5150 Freeport Blvd, Sacramento, CA 95822',
                'store_lat': 38.5328,
                'store_lng': -121.4997,
                'order_name': 'José R.',
                'pickup_time': now - timedelta(days=7),
                'estimated_items': '12 items',
                'status': 'completed',
                'claimed_at': now - timedelta(days=7, hours=2),
                'picked_up_at': now - timedelta(days=7, hours=1),
                'completed_at': now - timedelta(days=7)
            }
        ]
        
        delivery_objects = []
        for d_data in deliveries_data:
            delivery = Delivery(
                recipient_id=d_data['recipient'].id,
                volunteer_id=d_data['volunteer'].id if d_data['volunteer'] else None,
                store_name=d_data['store_name'],
                pickup_address=d_data['pickup_address'],
                store_latitude=d_data['store_lat'],
                store_longitude=d_data['store_lng'],
                order_name=d_data['order_name'],
                pickup_time=d_data['pickup_time'],
                estimated_items=d_data['estimated_items'],
                status=d_data['status'],
                claimed_at=d_data.get('claimed_at'),
                picked_up_at=d_data.get('picked_up_at'),
                completed_at=d_data.get('completed_at')
            )
            db.session.add(delivery)
            db.session.flush()
            delivery_objects.append(delivery)
            print(f"  Created delivery: {d_data['store_name']} ({d_data['status']})")
        
        # ===========================================
        # RATINGS (for completed deliveries)
        # ===========================================
        # Rating for Costco delivery
        rating1 = Rating(
            delivery_id=delivery_objects[3].id,  # Costco delivery
            volunteer_id=volunteer_objects[1].id,  # Sarah
            recipient_id=recipient_objects[0].id,  # Maria
            score=5,
            comment='Very friendly and professional. Thank you so much!'
        )
        db.session.add(rating1)
        
        # Rating for Raley's delivery
        rating2 = Rating(
            delivery_id=delivery_objects[4].id,  # Raley's delivery
            volunteer_id=volunteer_objects[0].id,  # Carlos
            recipient_id=recipient_objects[1].id,  # José
            score=5,
            comment='Excellent service, arrived right on time.'
        )
        db.session.add(rating2)
        
        print("  Created ratings for completed deliveries")
        
        # ===========================================
        # COMMIT ALL
        # ===========================================
        db.session.commit()
        
        print("\n" + "=" * 50)
        print("DEMO DATA SEEDED SUCCESSFULLY")
        print("=" * 50)
        print("\nDemo Accounts (password for all: demo2025):")
        print("-" * 50)
        print(f"  Admin:     admin@demo.aquiestamos.org")
        print(f"  Volunteer: carlos.v@demo.aquiestamos.org (approved)")
        print(f"  Volunteer: sarah.v@demo.aquiestamos.org (approved)")
        print(f"  Volunteer: pending.v@demo.aquiestamos.org (pending)")
        print(f"  Recipient: maria.r@demo.aquiestamos.org")
        print(f"  Recipient: jose.r@demo.aquiestamos.org")
        print(f"  Recipient: ana.r@demo.aquiestamos.org")
        print("-" * 50)


if __name__ == '__main__':
    seed_demo_data()
