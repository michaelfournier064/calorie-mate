from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import os

app = Flask(__name__)

# MySQL Database Configuration (XAMPP)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:@localhost:3306/caloriemate'
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
    try:
        with app.app_context():
            db.create_all()
            print("Database tables created successfully!")
            print("CalorieMate setup is complete!")
    except Exception as e:
        print(f"Error: {e}")
        print("MySQL might not be running or configured properly")
    
    app.run(debug=True)
