# CalorieMate Setup Guide

## Basic Setup for MySQL + Python

### 1. Install Required Packages

```bash
pip install flask flask-sqlalchemy pymysql python-dotenv
```

### 2. Create Basic Project Structure

```
calorie-mate/
├── app.py              # Main Flask application
├── requirements.txt    # Python dependencies
└── README.md          # This file
```

### 3. Basic Flask App with MySQL Connection

Create `app.py`:

```python
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import os

app = Flask(__name__)

# MySQL Database Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:password@localhost/caloriemate'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Basic User Model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)

@app.route('/')
def index():
    return 'CalorieMate is running!'

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
```

### 4. MySQL Database Setup

1. **Install MySQL Server**
2. **Create Database**:
   ```sql
   CREATE DATABASE caloriemate;
   ```
3. **Update connection string** in `app.py` with your MySQL credentials

### 5. Run the Application

```bash
python app.py
```

Visit `http://localhost:5000` to see your app running!

## Next Steps

- Add more models (Food, Exercise, etc.)
- Create routes for CRUD operations
- Add HTML templates
- Implement user authentication
- Add API endpoints

This gives you the foundation to build CalorieMate with MySQL backend using Python Flask.