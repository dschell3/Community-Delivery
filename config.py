import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Base configuration."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-me')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Encryption
    ENCRYPTION_KEY = os.environ.get('ENCRYPTION_KEY')
    
    # File uploads
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'uploads')
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
    
    # ID upload expiry
    ID_UPLOAD_EXPIRY_HOURS = int(os.environ.get('ID_UPLOAD_EXPIRY_HOURS', 72))
    
    # Session
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'True').lower() == 'true'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Application settings (can be overridden by database config table)
    MAX_ACTIVE_CLAIMS_PER_VOLUNTEER = 2
    MESSAGE_POLL_INTERVAL_SECONDS = 10
    INACTIVE_ACCOUNT_PURGE_MONTHS = 18


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL', 
        'mysql+pymysql://root:password@localhost:3306/community_delivery_dev'
    )
    SESSION_COOKIE_SECURE = False  # Allow HTTP in development


class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    SESSION_COOKIE_SECURE = False


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    
    @classmethod
    def init_app(cls, app):
        # Log to stderr in production
        import logging
        from logging import StreamHandler
        handler = StreamHandler()
        handler.setLevel(logging.INFO)
        app.logger.addHandler(handler)


config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
