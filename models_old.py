"""
Raw SQL models for CalorieMate application.
Replaces SQLAlchemy ORM with direct MySQL operations using PyMySQL.
"""

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
import logging

# Import raw SQL database client
from db_client import get_db_client

class UserRole(Enum):
    """User role enumeration."""
    USER = "user"
    MODERATOR = "moderator"
    ADMIN = "admin"

class ContentType(Enum):
    """Content type enumeration for reporting."""
    RECIPE = "recipe"
    REVIEW = "review"
    PRODUCT = "product"
    USER_PROFILE = "user_profile"

class SponsorshipType(Enum):
    """Sponsorship content type."""
    SPONSORED = "sponsored"
    INFLUENCER = "influencer"
    RECOMMENDED = "recommended"

class User(UserMixin):
    """Enhanced user model with raw SQL operations for authentication and profile features."""
    
    def __init__(self, **kwargs):
        """Initialize User instance from database row or kwargs."""
        self.id = kwargs.get('id')
        self.username = kwargs.get('username')
        self.email = kwargs.get('email')
        self.password_hash = kwargs.get('password_hash')
        self.first_name = kwargs.get('first_name')
        self.last_name = kwargs.get('last_name')
        self.role = kwargs.get('role', 'user')
        self.is_active = kwargs.get('is_active', True)
        self.email_verified = kwargs.get('email_verified', False)
        self.profile_picture_url = kwargs.get('profile_picture_url')
        self.bio = kwargs.get('bio')
        self.daily_calorie_goal = kwargs.get('daily_calorie_goal')
        self.dietary_restrictions = kwargs.get('dietary_restrictions')
        self.created_at = kwargs.get('created_at')
        self.updated_at = kwargs.get('updated_at')
        self.last_login = kwargs.get('last_login')
    
    @staticmethod
    def create(username: str, email: str, password: str, **kwargs) -> 'User':
        """Create a new user in the database."""
        db_client = get_db_client()
        
        # Check if username or email already exists
        if User.get_by_username(username):
            raise ValueError("Username already exists")
        if User.get_by_email(email):
            raise ValueError("Email already exists")
        
        user_data = {
            'username': username,
            'email': email.lower(),
            'password_hash': generate_password_hash(password),
            'first_name': kwargs.get('first_name'),
            'last_name': kwargs.get('last_name'),
            'role': kwargs.get('role', 'user'),
            'is_active': kwargs.get('is_active', True),
            'email_verified': kwargs.get('email_verified', False),
            'profile_picture_url': kwargs.get('profile_picture_url'),
            'bio': kwargs.get('bio'),
            'daily_calorie_goal': kwargs.get('daily_calorie_goal'),
            'dietary_restrictions': kwargs.get('dietary_restrictions')
        }
        
        user_id = db_client.insert_record('users', user_data)
        user_data['id'] = user_id
        return User(**user_data)
    
    @staticmethod
    def get(user_id: int) -> Optional['User']:
        """Get user by ID."""
        db_client = get_db_client()
        result = db_client.fetch_one("SELECT * FROM users WHERE id = %s", (user_id,))
        return User(**result) if result else None
    
    @staticmethod
    def get_by_username(username: str) -> Optional['User']:
        """Get user by username."""
        db_client = get_db_client()
        result = db_client.fetch_one("SELECT * FROM users WHERE username = %s", (username,))
        return User(**result) if result else None
    
    @staticmethod
    def get_by_email(email: str) -> Optional['User']:
        """Get user by email."""
        db_client = get_db_client()
        result = db_client.fetch_one("SELECT * FROM users WHERE email = %s", (email.lower(),))
        return User(**result) if result else None
    
    @staticmethod
    def get_by_username_or_email(username_or_email: str) -> Optional['User']:
        """Get user by username or email."""
        db_client = get_db_client()
        query = """
        SELECT * FROM users 
        WHERE username = %s OR email = %s
        """
        result = db_client.fetch_one(query, (username_or_email, username_or_email.lower()))
        return User(**result) if result else None
    
    @staticmethod
    def get_all(page: int = 1, per_page: int = 20, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Get paginated list of users with optional filters."""
        db_client = get_db_client()
        
        base_query = "SELECT * FROM users"
        params = ()
        
        if filters:
            where_clause, where_params = db_client.build_where_clause(filters)
            base_query += where_clause
            params = where_params
        
        base_query += " ORDER BY created_at DESC"
        
        result = db_client.fetch_paginated(base_query, params, page, per_page)
        result['items'] = [User(**row) for row in result['items']]
        return result
    
    def save(self) -> None:
        """Save user changes to database."""
        if not self.id:
            raise ValueError("Cannot save user without ID. Use User.create() for new users.")
        
        db_client = get_db_client()
        
        user_data = {
            'username': self.username,
            'email': self.email,
            'password_hash': self.password_hash,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'role': self.role,
            'is_active': self.is_active,
            'email_verified': self.email_verified,
            'profile_picture_url': self.profile_picture_url,
            'bio': self.bio,
            'daily_calorie_goal': self.daily_calorie_goal,
            'dietary_restrictions': self.dietary_restrictions,
            'last_login': self.last_login
        }
        
        db_client.update_record('users', user_data, {'id': self.id})
    
    def delete(self) -> None:
        """Delete user from database."""
        if not self.id:
            raise ValueError("Cannot delete user without ID")
        
        db_client = get_db_client()
        db_client.delete_record('users', {'id': self.id})
    
    def set_password(self, password: str) -> None:
        """Hash and set user password."""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password: str) -> bool:
        """Check if provided password matches hash."""
        return check_password_hash(self.password_hash, password)
    
    def is_admin(self) -> bool:
        """Check if user has admin privileges."""
        return self.role == 'admin'
    
    def is_moderator(self) -> bool:
        """Check if user has moderator or admin privileges."""
        return self.role in ['moderator', 'admin']
    
    def update_last_login(self) -> None:
        """Update last login timestamp."""
        db_client = get_db_client()
        self.last_login = datetime.utcnow()
        db_client.execute_update(
            "UPDATE users SET last_login = %s WHERE id = %s",
            (self.last_login, self.id)
        )
    
    def get_created_recipes(self, limit: int = None) -> List[Dict[str, Any]]:
        """Get recipes created by this user."""
        db_client = get_db_client()
        query = "SELECT * FROM recipes WHERE created_by_user_id = %s ORDER BY created_at DESC"
        
        if limit:
            query += f" LIMIT {limit}"
        
        return db_client.execute_query(query, (self.id,))
    
    def get_saved_recipes(self, limit: int = None) -> List[Dict[str, Any]]:
        """Get recipes saved by this user."""
        db_client = get_db_client()
        query = """
        SELECT r.*, usr.notes, usr.created_at as saved_at
        FROM recipes r
        JOIN user_saved_recipes usr ON r.id = usr.recipe_id
        WHERE usr.user_id = %s
        ORDER BY usr.created_at DESC
        """
        
        if limit:
            query += f" LIMIT {limit}"
        
        return db_client.execute_query(query, (self.id,))
    
    def get_product_history(self, limit: int = None) -> List[Dict[str, Any]]:
        """Get user's product scanning history."""
        db_client = get_db_client()
        query = """
        SELECT p.*, uph.action_type, uph.quantity_consumed, 
               uph.serving_size_consumed, uph.timestamp
        FROM products p
        JOIN user_product_history uph ON p.id = uph.product_id
        WHERE uph.user_id = %s
        ORDER BY uph.timestamp DESC
        """
        
        if limit:
            query += f" LIMIT {limit}"
        
        return db_client.execute_query(query, (self.id,))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert user to dictionary."""
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'role': self.role,
            'is_active': self.is_active,
            'email_verified': self.email_verified,
            'profile_picture_url': self.profile_picture_url,
            'bio': self.bio,
            'daily_calorie_goal': self.daily_calorie_goal,
            'dietary_restrictions': self.dietary_restrictions,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'last_login': self.last_login
        }
    
    def __repr__(self):
        return f'<User {self.username}>'

class Product(db.Model):
    """Product database for barcode scanning and nutrition lookup."""
    __tablename__ = 'products'
    
    id = db.Column(db.Integer, primary_key=True)
    barcode = db.Column(db.String(20), unique=True, nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    brand = db.Column(db.String(100), nullable=True)
    description = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(100), nullable=True)
    image_url = db.Column(db.String(255), nullable=True)
    
    # Product validation and verification
    is_verified = db.Column(db.Boolean, default=False, nullable=False)
    verified_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    verification_date = db.Column(db.DateTime, nullable=True)
    
    # Serving size information
    serving_size = db.Column(db.Float, nullable=True)  # in grams
    serving_size_unit = db.Column(db.String(20), default='g', nullable=False)
    servings_per_container = db.Column(db.Float, nullable=True)
    
    # Timestamps and tracking
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    # Relationships
    nutrition = db.relationship('ProductNutrition', backref='product', uselist=False, lazy=True)
    user_history = db.relationship('UserProductHistory', back_populates='product', lazy=True)
    
    def __repr__(self):
        return f'<Product {self.name} ({self.barcode})>'

class ProductNutrition(db.Model):
    """Comprehensive nutrition information for products."""
    __tablename__ = 'product_nutrition'
    
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, unique=True)
    
    # Basic macronutrients (per serving)
    calories = db.Column(db.Float, nullable=True)
    protein_g = db.Column(db.Float, nullable=True)
    carbohydrates_g = db.Column(db.Float, nullable=True)
    fiber_g = db.Column(db.Float, nullable=True)
    sugars_g = db.Column(db.Float, nullable=True)
    fat_total_g = db.Column(db.Float, nullable=True)
    fat_saturated_g = db.Column(db.Float, nullable=True)
    fat_trans_g = db.Column(db.Float, nullable=True)
    
    # Micronutrients
    sodium_mg = db.Column(db.Float, nullable=True)
    potassium_mg = db.Column(db.Float, nullable=True)
    cholesterol_mg = db.Column(db.Float, nullable=True)
    
    # Vitamins (% daily value)
    vitamin_a_percent = db.Column(db.Float, nullable=True)
    vitamin_c_percent = db.Column(db.Float, nullable=True)
    calcium_percent = db.Column(db.Float, nullable=True)
    iron_percent = db.Column(db.Float, nullable=True)
    
    # Additional nutrition data as JSON for flexibility
    additional_nutrients = db.Column(db.JSON, nullable=True)
    
    # Data validation and sources
    is_estimated = db.Column(db.Boolean, default=False, nullable=False)
    data_source = db.Column(db.String(100), nullable=True)  # FDA, user-input, etc.
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

class Recipe(db.Model):
    """Enhanced recipe model with nutrition tracking and community features."""
    __tablename__ = 'recipes'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    prep_time_minutes = db.Column(db.Integer, nullable=True)
    cook_time_minutes = db.Column(db.Integer, nullable=True)
    total_time_minutes = db.Column(db.Integer, nullable=True)
    servings = db.Column(db.Integer, nullable=False, default=1)
    difficulty_level = db.Column(db.String(20), nullable=True)  # Easy, Medium, Hard
    
    # Recipe categorization
    category = db.Column(db.String(100), nullable=True)
    cuisine_type = db.Column(db.String(100), nullable=True)
    dietary_tags = db.Column(db.JSON, nullable=True)  # vegetarian, vegan, gluten-free, etc.
    
    # Content and media
    image_url = db.Column(db.String(255), nullable=True)
    video_url = db.Column(db.String(255), nullable=True)
    
    # Community and moderation
    is_public = db.Column(db.Boolean, default=True, nullable=False)
    is_featured = db.Column(db.Boolean, default=False, nullable=False)
    is_approved = db.Column(db.Boolean, default=True, nullable=False)
    
    # Ownership and timestamps
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    ingredients = db.relationship('RecipeIngredient', back_populates='recipe', lazy=True, cascade='all, delete-orphan')
    instructions = db.relationship('RecipeInstruction', back_populates='recipe', lazy=True, cascade='all, delete-orphan')
    nutrition = db.relationship('RecipeNutrition', backref='recipe', uselist=False, lazy=True, cascade='all, delete-orphan')
    ratings = db.relationship('RecipeRating', back_populates='recipe', lazy=True)
    saved_by_users = db.relationship('UserSavedRecipe', back_populates='recipe', lazy=True)
    
    @property
    def average_rating(self):
        """Calculate average rating for the recipe."""
        if not self.ratings:
            return None
        return sum(rating.rating for rating in self.ratings) / len(self.ratings)
    
    @property
    def rating_count(self):
        """Get total number of ratings."""
        return len(self.ratings)
    
    def __repr__(self):
        return f'<Recipe {self.name}>'

class RecipeIngredient(db.Model):
    """Individual ingredients within a recipe with quantities."""
    __tablename__ = 'recipe_ingredients'
    
    id = db.Column(db.Integer, primary_key=True)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipes.id'), nullable=False)
    
    # Ingredient information
    ingredient_name = db.Column(db.String(200), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(50), nullable=False)
    preparation_note = db.Column(db.String(200), nullable=True)  # "chopped", "diced", etc.
    
    # Optional link to product database
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True)
    
    # Order for display
    order_index = db.Column(db.Integer, nullable=False, default=0)
    
    # Relationships
    recipe = db.relationship('Recipe', back_populates='ingredients')
    product = db.relationship('Product', backref='recipe_usages', lazy=True)

class RecipeInstruction(db.Model):
    """Step-by-step cooking instructions for recipes."""
    __tablename__ = 'recipe_instructions'
    
    id = db.Column(db.Integer, primary_key=True)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipes.id'), nullable=False)
    step_number = db.Column(db.Integer, nullable=False)
    instruction = db.Column(db.Text, nullable=False)
    time_minutes = db.Column(db.Integer, nullable=True)  # Time for this step
    temperature = db.Column(db.String(20), nullable=True)  # Cooking temperature
    
    # Relationships
    recipe = db.relationship('Recipe', back_populates='instructions')

class RecipeNutrition(db.Model):
    """Calculated nutrition information for complete recipes."""
    __tablename__ = 'recipe_nutrition'
    
    id = db.Column(db.Integer, primary_key=True)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipes.id'), nullable=False, unique=True)
    
    # Nutrition per serving
    calories_per_serving = db.Column(db.Float, nullable=True)
    protein_g = db.Column(db.Float, nullable=True)
    carbohydrates_g = db.Column(db.Float, nullable=True)
    fiber_g = db.Column(db.Float, nullable=True)
    sugars_g = db.Column(db.Float, nullable=True)
    fat_total_g = db.Column(db.Float, nullable=True)
    fat_saturated_g = db.Column(db.Float, nullable=True)
    sodium_mg = db.Column(db.Float, nullable=True)
    
    # Calculation metadata
    is_calculated = db.Column(db.Boolean, default=False, nullable=False)
    calculation_date = db.Column(db.DateTime, nullable=True)
    calculation_accuracy = db.Column(db.Float, nullable=True)  # Confidence score 0-1
    
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

class RecipeRating(db.Model):
    """User ratings and reviews for recipes."""
    __tablename__ = 'recipe_ratings'
    
    id = db.Column(db.Integer, primary_key=True)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipes.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    rating = db.Column(db.Integer, nullable=False)  # 1-5 stars
    review_text = db.Column(db.Text, nullable=True)
    would_make_again = db.Column(db.Boolean, nullable=True)
    
    # Moderation
    is_approved = db.Column(db.Boolean, default=True, nullable=False)
    flagged_count = db.Column(db.Integer, default=0, nullable=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    recipe = db.relationship('Recipe', back_populates='ratings')
    user = db.relationship('User', back_populates='recipe_ratings')
    
    # Unique constraint to prevent multiple ratings from same user
    __table_args__ = (db.UniqueConstraint('recipe_id', 'user_id', name='unique_user_recipe_rating'),)

class UserSavedRecipe(db.Model):
    """Users' saved/bookmarked recipes."""
    __tablename__ = 'user_saved_recipes'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipes.id'), nullable=False)
    notes = db.Column(db.Text, nullable=True)  # Personal notes about the recipe
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    user = db.relationship('User', back_populates='saved_recipes')
    recipe = db.relationship('Recipe', back_populates='saved_by_users')
    
    # Unique constraint
    __table_args__ = (db.UniqueConstraint('user_id', 'recipe_id', name='unique_user_saved_recipe'),)

class UserPersonalIngredient(db.Model):
    """Custom ingredients created by users for personal use."""
    __tablename__ = 'user_personal_ingredients'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Ingredient details
    name = db.Column(db.String(200), nullable=False)
    brand = db.Column(db.String(100), nullable=True)
    description = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(100), nullable=True)
    
    # Nutrition per 100g
    calories_per_100g = db.Column(db.Float, nullable=True)
    protein_per_100g = db.Column(db.Float, nullable=True)
    carbs_per_100g = db.Column(db.Float, nullable=True)
    fat_per_100g = db.Column(db.Float, nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user = db.relationship('User', back_populates='personal_ingredients')

class UserProductHistory(db.Model):
    """Track products that users have scanned or viewed."""
    __tablename__ = 'user_product_history'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    
    action_type = db.Column(db.String(50), nullable=False)  # 'scanned', 'viewed', 'added_to_meal'
    quantity_consumed = db.Column(db.Float, nullable=True)
    serving_size_consumed = db.Column(db.Float, nullable=True)
    
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    user = db.relationship('User', back_populates='product_history')
    product = db.relationship('Product', back_populates='user_history')

class AdminAction(db.Model):
    """Log administrative actions for audit purposes."""
    __tablename__ = 'admin_actions'
    
    id = db.Column(db.Integer, primary_key=True)
    admin_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    action_type = db.Column(db.String(100), nullable=False)  # 'user_suspended', 'content_removed', etc.
    target_type = db.Column(db.String(50), nullable=False)   # 'user', 'recipe', 'product', etc.
    target_id = db.Column(db.Integer, nullable=False)
    
    description = db.Column(db.Text, nullable=True)
    metadata_json = db.Column(db.JSON, nullable=True)  # Additional structured data
    
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    admin_user = db.relationship('User', backref='admin_actions', lazy=True)

class ReportedContent(db.Model):
    """User reports of inappropriate content or behavior."""
    __tablename__ = 'reported_content'
    
    id = db.Column(db.Integer, primary_key=True)
    reporter_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    content_type = db.Column(db.Enum(ContentType), nullable=False)
    content_id = db.Column(db.Integer, nullable=False)
    
    reason = db.Column(db.String(100), nullable=False)  # 'spam', 'inappropriate', 'copyright', etc.
    description = db.Column(db.Text, nullable=True)
    
    # Moderation status
    status = db.Column(db.String(50), default='pending', nullable=False)  # pending, reviewed, resolved
    reviewed_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    resolution_notes = db.Column(db.Text, nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    resolved_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    reporter = db.relationship('User', foreign_keys=[reporter_user_id], backref='submitted_reports', lazy=True)
    reviewer = db.relationship('User', foreign_keys=[reviewed_by_user_id], backref='reviewed_reports', lazy=True)

class SponsoredContent(db.Model):
    """Sponsored, influencer, and recommended recipe content."""
    __tablename__ = 'sponsored_content'
    
    id = db.Column(db.Integer, primary_key=True)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipes.id'), nullable=False)
    
    content_type = db.Column(db.Enum(SponsorshipType), nullable=False)
    sponsor_name = db.Column(db.String(200), nullable=True)
    sponsor_logo_url = db.Column(db.String(255), nullable=True)
    
    # Campaign details
    campaign_name = db.Column(db.String(200), nullable=True)
    priority_score = db.Column(db.Integer, default=1, nullable=False)  # Higher = more prominent
    
    # Display settings
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    start_date = db.Column(db.DateTime, nullable=True)
    end_date = db.Column(db.DateTime, nullable=True)
    
    # Analytics
    view_count = db.Column(db.Integer, default=0, nullable=False)
    click_count = db.Column(db.Integer, default=0, nullable=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    recipe = db.relationship('Recipe', backref='sponsored_content', lazy=True)