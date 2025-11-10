#!/bin/bash
set -e

echo "🚀 Starting CalorieMate application..."

# Wait for database to be ready
echo "⏳ Waiting for database to be ready..."
while ! mysqladmin ping -h"$DB_HOST" -P"$DB_PORT" -u"$DB_USER" -p"$DB_PASSWORD" --silent; do
    echo "Database is not ready yet. Waiting 2 seconds..."
    sleep 2
done

echo "✅ Database is ready!"

# Check if we need to initialize the database
echo "🔍 Checking database initialization status..."

# Run a simple query to check if tables exist
if ! mysql -h"$DB_HOST" -P"$DB_PORT" -u"$DB_USER" -p"$DB_PASSWORD" -D"$DB_NAME" -e "SELECT 1 FROM users LIMIT 1;" 2>/dev/null; then
    echo "📋 Database tables not found. Running schema initialization..."
    
    # The schema.sql should already be loaded by MySQL init scripts
    # But let's verify and create tables if needed
    python3 -c "
from app import create_app, initialize_database
app = create_app()
with app.app_context():
    if initialize_database():
        print('✅ Database schema initialized successfully!')
    else:
        print('❌ Database schema initialization failed!')
        exit(1)
    "
else
    echo "✅ Database tables already exist."
fi

echo "🎯 Starting Flask application..."
exec python app.py