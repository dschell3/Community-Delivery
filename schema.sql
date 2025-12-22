-- Aquí Estamos Database Schema
-- Current design uses sqlite for simplicity; adapt as needed for other RDBMS.
-- Focus on security, data integrity, and auditability.

-- Designed for MySQL but easily portable.
-- MySQL 8.0+

-- ============================================
-- USERS & AUTHENTICATION
-- ============================================

CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('admin', 'volunteer', 'recipient') NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active TIMESTAMP NULL,
    
    INDEX idx_email (email),
    INDEX idx_role (role)
);

-- ============================================
-- RECIPIENTS
-- ============================================

CREATE TABLE recipients (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL UNIQUE,
    display_name VARCHAR(100) NOT NULL,  -- Can be alias/first name only
    address_encrypted TEXT NOT NULL,      -- Fernet-encrypted full address
    phone_encrypted VARCHAR(255) NULL,    -- Fernet-encrypted phone (optional)
    general_area VARCHAR(100) NULL,       -- Non-sensitive area for matching (e.g., "North Sacramento")
    notes TEXT NULL,                       -- Delivery instructions (gate codes, etc.) - encrypted
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NULL,            -- Soft delete for retention policy
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user (user_id),
    INDEX idx_deleted (deleted_at)
);

-- Tombstone table for deleted recipients (preserves audit relationships)
CREATE TABLE recipient_tombstones (
    id INT PRIMARY KEY,                   -- Original recipient ID
    volunteer_ids JSON NOT NULL,          -- Array of volunteer IDs who had access
    last_active_date DATE NOT NULL,
    deleted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- VOLUNTEERS
-- ============================================

CREATE TABLE volunteers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL UNIQUE,
    full_name VARCHAR(255) NOT NULL,
    photo_path VARCHAR(500) NULL,         -- Path to profile photo
    service_area VARCHAR(255) NOT NULL,   -- Areas they're willing to serve
    availability_notes TEXT NULL,         -- Free text: "Weekends, evenings after 6pm"
    
    -- Vetting fields
    status ENUM('pending', 'approved', 'suspended', 'rejected') DEFAULT 'pending',
    attestation_completed BOOLEAN DEFAULT FALSE,  -- Confirmed not law enforcement
    attestation_timestamp TIMESTAMP NULL,
    reviewed_by INT NULL,                 -- Admin who reviewed
    reviewed_at TIMESTAMP NULL,
    rejection_reason TEXT NULL,
    suspension_reason TEXT NULL,
    
    -- Stats
    total_deliveries INT DEFAULT 0,
    average_rating DECIMAL(3,2) NULL,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (reviewed_by) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_user (user_id),
    INDEX idx_status (status),
    INDEX idx_service_area (service_area)
);

-- Temporary storage for ID verification photos (cleaned up after review)
CREATE TABLE volunteer_id_uploads (
    id INT AUTO_INCREMENT PRIMARY KEY,
    volunteer_id INT NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,        -- Auto-cleanup deadline
    
    FOREIGN KEY (volunteer_id) REFERENCES volunteers(id) ON DELETE CASCADE,
    INDEX idx_volunteer (volunteer_id),
    INDEX idx_expires (expires_at)
);

-- ============================================
-- DELIVERIES
-- ============================================

CREATE TABLE deliveries (
    id INT AUTO_INCREMENT PRIMARY KEY,
    recipient_id INT NOT NULL,
    volunteer_id INT NULL,                -- NULL when open/unclaimed
    
    -- Pickup details
    store_name VARCHAR(255) NOT NULL,
    pickup_address VARCHAR(500) NOT NULL, -- Store address (not sensitive)
    order_name VARCHAR(255) NOT NULL,     -- Name the order is under
    pickup_time DATETIME NOT NULL,        -- When order will be ready
    estimated_items VARCHAR(100) NULL,    -- "About 10 items", "2 bags", etc.
    
    -- Status tracking
    status ENUM('open', 'claimed', 'picked_up', 'completed', 'canceled') DEFAULT 'open',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    claimed_at TIMESTAMP NULL,
    picked_up_at TIMESTAMP NULL,          -- Volunteer confirmed pickup
    completed_at TIMESTAMP NULL,
    canceled_at TIMESTAMP NULL,
    canceled_by ENUM('recipient', 'volunteer', 'admin', 'system') NULL,
    cancellation_reason TEXT NULL,
    
    -- Priority for re-queued deliveries
    priority INT DEFAULT 0,               -- Higher = shows first (used when returned to pool)
    
    FOREIGN KEY (recipient_id) REFERENCES recipients(id) ON DELETE CASCADE,
    FOREIGN KEY (volunteer_id) REFERENCES volunteers(id) ON DELETE SET NULL,
    INDEX idx_recipient (recipient_id),
    INDEX idx_volunteer (volunteer_id),
    INDEX idx_status (status),
    INDEX idx_pickup_time (pickup_time),
    INDEX idx_status_priority (status, priority DESC, created_at ASC)
);

-- ============================================
-- MESSAGING
-- ============================================

CREATE TABLE messages (
    id INT AUTO_INCREMENT PRIMARY KEY,
    delivery_id INT NOT NULL,
    sender_id INT NOT NULL,               -- User ID of sender
    content TEXT NOT NULL,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    read_at TIMESTAMP NULL,
    
    FOREIGN KEY (delivery_id) REFERENCES deliveries(id) ON DELETE CASCADE,
    FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_delivery (delivery_id),
    INDEX idx_delivery_sent (delivery_id, sent_at),
    INDEX idx_sender (sender_id)
);

-- ============================================
-- RATINGS
-- ============================================

CREATE TABLE ratings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    delivery_id INT NOT NULL UNIQUE,      -- One rating per delivery
    volunteer_id INT NOT NULL,
    recipient_id INT NOT NULL,
    score TINYINT NOT NULL,               -- 1-5 stars
    comment TEXT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (delivery_id) REFERENCES deliveries(id) ON DELETE CASCADE,
    FOREIGN KEY (volunteer_id) REFERENCES volunteers(id) ON DELETE CASCADE,
    FOREIGN KEY (recipient_id) REFERENCES recipients(id) ON DELETE CASCADE,
    INDEX idx_volunteer (volunteer_id),
    INDEX idx_recipient (recipient_id),
    
    CONSTRAINT chk_score CHECK (score >= 1 AND score <= 5)
);

-- ============================================
-- AUDIT LOG
-- ============================================

-- Tracks relationships and actions, NOT sensitive data
CREATE TABLE audit_log (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    volunteer_id INT NULL,
    recipient_id INT NULL,
    delivery_id INT NULL,
    admin_id INT NULL,                    -- For admin actions
    action VARCHAR(100) NOT NULL,
    details JSON NULL,                    -- Non-sensitive metadata
    ip_address VARCHAR(45) NULL,          -- IPv4 or IPv6
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_volunteer (volunteer_id),
    INDEX idx_recipient (recipient_id),
    INDEX idx_delivery (delivery_id),
    INDEX idx_action (action),
    INDEX idx_timestamp (timestamp),
    INDEX idx_volunteer_timestamp (volunteer_id, timestamp)
);

-- Possible action values:
-- 'volunteer_registered', 'volunteer_approved', 'volunteer_rejected', 'volunteer_suspended'
-- 'delivery_created', 'delivery_claimed', 'delivery_canceled', 'delivery_picked_up', 'delivery_completed'
-- 'message_sent', 'address_accessed', 'rating_submitted'
-- 'recipient_registered', 'recipient_deleted', 'recipient_data_purged'
-- 'admin_login', 'admin_viewed_recipient'

-- ============================================
-- CONFIGURATION (per-instance settings)
-- ============================================

CREATE TABLE config (
    key_name VARCHAR(100) PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Default configuration
INSERT INTO config (key_name, value) VALUES
    ('max_active_claims_per_volunteer', '2'),
    ('id_upload_expiry_hours', '72'),
    ('inactive_account_purge_months', '18'),
    ('message_poll_interval_seconds', '10'),
    ('org_name', 'Aquí Estamos'),
    ('org_contact_email', 'admin@example.com');

-- ============================================
-- VIEWS (for common queries)
-- ============================================

-- Available deliveries for volunteers
CREATE VIEW available_deliveries AS
SELECT 
    d.id,
    d.store_name,
    d.pickup_address,
    d.pickup_time,
    d.estimated_items,
    d.priority,
    d.created_at,
    r.display_name AS recipient_name,
    r.general_area
FROM deliveries d
JOIN recipients r ON d.recipient_id = r.id
WHERE d.status = 'open'
ORDER BY d.priority DESC, d.created_at ASC;

-- Volunteer dashboard stats
CREATE VIEW volunteer_stats AS
SELECT 
    v.id AS volunteer_id,
    v.full_name,
    v.status,
    v.total_deliveries,
    v.average_rating,
    COUNT(CASE WHEN d.status = 'claimed' THEN 1 END) AS active_claims,
    COUNT(CASE WHEN d.status = 'picked_up' THEN 1 END) AS in_progress
FROM volunteers v
LEFT JOIN deliveries d ON v.id = d.volunteer_id AND d.status IN ('claimed', 'picked_up')
GROUP BY v.id;

-- ============================================
-- TRIGGERS
-- ============================================

-- Update volunteer stats after delivery completion
DELIMITER //

CREATE TRIGGER after_delivery_complete
AFTER UPDATE ON deliveries
FOR EACH ROW
BEGIN
    IF NEW.status = 'completed' AND OLD.status != 'completed' THEN
        UPDATE volunteers 
        SET total_deliveries = total_deliveries + 1
        WHERE id = NEW.volunteer_id;
    END IF;
END//

-- Update volunteer average rating after new rating
CREATE TRIGGER after_rating_insert
AFTER INSERT ON ratings
FOR EACH ROW
BEGIN
    UPDATE volunteers 
    SET average_rating = (
        SELECT AVG(score) 
        FROM ratings 
        WHERE volunteer_id = NEW.volunteer_id
    )
    WHERE id = NEW.volunteer_id;
END//

DELIMITER ;

-- ============================================
-- CLEANUP PROCEDURES
-- ============================================

DELIMITER //

-- Procedure to clean up expired ID uploads
CREATE PROCEDURE cleanup_expired_uploads()
BEGIN
    -- Delete physical files would need to happen in application code
    -- This just cleans up the database records
    DELETE FROM volunteer_id_uploads 
    WHERE expires_at < NOW();
END//

-- Procedure to purge inactive accounts
CREATE PROCEDURE purge_inactive_accounts(IN months_inactive INT)
BEGIN
    DECLARE cutoff_date TIMESTAMP;
    SET cutoff_date = DATE_SUB(NOW(), INTERVAL months_inactive MONTH);
    
    -- Create tombstones for recipients to be purged
    INSERT INTO recipient_tombstones (id, volunteer_ids, last_active_date)
    SELECT 
        r.id,
        COALESCE(
            (SELECT JSON_ARRAYAGG(DISTINCT d.volunteer_id) 
             FROM deliveries d 
             WHERE d.recipient_id = r.id AND d.volunteer_id IS NOT NULL),
            '[]'
        ),
        DATE(COALESCE(u.last_active, r.created_at))
    FROM recipients r
    JOIN users u ON r.user_id = u.id
    WHERE u.last_active < cutoff_date
      AND r.deleted_at IS NULL;
    
    -- Soft delete the recipients
    UPDATE recipients r
    JOIN users u ON r.user_id = u.id
    SET r.deleted_at = NOW(),
        r.address_encrypted = '[PURGED]',
        r.phone_encrypted = NULL,
        r.notes = NULL
    WHERE u.last_active < cutoff_date
      AND r.deleted_at IS NULL;
END//

DELIMITER ;
