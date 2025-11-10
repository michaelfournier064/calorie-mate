"""
Flask extensions initialization.
This module contains the extension instances that need to be shared across the application.
"""

from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect

# Initialize extensions (removed SQLAlchemy - now using raw SQL)
login_manager = LoginManager()
csrf = CSRFProtect()

# Configure login manager
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'