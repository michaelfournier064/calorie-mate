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
    app.config['DATABASE_URI'] = os.getenv('DATABASE_URI', 'mysql+pymysql://root:@localhost:3306/caloriemate')
    app.config['WTF_CSRF_TIME_LIMIT'] = 3600  # 1 hour
    app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_CONTENT_LENGTH', 16777216))  # 16MB
    
    # Database configuration for raw SQL
    app.config['DATABASE_CONFIG'] = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': int(os.getenv('DB_PORT', 3306)),
        'user': os.getenv('DB_USER', 'root'),
        'password': os.getenv('DB_PASSWORD', ''),
        'database': os.getenv('DB_NAME', 'caloriemate'),
        'charset': 'utf8mb4'
    }
    
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
        database_uri = app.config.get('DATABASE_URI') or os.getenv('DATABASE_URI')
        init_db_client(database_uri)
    
    # Register blueprints
    from routes.auth import auth_bp
    from routes.main import main_bp
    from routes.api import api_bp
    from routes.admin import admin_bp
    
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(main_bp)
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