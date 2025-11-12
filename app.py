"""
CalorieMate - Comprehensive Calorie and Recipe Tracking Application
A fullstack Flask application with barcode scanning, nutrition tracking, and recipe management.
"""

from flask import Flask
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Import extensions (removed SQLAlchemy - now using raw SQL)
from extensions import login_manager, csrf
from db_client import get_db_client, DatabaseClient

def create_app():
    """Application factory pattern for Flask app creation."""
    app = Flask(__name__)
    
    # Configuration
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-key-change-in-production')
    app.config['DATABASE_URL'] = os.getenv('DATABASE_URL', 'mysql+pymysql://admin:jY1tUaJq0ht32iEjVp5Q@calorie-mate.cv44iukwwhax.us-east-2.rds.amazonaws.com:3306/caloriemate')
    app.config['WTF_CSRF_TIME_LIMIT'] = 3600  # 1 hour
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB
    
    # Initialize extensions with app
    login_manager.init_app(app)
    csrf.init_app(app)
    
    # User loader function for raw SQL
    @login_manager.user_loader
    def load_user(user_id):
        from models import User
        return User.get(int(user_id))
    
    # Initialize database client
    with app.app_context():
        from db_client import init_db_client
        database_url = app.config.get('DATABASE_URL')
        init_db_client(database_url)
    
    # Register blueprints
    from routes.auth import auth_bp
    from routes.main import main_bp
    from routes.api import api_bp
    from routes.admin import admin_bp
    
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(main_bp)
    # Exempt API blueprint from CSRF (all routes require login)
    csrf.exempt(api_bp)
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    
    return app

def initialize_database():
    """Initialize database schema from schema.sql"""
    try:
        # Read schema file
        with open('schema.sql', 'r') as f:
            schema_sql = f.read()
        
        # Execute schema creation
        client = get_db_client()
        statements = [stmt.strip() for stmt in schema_sql.split(';') if stmt.strip()]
        
        failed_statements = []
        for statement in statements:
            if statement:
                success = client.execute_ddl(statement)
                if not success:
                    failed_statements.append(statement[:50] + "...")
        
        if failed_statements:
            print(f"⚠️  Some DDL statements failed: {len(failed_statements)}")
            for stmt in failed_statements[:3]:  # Show first 3 failures
                print(f"   - {stmt}")
        
        print("✅ Database schema initialized successfully!")
        return True
    except Exception as e:
        print(f"❌ Failed to initialize database schema: {e}")
        return False

if __name__ == '__main__':
    app = create_app()
    
    with app.app_context():
        if initialize_database():
            print("🚀 CalorieMate application starting...")
            app.run(debug=True, host='0.0.0.0', port=5000)
        else:
            print("❌ Failed to start application due to database initialization error")