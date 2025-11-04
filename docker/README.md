# CalorieMate Docker Setup

## 🐳 Docker Configuration for Raw SQL Implementation

This Docker setup has been updated to work with the CalorieMate application that uses raw SQL queries instead of SQLAlchemy ORM.

## 📋 Prerequisites

- Docker Desktop installed and running
- Docker Compose installed (included with Docker Desktop)

## 🚀 Quick Start

1. **Navigate to the project directory:**
   ```bash
   cd c:\Users\micha\source\repositories\school\calorie-mate
   ```

2. **Start the application:**
   ```bash
   docker-compose -f docker/docker-compose.yml up --build
   ```

3. **Access the application:**
   - **CalorieMate App**: http://localhost:5000
   - **phpMyAdmin**: http://localhost:8080

## 🛠️ Services

### MySQL Database (`db`)
- **Image**: mysql:8.0
- **Port**: 3306
- **Database**: caloriemate
- **User**: caloriemate_user
- **Password**: caloriemate_pass
- **Root Password**: caloriemate_root

### CalorieMate Application (`app`)
- **Port**: 5000
- **Environment**: Development
- **Database**: Raw SQL with PyMySQL
- **Health Check**: Enabled with 30s intervals

### phpMyAdmin (`phpmyadmin`)
- **Port**: 8080
- **Purpose**: Database management interface

## 🔧 Configuration

### Environment Variables (`.docker.env`)
```env
# Flask Configuration
FLASK_APP=app.py
FLASK_ENV=development
FLASK_DEBUG=1
SECRET_KEY=dev-key-change-in-production-docker

# Database Configuration
DB_HOST=db
DB_PORT=3306
DB_USER=caloriemate_user
DB_PASSWORD=caloriemate_pass
DB_NAME=caloriemate
```

### Database Schema
The database schema (`schema.sql`) is automatically loaded when the MySQL container starts for the first time.

## 📝 Available Commands

### Start Services
```bash
# Start in foreground
docker-compose -f docker/docker-compose.yml up

# Start in background
docker-compose -f docker/docker-compose.yml up -d

# Build and start
docker-compose -f docker/docker-compose.yml up --build
```

### Stop Services
```bash
# Stop services
docker-compose -f docker/docker-compose.yml down

# Stop and remove volumes (⚠️ This will delete database data)
docker-compose -f docker/docker-compose.yml down -v
```

### View Logs
```bash
# All services
docker-compose -f docker/docker-compose.yml logs

# Specific service
docker-compose -f docker/docker-compose.yml logs app
docker-compose -f docker/docker-compose.yml logs db
```

### Database Management
```bash
# Connect to MySQL container
docker-compose -f docker/docker-compose.yml exec db mysql -u caloriemate_user -p caloriemate

# Backup database
docker-compose -f docker/docker-compose.yml exec db mysqldump -u caloriemate_user -p caloriemate > backup.sql

# Restore database
docker-compose -f docker/docker-compose.yml exec -T db mysql -u caloriemate_user -p caloriemate < backup.sql
```

## 🔍 Troubleshooting

### Application Won't Start
1. Check if all containers are healthy:
   ```bash
   docker-compose -f docker/docker-compose.yml ps
   ```

2. View application logs:
   ```bash
   docker-compose -f docker/docker-compose.yml logs app
   ```

### Database Connection Issues
1. Verify database is running:
   ```bash
   docker-compose -f docker/docker-compose.yml logs db
   ```

2. Test database connectivity:
   ```bash
   docker-compose -f docker/docker-compose.yml exec app ping db
   ```

### Schema Issues
The startup script (`docker/startup.sh`) handles database initialization. If there are issues:

1. Check startup logs:
   ```bash
   docker-compose -f docker/docker-compose.yml logs app | grep -E "(schema|database|init)"
   ```

2. Manually run schema initialization:
   ```bash
   docker-compose -f docker/docker-compose.yml exec app python -c "from app import create_app, initialize_database; app = create_app(); app.app_context().push(); initialize_database()"
   ```

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   CalorieMate   │    │      MySQL       │    │   phpMyAdmin    │
│   Flask App     │◄──►│    Database      │◄──►│   Management    │
│   (Port 5000)   │    │   (Port 3306)    │    │   (Port 8080)   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## 🔒 Security Notes

- The current configuration is for **development only**
- Default passwords are used - change for production
- The `.docker.env` file contains development credentials
- For production, use Docker secrets or external secret management

## 🚀 Production Deployment

For production deployment, consider:

1. **Environment Variables**: Use production-safe credentials
2. **Volumes**: Use named volumes or bind mounts for data persistence
3. **Networks**: Configure proper Docker networks
4. **Security**: Remove phpMyAdmin, use HTTPS, implement proper authentication
5. **Monitoring**: Add logging and monitoring solutions
6. **Backups**: Implement automated database backup strategies

## 📚 Additional Resources

- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [MySQL Docker Image](https://hub.docker.com/_/mysql)
- [Flask Docker Best Practices](https://flask.palletsprojects.com/en/2.3.x/deploying/docker/)