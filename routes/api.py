"""
API routes for barcode scanning, nutrition lookup, and AJAX functionality.
"""

from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from models import Product, ProductNutrition, UserProductHistory, Recipe, UserSavedRecipe, RecipeRating
from db_client import get_db_client
import requests
import json

api_bp = Blueprint('api', __name__)

# External API configurations (placeholder - replace with real API keys)
NUTRITION_API_KEY = "your-nutrition-api-key"
BARCODE_API_KEY = "your-barcode-api-key"

@api_bp.route('/barcode/<barcode>')
@login_required
def lookup_barcode(barcode):
    """Look up product information by barcode."""
    try:
        # First check our local database
        product = Product.get_by_barcode(barcode)
        
        if product:
            # Log user activity
            UserProductHistory.create(
                user_id=current_user.id,
                product_id=product.id,
                action_type='scanned'
            )
            
            # Get nutrition data
            nutrition = ProductNutrition.get_by_product_id(product.id)
            
            return jsonify({
                'found': True,
                'source': 'local',
                'product': {
                    'id': product.id,
                    'name': product.name,
                    'brand': product.brand,
                    'barcode': product.barcode,
                    'description': product.description,
                    'category': product.category,
                    'serving_size': product.serving_size,
                    'serving_size_unit': product.serving_size_unit,
                    'nutrition': nutrition.calories if nutrition else None
                }
            })
        
        # If not in local DB, try external APIs
        external_product = fetch_product_from_external_api(barcode)
        
        if external_product:
            # Add to our database
            new_product = Product.create(
                barcode=barcode,
                name=external_product.get('name', 'Unknown Product'),
                brand=external_product.get('brand'),
                description=external_product.get('description'),
                category=external_product.get('category'),
                serving_size=external_product.get('serving_size'),
                serving_size_unit=external_product.get('serving_size_unit', 'g'),
                created_by_user_id=current_user.id
            )
            
            # Add nutrition if available
            if external_product.get('nutrition') and new_product:
                ProductNutrition.create(
                    product_id=new_product.id,
                    **external_product['nutrition']
                )
            
            # Log user activity
            UserProductHistory.create(
                user_id=current_user.id,
                product_id=new_product.id,
                action_type='scanned'
            )
            
            return jsonify({
                'found': True,
                'source': 'external',
                'product': {
                    'id': new_product.id,
                    'name': new_product.name,
                    'brand': new_product.brand,
                    'barcode': new_product.barcode,
                    'description': new_product.description,
                    'category': new_product.category,
                    'serving_size': new_product.serving_size,
                    'serving_size_unit': new_product.serving_size_unit,
                    'nutrition': external_product.get('nutrition', {}).get('calories')
                }
            })
        
        # Product not found anywhere
        return jsonify({
            'found': False,
            'message': 'Product not found. You can add it manually.',
            'barcode': barcode
        }), 404
    
    except Exception as e:
        current_app.logger.error(f"Barcode lookup error: {e}")
        return jsonify({'error': 'Failed to lookup product'}), 500

@api_bp.route('/product', methods=['POST'])
@login_required
def add_product():
    """Add a new product to the database."""
    try:
        data = request.get_json()
        
        # Validation
        required_fields = ['barcode', 'name']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Check if barcode already exists
        existing = Product.get_by_barcode(data['barcode'])
        if existing:
            return jsonify({'error': 'Product with this barcode already exists'}), 409
        
        # Create product
        product = Product.create(
            barcode=data['barcode'],
            name=data['name'],
            brand=data.get('brand'),
            description=data.get('description'),
            category=data.get('category'),
            serving_size=data.get('serving_size'),
            serving_size_unit=data.get('serving_size_unit', 'g'),
            created_by_user_id=current_user.id
        )
        
        if not product:
            return jsonify({'error': 'Failed to create product'}), 500
        
        # Add nutrition if provided
        nutrition_data = data.get('nutrition', {})
        if any(nutrition_data.values()):
            ProductNutrition.create(
                product_id=product.id,
                calories=nutrition_data.get('calories'),
                protein_g=nutrition_data.get('protein_g'),
                carbohydrates_g=nutrition_data.get('carbohydrates_g'),
                fiber_g=nutrition_data.get('fiber_g'),
                sugars_g=nutrition_data.get('sugars_g'),
                fat_total_g=nutrition_data.get('fat_total_g'),
                fat_saturated_g=nutrition_data.get('fat_saturated_g'),
                sodium_mg=nutrition_data.get('sodium_mg')
            )
        
        return jsonify({
            'success': True,
            'product_id': product.id,
            'message': 'Product added successfully'
        })
    
    except Exception as e:
        current_app.logger.error(f"Add product error: {e}")
        return jsonify({'error': 'Failed to add product'}), 500

@api_bp.route('/nutrition/calculate', methods=['POST'])
@login_required
def calculate_nutrition():
    """Calculate nutrition for custom serving sizes or recipe combinations."""
    try:
        data = request.get_json()
        
        # Handle single product calculation
        if data.get('product_id') and data.get('quantity'):
            product = Product.get(data['product_id'])
            if not product:
                return jsonify({'error': 'Product not found'}), 404
            
            nutrition = ProductNutrition.get_by_product_id(product.id)
            if not nutrition:
                return jsonify({'error': 'Nutrition data not available for this product'}), 400
            
            quantity = float(data['quantity'])
            serving_ratio = quantity / (product.serving_size or 100)
            
            calculated_nutrition = {
                'calories': round((nutrition.calories or 0) * serving_ratio, 1),
                'protein_g': round((nutrition.protein_g or 0) * serving_ratio, 1),
                'carbohydrates_g': round((nutrition.carbohydrates_g or 0) * serving_ratio, 1),
                'fat_total_g': round((nutrition.fat_total_g or 0) * serving_ratio, 1),
                'fiber_g': round((nutrition.fiber_g or 0) * serving_ratio, 1),
                'sodium_mg': round((nutrition.sodium_mg or 0) * serving_ratio, 1)
            }
            
            return jsonify({
                'success': True,
                'nutrition': calculated_nutrition,
                'quantity': quantity,
                'unit': product.serving_size_unit
            })
        
        # Handle recipe ingredient combination calculation
        elif data.get('ingredients'):
            total_nutrition = {
                'calories': 0,
                'protein_g': 0,
                'carbohydrates_g': 0,
                'fat_total_g': 0,
                'fiber_g': 0,
                'sodium_mg': 0
            }
            
            for ingredient in data['ingredients']:
                product = Product.get(ingredient.get('product_id'))
                if product:
                    nutrition = ProductNutrition.get_by_product_id(product.id)
                    if nutrition:
                        quantity = float(ingredient.get('quantity', 0))
                        serving_ratio = quantity / (product.serving_size or 100)
                        
                        total_nutrition['calories'] += (nutrition.calories or 0) * serving_ratio
                        total_nutrition['protein_g'] += (nutrition.protein_g or 0) * serving_ratio
                        total_nutrition['carbohydrates_g'] += (nutrition.carbohydrates_g or 0) * serving_ratio
                        total_nutrition['fat_total_g'] += (nutrition.fat_total_g or 0) * serving_ratio
                        total_nutrition['fiber_g'] += (nutrition.fiber_g or 0) * serving_ratio
                        total_nutrition['sodium_mg'] += (nutrition.sodium_mg or 0) * serving_ratio
            
            # Round all values
            for key in total_nutrition:
                total_nutrition[key] = round(total_nutrition[key], 1)
            
            # Calculate per serving if servings specified
            servings = data.get('servings', 1)
            if servings > 1:
                per_serving = {key: round(value / servings, 1) for key, value in total_nutrition.items()}
                return jsonify({
                    'success': True,
                    'nutrition_total': total_nutrition,
                    'nutrition_per_serving': per_serving,
                    'servings': servings
                })
            
            return jsonify({
                'success': True,
                'nutrition': total_nutrition
            })
        
        return jsonify({'error': 'Invalid request data'}), 400
    
    except Exception as e:
        current_app.logger.error(f"Nutrition calculation error: {e}")
        return jsonify({'error': 'Failed to calculate nutrition'}), 500

@api_bp.route('/recipe/<int:recipe_id>/save', methods=['POST'])
@login_required
def save_recipe(recipe_id):
    """Save/unsave a recipe for the current user."""
    try:
        recipe = Recipe.get(recipe_id)
        if not recipe:
            return jsonify({'error': 'Recipe not found'}), 404
        
        # Check if already saved
        is_saved = UserSavedRecipe.is_saved(current_user.id, recipe_id)
        
        if is_saved:
            # Remove save
            UserSavedRecipe.delete(current_user.id, recipe_id)
            action = 'removed'
        else:
            # Add save
            UserSavedRecipe.create(
                user_id=current_user.id,
                recipe_id=recipe_id
            )
            action = 'saved'
        
        return jsonify({
            'success': True,
            'action': action,
            'is_saved': action == 'saved'
        })
    
    except Exception as e:
        current_app.logger.error(f"Save recipe error: {e}")
        return jsonify({'error': 'Failed to save recipe'}), 500

@api_bp.route('/recipe/<int:recipe_id>/rate', methods=['POST'])
@login_required
def rate_recipe(recipe_id):
    """Rate a recipe (1-5 stars)."""
    try:
        data = request.get_json()
        rating = data.get('rating')
        review_text = data.get('review_text', '').strip()
        
        if not rating or rating not in [1, 2, 3, 4, 5]:
            return jsonify({'error': 'Rating must be between 1 and 5'}), 400
        
        recipe = Recipe.get(recipe_id)
        if not recipe:
            return jsonify({'error': 'Recipe not found'}), 404
        
        # Check if user already rated this recipe
        existing_rating = RecipeRating.get_by_user_and_recipe(current_user.id, recipe_id)
        
        if existing_rating:
            # Update existing rating
            existing_rating.rating = rating
            existing_rating.review_text = review_text if review_text else None
            existing_rating.save()
            action = 'updated'
        else:
            # Create new rating
            RecipeRating.create(
                user_id=current_user.id,
                recipe_id=recipe_id,
                rating=rating,
                review_text=review_text if review_text else None
            )
            action = 'created'
        
        return jsonify({
            'success': True,
            'action': action,
            'rating': rating
        })
    
    except Exception as e:
        current_app.logger.error(f"Rate recipe error: {e}")
        return jsonify({'error': 'Failed to rate recipe'}), 500

@api_bp.route('/product/search')
@login_required
def search_products():
    """Search products by name or barcode."""
    try:
        query = request.args.get('q', '').strip()
        
        if not query or len(query) < 2:
            return jsonify({'products': []})
        
        # Search products using the model's search method
        products_data = Product.search(query, limit=20)
        
        products = []
        for product in products_data:
            # Get nutrition data for each product
            nutrition = ProductNutrition.get_by_product_id(product.id)
            
            product_dict = {
                'id': product.id,
                'name': product.name,
                'brand': product.brand,
                'barcode': product.barcode,
                'description': product.description,
                'category': product.category,
                'serving_size': product.serving_size,
                'serving_size_unit': product.serving_size_unit,
                'nutrition': {
                    'calories': nutrition.calories if nutrition else None,
                    'protein_g': nutrition.protein_g if nutrition else None,
                    'carbohydrates_g': nutrition.carbohydrates_g if nutrition else None,
                    'fat_total_g': nutrition.fat_total_g if nutrition else None,
                    'fiber_g': nutrition.fiber_g if nutrition else None,
                    'sodium_mg': nutrition.sodium_mg if nutrition else None
                } if nutrition else {}
            }
            products.append(product_dict)
        
        return jsonify({'products': products})
    
    except Exception as e:
        current_app.logger.error(f"Product search error: {e}")
        return jsonify({'error': 'Search failed'}), 500

@api_bp.route('/product/<int:product_id>')
@login_required
def get_product_by_id(product_id):
    """Get detailed product information by ID."""
    try:
        product = Product.get(product_id)
        if not product:
            return jsonify({'error': 'Product not found'}), 404
        
        # Get nutrition data
        nutrition = ProductNutrition.get_by_product_id(product.id)
        
        product_data = {
            'product': {
                'id': product.id,
                'name': product.name,
                'brand': product.brand,
                'barcode': product.barcode,
                'description': product.description,
                'category': product.category,
                'serving_size': product.serving_size,
                'serving_size_unit': product.serving_size_unit,
                'nutrition': {
                    'calories': nutrition.calories if nutrition else None,
                    'protein_g': nutrition.protein_g if nutrition else None,
                    'carbohydrates_g': nutrition.carbohydrates_g if nutrition else None,
                    'fat_total_g': nutrition.fat_total_g if nutrition else None,
                    'fiber_g': nutrition.fiber_g if nutrition else None,
                    'sodium_mg': nutrition.sodium_mg if nutrition else None,
                    'sugars_g': nutrition.sugars_g if nutrition else None,
                    'fat_saturated_g': nutrition.fat_saturated_g if nutrition else None
                } if nutrition else {}
            }
        }
        
        return jsonify(product_data)
    
    except Exception as e:
        current_app.logger.error(f"Get product error: {e}")
        return jsonify({'error': 'Failed to get product'}), 500

@api_bp.route('/recipes')
@login_required  
def get_recipes_api():
    """Get recipes as JSON API."""
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        search = request.args.get('search', '').strip()
        
        filters = {'is_public': True, 'is_approved': True}
        
        if search:
            recipes_data = Recipe.search(search, filters=filters, limit=per_page)
            # Convert to paginated format for consistency
            result = {
                'items': recipes_data,
                'total': len(recipes_data),
                'page': 1,
                'per_page': per_page,
                'pages': 1
            }
        else:
            result = Recipe.get_all(page=page, per_page=per_page, filters=filters)
        
        # Convert recipes to JSON-serializable format
        recipes = []
        for recipe in result['items']:
            recipe_dict = {
                'id': recipe.id,
                'name': recipe.name,
                'description': recipe.description,
                'ingredients': recipe.ingredients,
                'instructions': recipe.instructions,
                'prep_time_minutes': recipe.prep_time_minutes,
                'cook_time_minutes': recipe.cook_time_minutes,
                'servings': recipe.servings,
                'category': recipe.category,
                'cuisine_type': recipe.cuisine_type,
                'difficulty_level': recipe.difficulty_level,
                'is_featured': recipe.is_featured,
                'created_at': recipe.created_at.isoformat() if recipe.created_at else None,
                'average_rating': recipe.average_rating,
                'rating_count': recipe.rating_count
            }
            recipes.append(recipe_dict)
        
        return jsonify({
            'recipes': recipes,
            'pagination': {
                'page': result['page'],
                'per_page': result['per_page'],
                'total': result['total'],
                'pages': result['pages']
            }
        })
    
    except Exception as e:
        current_app.logger.error(f"Get recipes API error: {e}")
        return jsonify({'error': 'Failed to get recipes'}), 500

@api_bp.route('/nutrition/search')
@login_required
def search_nutrition():
    """Search nutrition database (external API integration)."""
    try:
        query = request.args.get('q', '').strip()
        
        if not query:
            return jsonify({'items': []})
        
        # This would integrate with external nutrition APIs
        # For now, return local product search results
        products = Product.search(query, limit=10)
        
        nutrition_items = []
        for product in products:
            nutrition = ProductNutrition.get_by_product_id(product.id)
            if nutrition:
                nutrition_items.append({
                    'id': product.id,
                    'name': product.name,
                    'brand': product.brand,
                    'serving_size': product.serving_size,
                    'serving_unit': product.serving_size_unit,
                    'calories': nutrition.calories,
                    'protein': nutrition.protein_g,
                    'carbs': nutrition.carbohydrates_g,
                    'fat': nutrition.fat_total_g
                })
        
        return jsonify({'items': nutrition_items})
    
    except Exception as e:
        current_app.logger.error(f"Nutrition search error: {e}")
        return jsonify({'error': 'Nutrition search failed'}), 500

def fetch_product_from_external_api(barcode):
    """
    Fetch product information from external APIs.
    This is a placeholder implementation - integrate with real APIs like:
    - Open Food Facts
    - FoodData Central (USDA)
    - Edamam Food Database
    """
    # Placeholder implementation
    try:
        # Example: Open Food Facts API
        url = f"https://world.openfoodfacts.org/api/v0/product/{barcode}.json"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('status') == 1:  # Product found
                product_data = data.get('product', {})
                
                return {
                    'name': product_data.get('product_name', 'Unknown Product'),
                    'brand': product_data.get('brands'),
                    'category': product_data.get('categories'),
                    'description': product_data.get('generic_name'),
                    'serving_size': 100,  # Default to 100g
                    'serving_size_unit': 'g',
                    'nutrition': {
                        'calories': product_data.get('nutriments', {}).get('energy-kcal_100g'),
                        'protein_g': product_data.get('nutriments', {}).get('proteins_100g'),
                        'carbohydrates_g': product_data.get('nutriments', {}).get('carbohydrates_100g'),
                        'fat_total_g': product_data.get('nutriments', {}).get('fat_100g'),
                        'fiber_g': product_data.get('nutriments', {}).get('fiber_100g'),
                        'sodium_mg': product_data.get('nutriments', {}).get('sodium_100g')
                    }
                }
    
    except Exception as e:
        current_app.logger.error(f"External API error: {e}")
    
    return None

@api_bp.route('/user/statistics')
@login_required
def user_statistics():
    """Get user activity statistics."""
    try:
        db_client = get_db_client()
        
        # Get recipes created by user
        recipes_created = db_client.execute_query(
            "SELECT COUNT(*) as count FROM recipes WHERE created_by_user_id = %s",
            (current_user.id,)
        )[0]['count']
        
        # Get recipes saved by user
        recipes_saved = db_client.execute_query(
            "SELECT COUNT(*) as count FROM user_saved_recipes WHERE user_id = %s",
            (current_user.id,)
        )[0]['count']
        
        # Get personal ingredients count
        personal_ingredients = db_client.execute_query(
            "SELECT COUNT(*) as count FROM user_personal_ingredients WHERE user_id = %s",
            (current_user.id,)
        )[0]['count']
        
        return jsonify({
            'success': True,
            'statistics': {
                'recipes_created': recipes_created,
                'recipes_saved': recipes_saved,
                'personal_ingredients': personal_ingredients
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"Error fetching user statistics: {e}")
        return jsonify({
            'success': False,
            'message': 'Failed to fetch user statistics'
        }), 500