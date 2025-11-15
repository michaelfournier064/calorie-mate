"""
Raw SQL models for CalorieMate application.
Replaces SQLAlchemy ORM with direct MySQL operations using PyMySQL.
"""

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any, Union
import logging
import json

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
        self._is_active = kwargs.get('is_active', True)  # Use private attribute
        self.email_verified = kwargs.get('email_verified', False)
        self.profile_picture_url = kwargs.get('profile_picture_url')
        self.bio = kwargs.get('bio')
        self.daily_calorie_goal = kwargs.get('daily_calorie_goal')
        self.dietary_restrictions = kwargs.get('dietary_restrictions')
        self.created_at = kwargs.get('created_at')
        self.updated_at = kwargs.get('updated_at')
        self.last_login = kwargs.get('last_login')
    
    @property
    def is_active(self):
        """Override UserMixin's is_active property."""
        return self._is_active
    
    @is_active.setter
    def is_active(self, value):
        """Setter for is_active property."""
        self._is_active = bool(value)
    
    @staticmethod
    def create(username: str, email: str, password: str, **kwargs) -> 'User':
        """Create a new user in the database."""
        db_client = get_db_client()
        
        # Check if username or email already exists
        if User.get_by_username(username):
            raise ValueError("Username already exists")
        if User.get_by_email(email):
            raise ValueError("Email already exists")
        
        # Insert user with direct SQL
        query = """
            INSERT INTO users 
            (username, email, password_hash, first_name, last_name, role, is_active, 
             email_verified, profile_picture_url, bio, daily_calorie_goal, dietary_restrictions, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """
        
        user_id = db_client.execute_insert(query, (
            username,
            email.lower(),
            generate_password_hash(password),
            kwargs.get('first_name'),
            kwargs.get('last_name'),
            kwargs.get('role', 'user'),
            kwargs.get('is_active', True),
            kwargs.get('email_verified', False),
            kwargs.get('profile_picture_url'),
            kwargs.get('bio'),
            kwargs.get('daily_calorie_goal'),
            kwargs.get('dietary_restrictions')
        ))
        
        # Create user data for return
        user_data = {
            'id': user_id,
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
    def count() -> int:
        """Get total user count."""
        db_client = get_db_client()
        result = db_client.fetch_one("SELECT COUNT(*) as count FROM users")
        return result['count'] if result else 0
    
    @staticmethod
    def get_all(page: int = 1, per_page: int = 20, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Get paginated list of users with optional filters."""
        db_client = get_db_client()
        
        base_query = "SELECT * FROM users"
        params = ()
        
        if filters:
            # Build WHERE clause manually for direct SQL
            where_parts = []
            filter_params = []
            for key, value in filters.items():
                if value is None:
                    where_parts.append(f"{key} IS NULL")
                elif isinstance(value, (list, tuple)):
                    placeholders = ', '.join(['%s'] * len(value))
                    where_parts.append(f"{key} IN ({placeholders})")
                    filter_params.extend(value)
                elif isinstance(value, bool):
                    where_parts.append(f"{key} = %s")
                    filter_params.append(1 if value else 0)
                else:
                    where_parts.append(f"{key} = %s")
                    filter_params.append(value)
            
            if where_parts:
                base_query += " WHERE " + " AND ".join(where_parts)
                params = tuple(filter_params)
        
        base_query += " ORDER BY created_at DESC"
        
        result = db_client.fetch_paginated(base_query, params, page, per_page)
        result['items'] = [User(**row) for row in result['items']]
        return result
    
    def save(self) -> None:
        """Save user changes to database."""
        if not self.id:
            raise ValueError("Cannot save user without ID. Use User.create() for new users.")
        
        db_client = get_db_client()
        
        query = """
            UPDATE users SET 
                username = %s, email = %s, password_hash = %s, first_name = %s, last_name = %s,
                role = %s, is_active = %s, email_verified = %s, profile_picture_url = %s, 
                bio = %s, daily_calorie_goal = %s, dietary_restrictions = %s, last_login = %s,
                updated_at = NOW()
            WHERE id = %s
        """
        
        db_client.execute_update(query, (
            self.username, self.email, self.password_hash, self.first_name, self.last_name,
            self.role, self.is_active, self.email_verified, self.profile_picture_url,
            self.bio, self.daily_calorie_goal, self.dietary_restrictions, self.last_login,
            self.id
        ))
    
    def delete(self) -> None:
        """Delete user from database."""
        if not self.id:
            raise ValueError("Cannot delete user without ID")
        
        db_client = get_db_client()
        db_client.execute_delete("DELETE FROM users WHERE id = %s", (self.id,))
    
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
    
    @property
    def personal_ingredients(self) -> List[Dict[str, Any]]:
        """Get user's personal ingredients."""
        db_client = get_db_client()
        query = """
        SELECT * FROM user_personal_ingredients 
        WHERE user_id = %s 
        ORDER BY name ASC
        """
        return db_client.execute_query(query, (self.id,))
    
    def __repr__(self):
        return f'<User {self.username}>'


class ProductNutrition:
    """Product nutrition data model for storing nutritional information."""
    
    def __init__(self, id=None, product_id=None, calories=None, protein_g=None,
                 carbohydrates_g=None, fiber_g=None, sugars_g=None, fat_total_g=None,
                 fat_saturated_g=None, sodium_mg=None, created_at=None, updated_at=None):
        self.id = id
        self.product_id = product_id
        self.calories = calories
        self.protein_g = protein_g
        self.carbohydrates_g = carbohydrates_g
        self.fiber_g = fiber_g
        self.sugars_g = sugars_g
        self.fat_total_g = fat_total_g
        self.fat_saturated_g = fat_saturated_g
        self.sodium_mg = sodium_mg
        self.created_at = created_at
        self.updated_at = updated_at
    
    @staticmethod
    def create(product_id, calories=None, protein_g=None, carbohydrates_g=None,
               fiber_g=None, sugars_g=None, fat_total_g=None, fat_saturated_g=None,
               fat_trans_g=None, sodium_mg=None, cholesterol_mg=None, potassium_mg=None,
               vitamin_a_percent=None, vitamin_c_percent=None, calcium_percent=None,
               iron_percent=None):
        """Create new product nutrition record."""
        client = get_db_client()
        
        query = """
            INSERT INTO product_nutrition 
            (product_id, calories, protein_g, carbohydrates_g, fiber_g, sugars_g,
             fat_total_g, fat_saturated_g, fat_trans_g, sodium_mg, cholesterol_mg,
             potassium_mg, vitamin_a_percent, vitamin_c_percent, calcium_percent,
             iron_percent, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """
        
        nutrition_id = client.execute_insert(query, (
            product_id, calories, protein_g, carbohydrates_g, fiber_g, sugars_g,
            fat_total_g, fat_saturated_g, fat_trans_g, sodium_mg, cholesterol_mg,
            potassium_mg, vitamin_a_percent, vitamin_c_percent, calcium_percent,
            iron_percent
        ))
        if nutrition_id:
            return ProductNutrition.get_by_product_id(product_id)
        return None
    
    @staticmethod
    def get_by_product_id(product_id):
        """Get nutrition data for a specific product."""
        client = get_db_client()
        
        query = "SELECT * FROM product_nutrition WHERE product_id = %s"
        result = client.execute_query(query, (product_id,))
        
        if result and len(result) > 0:
            row = result[0]
            return ProductNutrition(
                id=row[0], product_id=row[1], calories=row[2], protein_g=row[3],
                carbohydrates_g=row[4], fiber_g=row[5], sugars_g=row[6],
                fat_total_g=row[7], fat_saturated_g=row[8], sodium_mg=row[9],
                created_at=row[10], updated_at=row[11]
            )
        return None
    
    def save(self):
        """Update existing nutrition record."""
        if not self.id:
            return False
        
        client = get_db_client()
        
        query = """
            UPDATE product_nutrition SET
                calories = %s, protein_g = %s, carbohydrates_g = %s, fiber_g = %s,
                sugars_g = %s, fat_total_g = %s, fat_saturated_g = %s, sodium_mg = %s,
                updated_at = NOW()
            WHERE id = %s
        """
        
        return client.execute_query(query, (
            self.calories, self.protein_g, self.carbohydrates_g, self.fiber_g,
            self.sugars_g, self.fat_total_g, self.fat_saturated_g, self.sodium_mg,
            self.id
        ))


class Product:
    """Product model for barcode scanning and nutrition lookup."""
    
    def __init__(self, **kwargs):
        """Initialize Product instance from database row or kwargs."""
        self.id = kwargs.get('id')
        self.barcode = kwargs.get('barcode')
        self.name = kwargs.get('name')
        self.brand = kwargs.get('brand')
        self.description = kwargs.get('description')
        self.category = kwargs.get('category')
        self.image_url = kwargs.get('image_url')
        self.is_verified = kwargs.get('is_verified', False)
        self.verified_by_user_id = kwargs.get('verified_by_user_id')
        self.verification_date = kwargs.get('verification_date')
        self.serving_size = kwargs.get('serving_size')
        self.serving_size_unit = kwargs.get('serving_size_unit', 'g')
        self.servings_per_container = kwargs.get('servings_per_container')
        self.created_at = kwargs.get('created_at')
        self.updated_at = kwargs.get('updated_at')
        self.created_by_user_id = kwargs.get('created_by_user_id')
        
        # Cache for nutrition data
        self._nutrition = None
    
    @staticmethod
    def create(barcode: str, name: str, **kwargs) -> 'Product':
        """Create a new product in the database."""
        db_client = get_db_client()
        
        # Check if barcode already exists
        if Product.get_by_barcode(barcode):
            raise ValueError("Product with this barcode already exists")
        
        query = """
            INSERT INTO products 
            (barcode, name, brand, description, category, image_url, is_verified, 
             verified_by_user_id, serving_size, serving_size_unit, servings_per_container, 
             created_by_user_id, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """
        
        product_id = db_client.execute_insert(query, (
            barcode, name, kwargs.get('brand'), kwargs.get('description'),
            kwargs.get('category'), kwargs.get('image_url'), kwargs.get('is_verified', False),
            kwargs.get('verified_by_user_id'), kwargs.get('serving_size'),
            kwargs.get('serving_size_unit', 'g'), kwargs.get('servings_per_container'),
            kwargs.get('created_by_user_id')
        ))
        
        # Create product data for return
        product_data = {
            'id': product_id,
            'barcode': barcode,
            'name': name,
            'brand': kwargs.get('brand'),
            'description': kwargs.get('description'),
            'category': kwargs.get('category'),
            'image_url': kwargs.get('image_url'),
            'is_verified': kwargs.get('is_verified', False),
            'verified_by_user_id': kwargs.get('verified_by_user_id'),
            'serving_size': kwargs.get('serving_size'),
            'serving_size_unit': kwargs.get('serving_size_unit', 'g'),
            'servings_per_container': kwargs.get('servings_per_container'),
            'created_by_user_id': kwargs.get('created_by_user_id')
        }
        return Product(**product_data)
    
    @staticmethod
    def get(product_id: int) -> Optional['Product']:
        """Get product by ID."""
        db_client = get_db_client()
        result = db_client.fetch_one("SELECT * FROM products WHERE id = %s", (product_id,))
        return Product(**result) if result else None
    
    @staticmethod
    def get_by_barcode(barcode: str) -> Optional['Product']:
        """Get product by barcode."""
        db_client = get_db_client()
        result = db_client.fetch_one("SELECT * FROM products WHERE barcode = %s", (barcode,))
        return Product(**result) if result else None
    
    @staticmethod
    def count() -> int:
        """Get total product count."""
        db_client = get_db_client()
        result = db_client.fetch_one("SELECT COUNT(*) as count FROM products")
        return result['count'] if result else 0
    
    @staticmethod
    def search(query: str, limit: int = 20) -> List['Product']:
        """Search products by name or brand."""
        db_client = get_db_client()
        search_query = """
        SELECT * FROM products 
        WHERE name LIKE %s OR brand LIKE %s 
        ORDER BY is_verified DESC, name ASC
        LIMIT %s
        """
        search_term = f"%{query}%"
        results = db_client.execute_query(search_query, (search_term, search_term, limit))
        return [Product(**row) for row in results]
    
    def get_nutrition(self) -> Optional[Dict[str, Any]]:
        """Get nutrition information for this product."""
        if self._nutrition is None and self.id:
            db_client = get_db_client()
            result = db_client.fetch_one("SELECT * FROM product_nutrition WHERE product_id = %s", (self.id,))
            self._nutrition = result
        return self._nutrition
    
    def set_nutrition(self, nutrition_data: Dict[str, Any]) -> None:
        """Set nutrition information for this product."""
        if not self.id:
            raise ValueError("Cannot set nutrition for product without ID")
        
        db_client = get_db_client()
        
        # Check if nutrition record exists
        existing = db_client.fetch_one("SELECT id FROM product_nutrition WHERE product_id = %s", (self.id,))
        
        nutrition_data['product_id'] = self.id
        
        if existing:
            # Update existing nutrition
            query = """
                UPDATE product_nutrition SET 
                    calories = %s, protein_g = %s, carbohydrates_g = %s, fiber_g = %s,
                    sugars_g = %s, fat_total_g = %s, fat_saturated_g = %s, sodium_mg = %s,
                    updated_at = NOW()
                WHERE product_id = %s
            """
            db_client.execute_update(query, (
                nutrition_data.get('calories'), nutrition_data.get('protein_g'),
                nutrition_data.get('carbohydrates_g'), nutrition_data.get('fiber_g'),
                nutrition_data.get('sugars_g'), nutrition_data.get('fat_total_g'),
                nutrition_data.get('fat_saturated_g'), nutrition_data.get('sodium_mg'),
                self.id
            ))
        else:
            # Create new nutrition record
            query = """
                INSERT INTO product_nutrition 
                (product_id, calories, protein_g, carbohydrates_g, fiber_g, sugars_g,
                 fat_total_g, fat_saturated_g, sodium_mg, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            """
            db_client.execute_insert(query, (
                self.id, nutrition_data.get('calories'), nutrition_data.get('protein_g'),
                nutrition_data.get('carbohydrates_g'), nutrition_data.get('fiber_g'),
                nutrition_data.get('sugars_g'), nutrition_data.get('fat_total_g'),
                nutrition_data.get('fat_saturated_g'), nutrition_data.get('sodium_mg')
            ))
        
        # Clear cache
        self._nutrition = None
    
    def save(self) -> None:
        """Save product changes to database."""
        if not self.id:
            raise ValueError("Cannot save product without ID. Use Product.create() for new products.")
        
        db_client = get_db_client()
        
        query = """
            UPDATE products SET 
                barcode = %s, name = %s, brand = %s, description = %s, category = %s,
                image_url = %s, is_verified = %s, verified_by_user_id = %s, 
                verification_date = %s, serving_size = %s, serving_size_unit = %s,
                servings_per_container = %s, created_by_user_id = %s, updated_at = NOW()
            WHERE id = %s
        """
        
        db_client.execute_update(query, (
            self.barcode, self.name, self.brand, self.description, self.category,
            self.image_url, self.is_verified, self.verified_by_user_id,
            self.verification_date, self.serving_size, self.serving_size_unit,
            self.servings_per_container, self.created_by_user_id, self.id
        ))
    
    def __repr__(self):
        return f'<Product {self.name} ({self.barcode})>'


class Recipe:
    """Enhanced recipe model with nutrition tracking and community features."""
    
    def __init__(self, **kwargs):
        """Initialize Recipe instance from database row or kwargs."""
        import json
        
        self.id = kwargs.get('id')
        self.name = kwargs.get('name')
        self.description = kwargs.get('description')
        self.ingredients = kwargs.get('ingredients')
        self.instructions = kwargs.get('instructions')
        self.prep_time_minutes = kwargs.get('prep_time_minutes')
        self.cook_time_minutes = kwargs.get('cook_time_minutes')
        self.total_time_minutes = kwargs.get('total_time_minutes')
        self.servings = kwargs.get('servings', 1)
        self.difficulty_level = kwargs.get('difficulty_level')
        self.category = kwargs.get('category')
        self.cuisine_type = kwargs.get('cuisine_type')
        
        # Handle JSON dietary_tags field
        dietary_tags = kwargs.get('dietary_tags')
        if isinstance(dietary_tags, str):
            try:
                self.dietary_tags = json.loads(dietary_tags)
            except (json.JSONDecodeError, TypeError):
                self.dietary_tags = None
        else:
            self.dietary_tags = dietary_tags
            
        self.image_url = kwargs.get('image_url')
        self.video_url = kwargs.get('video_url')
        self.is_public = kwargs.get('is_public', True)
        self.is_featured = kwargs.get('is_featured', False)
        self.is_approved = kwargs.get('is_approved', True)
        self.created_by_user_id = kwargs.get('created_by_user_id')
        self.created_at = kwargs.get('created_at')
        self.updated_at = kwargs.get('updated_at')
        
        # Cache for related data
        self._ingredients = None
        self._instructions = None
        self._nutrition = None
        self._ratings = None
        self._creator = None
    
    @staticmethod
    def create(name: str, created_by_user_id: int, **kwargs) -> 'Recipe':
        """Create a new recipe in the database."""
        db_client = get_db_client()
        
        import json
        
        # Convert dietary_tags to JSON string if it's a list/dict
        dietary_tags = kwargs.get('dietary_tags')
        if isinstance(dietary_tags, (list, dict)):
            dietary_tags = json.dumps(dietary_tags)
        
        query = """
            INSERT INTO recipes 
            (name, description, ingredients, instructions, prep_time_minutes, cook_time_minutes, 
             total_time_minutes, servings, difficulty_level, category, cuisine_type, dietary_tags,
             image_url, video_url, is_public, is_featured, is_approved, created_by_user_id, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """
        
        recipe_id = db_client.execute_insert(query, (
            name, kwargs.get('description'), kwargs.get('ingredients'), kwargs.get('instructions'),
            kwargs.get('prep_time_minutes'), kwargs.get('cook_time_minutes'), kwargs.get('total_time_minutes'),
            kwargs.get('servings', 1), kwargs.get('difficulty_level'), kwargs.get('category'),
            kwargs.get('cuisine_type'), dietary_tags, kwargs.get('image_url'), kwargs.get('video_url'),
            kwargs.get('is_public', True), kwargs.get('is_featured', False), kwargs.get('is_approved', True),
            created_by_user_id
        ))
        
        # Create recipe data for return
        recipe_data = {
            'id': recipe_id,
            'name': name,
            'description': kwargs.get('description'),
            'ingredients': kwargs.get('ingredients'),
            'instructions': kwargs.get('instructions'),
            'prep_time_minutes': kwargs.get('prep_time_minutes'),
            'cook_time_minutes': kwargs.get('cook_time_minutes'),
            'total_time_minutes': kwargs.get('total_time_minutes'),
            'servings': kwargs.get('servings', 1),
            'difficulty_level': kwargs.get('difficulty_level'),
            'category': kwargs.get('category'),
            'cuisine_type': kwargs.get('cuisine_type'),
            'dietary_tags': kwargs.get('dietary_tags'),
            'image_url': kwargs.get('image_url'),
            'video_url': kwargs.get('video_url'),
            'is_public': kwargs.get('is_public', True),
            'is_featured': kwargs.get('is_featured', False),
            'is_approved': kwargs.get('is_approved', True),
            'created_by_user_id': created_by_user_id
        }
        return Recipe(**recipe_data)
    
    @staticmethod
    def get(recipe_id: int) -> Optional['Recipe']:
        """Get recipe by ID."""
        db_client = get_db_client()
        result = db_client.fetch_one("SELECT * FROM recipes WHERE id = %s", (recipe_id,))
        return Recipe(**result) if result else None
    
    @staticmethod
    def update(recipe_id: int, update_data: Dict[str, Any]) -> bool:
        """Update an existing recipe in the database."""
        db_client = get_db_client()
        
        # Only include allowed fields for update
        allowed_fields = {
            'name', 'description', 'ingredients', 'instructions', 
            'prep_time_minutes', 'cook_time_minutes', 'total_time_minutes',
            'servings', 'difficulty_level', 'category', 'cuisine_type',
            'dietary_tags', 'image_url', 'video_url', 'is_public', 'is_featured'
        }
        
        filtered_data = {k: v for k, v in update_data.items() if k in allowed_fields}
        
        if not filtered_data:
            return False
        
        try:
            import json
            
            # Build SET clause dynamically based on filtered_data
            set_parts = []
            params = []
            
            for key, value in filtered_data.items():
                set_parts.append(f"{key} = %s")
                # Handle JSON fields
                if isinstance(value, (list, dict)):
                    params.append(json.dumps(value))
                else:
                    params.append(value)
            
            if not set_parts:
                return False
            
            set_clause = ", ".join(set_parts)
            params.append(recipe_id)  # Add recipe_id for WHERE clause
            
            query = f"UPDATE recipes SET {set_clause}, updated_at = NOW() WHERE id = %s"
            result = db_client.execute_update(query, tuple(params))
            return result > 0  # Returns number of affected rows
        except Exception as e:
            print(f"Error updating recipe {recipe_id}: {e}")
            return False
    
    @staticmethod
    def delete(recipe_id: int) -> bool:
        """Delete a recipe from the database."""
        db_client = get_db_client()
        
        try:
            result = db_client.execute_delete("DELETE FROM recipes WHERE id = %s", (recipe_id,))
            return result > 0  # Returns number of affected rows
        except Exception as e:
            print(f"Error deleting recipe {recipe_id}: {e}")
            return False
    
    @staticmethod
    def count(filters: Dict[str, Any] = None) -> int:
        """Get total recipe count with optional filters."""
        db_client = get_db_client()
        
        query = "SELECT COUNT(*) as count FROM recipes"
        params = ()
        
        if filters:
            # Build WHERE clause manually for direct SQL
            where_parts = []
            filter_params = []
            for key, value in filters.items():
                if value is None:
                    where_parts.append(f"{key} IS NULL")
                elif isinstance(value, (list, tuple)):
                    placeholders = ', '.join(['%s'] * len(value))
                    where_parts.append(f"{key} IN ({placeholders})")
                    filter_params.extend(value)
                elif isinstance(value, bool):
                    where_parts.append(f"{key} = %s")
                    filter_params.append(1 if value else 0)
                else:
                    where_parts.append(f"{key} = %s")
                    filter_params.append(value)
            
            if where_parts:
                query += " WHERE " + " AND ".join(where_parts)
                params = tuple(filter_params)
        
        result = db_client.fetch_one(query, params)
        return result['count'] if result else 0
    
    @staticmethod
    def get_all(page: int = 1, per_page: int = 20, filters: Dict[str, Any] = None, 
               order_by: str = "created_at DESC") -> Dict[str, Any]:
        """Get paginated list of recipes with optional filters."""
        db_client = get_db_client()
        
        base_query = "SELECT * FROM recipes"
        params = ()
        
        if filters:
            # Build WHERE clause manually for direct SQL
            where_parts = []
            filter_params = []
            for key, value in filters.items():
                if value is None:
                    where_parts.append(f"{key} IS NULL")
                elif isinstance(value, (list, tuple)):
                    placeholders = ', '.join(['%s'] * len(value))
                    where_parts.append(f"{key} IN ({placeholders})")
                    filter_params.extend(value)
                elif isinstance(value, bool):
                    where_parts.append(f"{key} = %s")
                    filter_params.append(1 if value else 0)
                else:
                    where_parts.append(f"{key} = %s")
                    filter_params.append(value)
            
            if where_parts:
                base_query += " WHERE " + " AND ".join(where_parts)
                params = tuple(filter_params)
        
        base_query += f" ORDER BY {order_by}"
        
        result = db_client.fetch_paginated(base_query, params, page, per_page)
        result['items'] = [Recipe(**row) for row in result['items']]
        return result
    
    @staticmethod
    def search(query: str, filters: Dict[str, Any] = None, limit: int = 20) -> List['Recipe']:
        """Search recipes by name, description, ingredients, category, cuisine_type, or dietary tags."""
        db_client = get_db_client()
        
        search_term = f"%{query}%"
        
        # Build comprehensive search query across multiple fields
        # For JSON tags, we search for exact matches and also convert JSON to text for partial matching
        # Also search in recipe_ingredients table for individual ingredient names
        search_query = """
        SELECT DISTINCT r.* FROM recipes r
        LEFT JOIN recipe_ingredients ri ON r.id = ri.recipe_id
        WHERE (
            r.name LIKE %s 
            OR r.description LIKE %s 
            OR r.ingredients LIKE %s
            OR r.category LIKE %s
            OR r.cuisine_type LIKE %s
            OR (r.dietary_tags IS NOT NULL AND (
                JSON_SEARCH(r.dietary_tags, 'one', %s) IS NOT NULL
                OR CAST(r.dietary_tags AS CHAR) LIKE %s
            ))
            OR ri.ingredient_name LIKE %s
        )
        """
        # Search for exact tag match and also search in JSON text representation
        # Added search_term for recipe_ingredients.ingredient_name
        params = [search_term, search_term, search_term, search_term, search_term, query, search_term, search_term]
        
        if filters:
            # Build WHERE clause manually for direct SQL
            where_parts = []
            for key, value in filters.items():
                if value is None:
                    where_parts.append(f"{key} IS NULL")
                elif isinstance(value, (list, tuple)):
                    placeholders = ', '.join(['%s'] * len(value))
                    where_parts.append(f"{key} IN ({placeholders})")
                    params.extend(value)
                elif isinstance(value, bool):
                    where_parts.append(f"{key} = %s")
                    params.append(1 if value else 0)
                else:
                    where_parts.append(f"{key} = %s")
                    params.append(value)
            
            if where_parts:
                search_query += " AND " + " AND ".join(where_parts)
        
        search_query += " ORDER BY r.is_featured DESC, r.created_at DESC LIMIT %s"
        params.append(limit)
        
        results = db_client.execute_query(search_query, tuple(params))
        return [Recipe(**row) for row in results]
    
    @staticmethod
    def get_categories() -> List[str]:
        """Get list of distinct recipe categories."""
        db_client = get_db_client()
        query = """
        SELECT DISTINCT category 
        FROM recipes 
        WHERE category IS NOT NULL AND category != '' 
        AND is_public = 1 AND is_approved = 1
        ORDER BY category
        """
        results = db_client.execute_query(query)
        return [row['category'] for row in results]
    
    def get_ingredients(self) -> List[Dict[str, Any]]:
        """Get ingredients for this recipe."""
        if self._ingredients is None and self.id:
            db_client = get_db_client()
            query = """
            SELECT * FROM recipe_ingredients 
            WHERE recipe_id = %s 
            ORDER BY order_index ASC
            """
            self._ingredients = db_client.execute_query(query, (self.id,))
        return self._ingredients or []
    
    def get_instructions(self) -> List[Dict[str, Any]]:
        """Get instructions for this recipe."""
        if self._instructions is None and self.id:
            db_client = get_db_client()
            query = """
            SELECT * FROM recipe_instructions 
            WHERE recipe_id = %s 
            ORDER BY step_number ASC
            """
            self._instructions = db_client.execute_query(query, (self.id,))
        return self._instructions or []
    
    def get_nutrition(self) -> Optional[Dict[str, Any]]:
        """Get nutrition information for this recipe."""
        if self._nutrition is None and self.id:
            db_client = get_db_client()
            result = db_client.fetch_one("SELECT * FROM recipe_nutrition WHERE recipe_id = %s", (self.id,))
            self._nutrition = result
        return self._nutrition
    
    def get_ratings(self) -> List[Dict[str, Any]]:
        """Get ratings for this recipe."""
        if self._ratings is None and self.id:
            db_client = get_db_client()
            query = """
            SELECT rr.*, u.username 
            FROM recipe_ratings rr
            JOIN users u ON rr.user_id = u.id
            WHERE rr.recipe_id = %s AND rr.is_approved = 1
            ORDER BY rr.created_at DESC
            """
            self._ratings = db_client.execute_query(query, (self.id,))
        return self._ratings or []
    
    @property
    def average_rating(self) -> Optional[float]:
        """Calculate average rating for the recipe."""
        if not self.id:
            return None
        
        db_client = get_db_client()
        result = db_client.fetch_one(
            "SELECT AVG(rating) as avg_rating FROM recipe_ratings WHERE recipe_id = %s AND is_approved = 1",
            (self.id,)
        )
        return float(result['avg_rating']) if result and result['avg_rating'] else None
    
    @property
    def rating_count(self) -> int:
        """Get total number of ratings."""
        if not self.id:
            return 0
        
        db_client = get_db_client()
        result = db_client.fetch_one(
            "SELECT COUNT(*) as count FROM recipe_ratings WHERE recipe_id = %s AND is_approved = 1",
            (self.id,)
        )
        return result['count'] if result else 0
    
    def get_creator(self) -> Optional[User]:
        """Get the user who created this recipe."""
        if self._creator is None and self.created_by_user_id:
            self._creator = User.get(self.created_by_user_id)
        return self._creator
    
    def save(self) -> None:
        """Save recipe changes to database."""
        if not self.id:
            raise ValueError("Cannot save recipe without ID. Use Recipe.create() for new recipes.")
        
        db_client = get_db_client()
        
        import json
        
        # Handle dietary_tags JSON serialization
        dietary_tags = self.dietary_tags
        if isinstance(dietary_tags, (list, dict)):
            dietary_tags = json.dumps(dietary_tags)
        
        query = """
            UPDATE recipes SET 
                name = %s, description = %s, ingredients = %s, instructions = %s,
                prep_time_minutes = %s, cook_time_minutes = %s, total_time_minutes = %s,
                servings = %s, difficulty_level = %s, category = %s, cuisine_type = %s,
                dietary_tags = %s, image_url = %s, video_url = %s, is_public = %s,
                is_featured = %s, is_approved = %s, updated_at = NOW()
            WHERE id = %s
        """
        
        db_client.execute_update(query, (
            self.name, self.description, self.ingredients, self.instructions,
            self.prep_time_minutes, self.cook_time_minutes, self.total_time_minutes,
            self.servings, self.difficulty_level, self.category, self.cuisine_type,
            dietary_tags, self.image_url, self.video_url, self.is_public,
            self.is_featured, self.is_approved, self.id
        ))
    
    def __repr__(self):
        return f'<Recipe {self.name}>'


# Additional model classes for completeness

class RecipeRating:
    """User ratings and reviews for recipes."""
    
    def __init__(self, **kwargs):
        self.id = kwargs.get('id')
        self.recipe_id = kwargs.get('recipe_id')
        self.user_id = kwargs.get('user_id')
        self.rating = kwargs.get('rating')
        self.review_text = kwargs.get('review_text')
        self.would_make_again = kwargs.get('would_make_again')
        self.is_approved = kwargs.get('is_approved', True)
        self.flagged_count = kwargs.get('flagged_count', 0)
        self.created_at = kwargs.get('created_at')
        self.updated_at = kwargs.get('updated_at')
    
    @staticmethod
    def create(recipe_id: int, user_id: int, rating: int, **kwargs) -> 'RecipeRating':
        """Create a new recipe rating."""
        db_client = get_db_client()
        
        query = """
            INSERT INTO recipe_ratings 
            (recipe_id, user_id, rating, review_text, would_make_again, is_approved, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
        """
        
        rating_id = db_client.execute_insert(query, (
            recipe_id, user_id, rating, kwargs.get('review_text'),
            kwargs.get('would_make_again'), kwargs.get('is_approved', True)
        ))
        
        # Create rating data for return
        rating_data = {
            'id': rating_id,
            'recipe_id': recipe_id,
            'user_id': user_id,
            'rating': rating,
            'review_text': kwargs.get('review_text'),
            'would_make_again': kwargs.get('would_make_again'),
            'is_approved': kwargs.get('is_approved', True)
        }
        return RecipeRating(**rating_data)
    
    @staticmethod
    def get_by_user_and_recipe(user_id: int, recipe_id: int) -> Optional['RecipeRating']:
        """Get rating by user and recipe."""
        db_client = get_db_client()
        result = db_client.fetch_one(
            "SELECT * FROM recipe_ratings WHERE user_id = %s AND recipe_id = %s",
            (user_id, recipe_id)
        )
        return RecipeRating(**result) if result else None


class UserSavedRecipe:
    """Users' saved/bookmarked recipes."""
    
    def __init__(self, **kwargs):
        self.id = kwargs.get('id')
        self.user_id = kwargs.get('user_id')
        self.recipe_id = kwargs.get('recipe_id')
        self.notes = kwargs.get('notes')
        self.created_at = kwargs.get('created_at')
    
    @staticmethod
    def create(user_id: int, recipe_id: int, **kwargs) -> 'UserSavedRecipe':
        """Create a new saved recipe."""
        db_client = get_db_client()
        
        query = """
            INSERT INTO user_saved_recipes 
            (user_id, recipe_id, notes, created_at)
            VALUES (%s, %s, %s, NOW())
        """
        
        saved_id = db_client.execute_insert(query, (
            user_id, recipe_id, kwargs.get('notes')
        ))
        
        # Create saved data for return
        saved_data = {
            'id': saved_id,
            'user_id': user_id,
            'recipe_id': recipe_id,
            'notes': kwargs.get('notes')
        }
        return UserSavedRecipe(**saved_data)
    
    @staticmethod
    def get_by_user_and_recipe(user_id: int, recipe_id: int) -> Optional['UserSavedRecipe']:
        """Get saved recipe by user and recipe."""
        db_client = get_db_client()
        result = db_client.fetch_one(
            "SELECT * FROM user_saved_recipes WHERE user_id = %s AND recipe_id = %s",
            (user_id, recipe_id)
        )
        return UserSavedRecipe(**result) if result else None
    
    @staticmethod
    def is_saved(user_id: int, recipe_id: int) -> bool:
        """Check if a recipe is saved by a user."""
        return UserSavedRecipe.get_by_user_and_recipe(user_id, recipe_id) is not None
    
    @staticmethod
    def delete(user_id: int, recipe_id: int) -> bool:
        """Delete saved recipe by user and recipe IDs."""
        db_client = get_db_client()
        result = db_client.execute_delete(
            "DELETE FROM user_saved_recipes WHERE user_id = %s AND recipe_id = %s",
            (user_id, recipe_id)
        )
        return result > 0
    
    def delete(self) -> None:
        """Delete saved recipe."""
        if not self.id:
            raise ValueError("Cannot delete saved recipe without ID")
        
        db_client = get_db_client()
        db_client.execute_delete("DELETE FROM user_saved_recipes WHERE id = %s", (self.id,))


class UserProductHistory:
    """Track products that users have scanned or viewed."""
    
    def __init__(self, **kwargs):
        self.id = kwargs.get('id')
        self.user_id = kwargs.get('user_id')
        self.product_id = kwargs.get('product_id')
        self.action_type = kwargs.get('action_type')
        self.quantity_consumed = kwargs.get('quantity_consumed')
        self.serving_size_consumed = kwargs.get('serving_size_consumed')
        self.timestamp = kwargs.get('timestamp')
    
    @staticmethod
    def create(user_id: int, product_id: int, action_type: str, **kwargs) -> 'UserProductHistory':
        """Create a new product history entry."""
        db_client = get_db_client()
        
        query = """
            INSERT INTO user_product_history 
            (user_id, product_id, action_type, quantity_consumed, serving_size_consumed, timestamp)
            VALUES (%s, %s, %s, %s, %s, NOW())
        """
        
        history_id = db_client.execute_insert(query, (
            user_id, product_id, action_type, kwargs.get('quantity_consumed'),
            kwargs.get('serving_size_consumed')
        ))
        
        # Create history data for return
        history_data = {
            'id': history_id,
            'user_id': user_id,
            'product_id': product_id,
            'action_type': action_type,
            'quantity_consumed': kwargs.get('quantity_consumed'),
            'serving_size_consumed': kwargs.get('serving_size_consumed')
        }
        return UserProductHistory(**history_data)


# Helper functions for database initialization

# Database initialization functions removed - not used in application
# init_database(), create_tables() functions removed

# Stub model classes removed - these were incomplete implementations:
# - ReportedContent class removed
# - AdminAction class removed  
# - SponsoredContent class removed

# Enum classes kept for existing code compatibility
class UserRole:
    """User role enumeration."""
    USER = 'user'
    MODERATOR = 'moderator'
    ADMIN = 'admin'


class ContentType:
    """Content type enumeration."""
    RECIPE = 'recipe'
    REVIEW = 'review'
    PRODUCT = 'product'