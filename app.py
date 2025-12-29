import os
import click
from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_migrate import Migrate

from config import config

# Initialize extensions (without app)
db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()
migrate = Migrate()

# Configure login manager
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'


def create_app(config_name=None):
    """Application factory."""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'default')
    
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    # Initialize extensions with app
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    migrate.init_app(app, db)
    
    # Ensure upload directories exist
    upload_folder = app.config['UPLOAD_FOLDER']
    os.makedirs(os.path.join(upload_folder, 'id_photos'), exist_ok=True)
    os.makedirs(os.path.join(upload_folder, 'volunteer_photos'), exist_ok=True)
    
    # Register blueprints
    from blueprints.auth import bp as auth_bp
    from blueprints.recipient import bp as recipient_bp
    from blueprints.volunteer import bp as volunteer_bp
    from blueprints.admin import bp as admin_bp
    from blueprints.api import bp as api_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(recipient_bp, url_prefix='/recipient')
    app.register_blueprint(volunteer_bp, url_prefix='/volunteer')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(api_bp, url_prefix='/api')
    
    # Register error handlers
    register_error_handlers(app)
    
    # Register CLI commands
    register_cli_commands(app)
    
    # Landing page route
    @app.route('/')
    def index():
        return render_template('landing.html')
    
    # User loader for Flask-Login
    @login_manager.user_loader
    def load_user(user_id):
        from models.user import User
        return User.query.get(int(user_id))
    
    return app


def register_error_handlers(app):
    """Register error handlers."""
    
    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/403.html'), 403
    
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template('errors/500.html'), 500


def register_cli_commands(app):
    """Register CLI commands."""
    
    @app.cli.command('create-admin')
    @click.option('--email', prompt=True, help='Admin email address')
    @click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True, help='Admin password')
    def create_admin(email, password):
        """Create an admin user."""
        from models.user import User
        from werkzeug.security import generate_password_hash
        
        # Check if user already exists
        existing = User.query.filter_by(email=email).first()
        if existing:
            click.echo(f'Error: User with email {email} already exists.')
            return
        
        user = User(
            email=email,
            password_hash=generate_password_hash(password),
            role='admin',
            is_active=True
        )
        db.session.add(user)
        db.session.commit()
        click.echo(f'Admin user created: {email}')
    
    @app.cli.command('cleanup-uploads')
    def cleanup_uploads():
        """Remove expired ID upload files."""
        from services.cleanup_service import cleanup_expired_uploads
        count = cleanup_expired_uploads()
        click.echo(f'Cleaned up {count} expired uploads.')
    
    @app.cli.command('purge-inactive')
    @click.option('--months', default=18, help='Months of inactivity before purge')
    def purge_inactive(months):
        """Purge inactive recipient accounts."""
        from services.cleanup_service import purge_inactive_accounts
        count = purge_inactive_accounts(months)
        click.echo(f'Purged {count} inactive accounts.')


# Create app instance for running directly
app = create_app()

if __name__ == '__main__':
    app.run(debug=True)
