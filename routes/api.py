"""
API routes for barcode scanning, nutrition lookup, and AJAX functionality.
"""

from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from models import Product, ProductNutrition, UserProductHistory, Recipe, UserSavedRecipe, RecipeRating
from db_client import get_db_client
import requests
import json
import time
import random

api_bp = Blueprint('api', __name__)

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
        required_fields = ['name']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Generate barcode if not provided
        barcode = data.get('barcode', '').strip() if data.get('barcode') else ''
        if not barcode:
            barcode = f'MANUAL_{current_user.id}_{int(time.time())}_{random.randint(1000, 9999)}'
        
        # Check if product with this barcode already exists
        existing = Product.get_by_barcode(barcode)
        if existing:
            # Product already exists, return existing product info
            return jsonify({
                'success': False,
                'error': 'Product with this barcode already exists',
                'existing_product_id': existing.id,
                'existing_product_name': existing.name,
                'message': f'A product with barcode "{barcode}" already exists in the database.'
            }), 409
        
        # Create product
        product = Product.create(
            barcode=barcode,
            name=data['name'],
            brand=data.get('brand'),
            description=data.get('description'),
            category=data.get('category'),
            serving_size=data.get('serving_size'),
            serving_size_unit=data.get('serving_size_unit', 'g'),
            servings_per_container=data.get('servings_per_container'),
            created_by_user_id=current_user.id
        )
        
        if not product:
            return jsonify({'error': 'Failed to create product'}), 500
        
        # Add nutrition if provided
        nutrition_data = data.get('nutrition', {})
        if nutrition_data and any(v is not None and v != '' and v != 0 for v in nutrition_data.values()):
            try:
                ProductNutrition.create(
                    product_id=product.id,
                    calories=nutrition_data.get('calories'),
                    protein_g=nutrition_data.get('protein_g'),
                    carbohydrates_g=nutrition_data.get('carbohydrates_g'),
                    fiber_g=nutrition_data.get('fiber_g'),
                    sugars_g=nutrition_data.get('sugars_g'),
                    fat_total_g=nutrition_data.get('fat_total_g'),
                    fat_saturated_g=nutrition_data.get('fat_saturated_g'),
                    fat_trans_g=nutrition_data.get('fat_trans_g'),
                    sodium_mg=nutrition_data.get('sodium_mg'),
                    cholesterol_mg=nutrition_data.get('cholesterol_mg'),
                    potassium_mg=nutrition_data.get('potassium_mg'),
                    vitamin_a_percent=nutrition_data.get('vitamin_a_percent'),
                    vitamin_c_percent=nutrition_data.get('vitamin_c_percent'),
                    calcium_percent=nutrition_data.get('calcium_percent'),
                    iron_percent=nutrition_data.get('iron_percent')
                )
            except Exception as nutrition_error:
                current_app.logger.error(f"Error adding nutrition data: {nutrition_error}")
                # Don't fail the whole request if nutrition fails, just log it
        
        return jsonify({
            'success': True,
            'product_id': product.id,
            'message': 'Product added successfully'
        })
    
    except ValueError as e:
        current_app.logger.error(f"Add product validation error: {e}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Add product error: {e}")
        import traceback
        current_app.logger.error(traceback.format_exc())
        return jsonify({'error': f'Failed to add product: {str(e)}'}), 500

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

@api_bp.route('/product/delete/<int:product_id>', methods=['POST'])
@login_required
def delete_product(product_id):
    """Delete a product (AJAX endpoint)."""
    try:
        product = Product.get(product_id)
        if not product:
            return jsonify({'error': 'Product not found'}), 404
        
        # Check if user can delete this product
        if product.created_by_user_id != current_user.id and not current_user.is_moderator():
            return jsonify({'error': 'You can only delete your own products'}), 403
        
        # Delete the product
        success = Product.delete(product_id)
        if success:
            return jsonify({'success': True, 'message': 'Product deleted successfully'})
        else:
            # Get more specific error information
            current_app.logger.error(f"Failed to delete product {product_id}")
            return jsonify({'error': 'Failed to delete product. Please check server logs for details.'}), 500
    
    except Exception as e:
        error_msg = str(e)
        current_app.logger.error(f"Error deleting product {product_id}: {error_msg}")
        import traceback
        current_app.logger.error(traceback.format_exc())
        print(f"Error deleting product: {e}")
        traceback.print_exc()
        return jsonify({'error': f'An error occurred while deleting the product: {error_msg}'}), 500

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

@api_bp.route('/recipe/<int:recipe_id>/nutrition')
@login_required
def get_recipe_nutrition(recipe_id):
    """Get nutrition data for a specific recipe."""
    try:
        recipe = Recipe.get(recipe_id)
        if not recipe:
            return jsonify({'error': 'Recipe not found'}), 404
        
        # Check if recipe is accessible
        if not recipe.is_public or not recipe.is_approved:
            if recipe.created_by_user_id != current_user.id and not current_user.is_moderator():
                return jsonify({'error': 'Recipe not accessible'}), 403
        
        # Get nutrition data
        nutrition = recipe.get_nutrition()
        
        if nutrition:
            # Calculate per serving
            servings = recipe.servings or 1
            per_serving = {
                'calories': round((nutrition.get('calories_per_serving') or 0), 1),
                'protein': round((nutrition.get('protein_g') or 0), 1),
                'carbs': round((nutrition.get('carbohydrates_g') or 0), 1),
                'fat': round((nutrition.get('fat_total_g') or 0), 1)
            }
        else:
            # No nutrition data available
            per_serving = {
                'calories': 0,
                'protein': 0,
                'carbs': 0,
                'fat': 0
            }
        
        return jsonify({
            'recipe': {
                'id': recipe.id,
                'name': recipe.name,
                'servings': servings,
                'description': recipe.description
            },
            'nutrition': per_serving
        })
    
    except Exception as e:
        current_app.logger.error(f"Get recipe nutrition error: {e}")
        return jsonify({'error': 'Failed to get recipe nutrition'}), 500

@api_bp.route('/recipe/search')
@login_required
def search_recipes_api():
    """Search recipes for nutrition calculator - includes public recipes and user's personal recipes."""
    try:
        query = request.args.get('q', '').strip()
        
        if not query:
            return jsonify({'recipes': []})
        
        # Search public/approved recipes
        public_recipes = Recipe.search(query, filters={'is_public': True, 'is_approved': True}, limit=20)
        
        # Search user's personal recipes (regardless of public/approved status)
        personal_recipes = Recipe.search(query, filters={'created_by_user_id': current_user.id}, limit=20)
        
        # Combine recipes and remove duplicates using a set of recipe IDs
        seen_ids = set()
        all_recipes = []
        
        # Add personal recipes first (so they appear first in results)
        for recipe in personal_recipes:
            if recipe.id not in seen_ids:
                all_recipes.append(recipe)
                seen_ids.add(recipe.id)
        
        # Add public recipes that aren't already included
        for recipe in public_recipes:
            if recipe.id not in seen_ids:
                all_recipes.append(recipe)
                seen_ids.add(recipe.id)
        
        recipe_list = []
        for recipe in all_recipes:
            nutrition = recipe.get_nutrition()
            recipe_list.append({
                'id': recipe.id,
                'name': recipe.name,
                'servings': recipe.servings or 1,
                'description': recipe.description,
                'category': recipe.category,
                'calories': round((nutrition.get('calories_per_serving') or 0), 1) if nutrition else 0,
                'protein': round((nutrition.get('protein_g') or 0), 1) if nutrition else 0,
                'carbs': round((nutrition.get('carbohydrates_g') or 0), 1) if nutrition else 0,
                'fat': round((nutrition.get('fat_total_g') or 0), 1) if nutrition else 0
            })
        
        return jsonify({'recipes': recipe_list})
    
    except Exception as e:
        current_app.logger.error(f"Recipe search error: {e}")
        return jsonify({'error': 'Recipe search failed'}), 500

@api_bp.route('/ingredients/personal')
@login_required
def get_personal_ingredients():
    """Get user's own personal ingredients only."""
    try:
        db_client = get_db_client()
        # Get only user's own ingredients
        ingredients = db_client.execute_query(
            "SELECT * FROM user_personal_ingredients WHERE user_id = %s ORDER BY name ASC",
            (current_user.id,)
        )
        
        ingredient_list = []
        for ing in ingredients:
            # Nutrition values are per serving (stored in calories_per_100g, etc. columns for backward compatibility)
            ingredient_list.append({
                'id': ing['id'],
                'name': ing['name'],
                'brand': ing.get('brand'),
                'category': ing.get('category'),
                'calories': round((ing.get('calories_per_100g') or 0), 1),
                'protein': round((ing.get('protein_per_100g') or 0), 1),
                'carbs': round((ing.get('carbs_per_100g') or 0), 1),
                'fat': round((ing.get('fat_per_100g') or 0), 1),
                'is_public': bool(ing.get('is_public', False))
            })
        
        return jsonify({'ingredients': ingredient_list})
    
    except Exception as e:
        current_app.logger.error(f"Get personal ingredients error: {e}")
        return jsonify({'error': 'Failed to get personal ingredients'}), 500

@api_bp.route('/ingredients/search')
@login_required
def search_all_ingredients():
    """Search for ingredients from products and personal ingredients for recipe creation."""
    try:
        query = request.args.get('q', '').strip()
        db_client = get_db_client()
        
        results = []
        
        if query and len(query) >= 2:
            search_term = f'%{query}%'
            
            # Search products
            products = db_client.execute_query(
                """SELECT id, name, brand, category, 'product' as type
                   FROM products 
                   WHERE name LIKE %s OR brand LIKE %s
                   ORDER BY name ASC
                   LIMIT 20""",
                (search_term, search_term)
            )
            
            for prod in products:
                results.append({
                    'id': prod['id'],
                    'name': prod['name'],
                    'brand': prod.get('brand'),
                    'category': prod.get('category'),
                    'type': 'product'
                })
            
            # Search personal ingredients (public ones and user's own)
            personal_ingredients = db_client.execute_query(
                """SELECT id, name, brand, category, 'ingredient' as type
                   FROM user_personal_ingredients 
                   WHERE (is_public = 1 OR user_id = %s)
                   AND (name LIKE %s OR brand LIKE %s OR category LIKE %s)
                   ORDER BY name ASC
                   LIMIT 20""",
                (current_user.id, search_term, search_term, search_term)
            )
            
            for ing in personal_ingredients:
                results.append({
                    'id': ing['id'],
                    'name': ing['name'],
                    'brand': ing.get('brand'),
                    'category': ing.get('category'),
                    'type': 'ingredient'
                })
        
        return jsonify({'ingredients': results})
    
    except Exception as e:
        current_app.logger.error(f"Search all ingredients error: {e}")
        return jsonify({'error': 'Failed to search ingredients'}), 500

@api_bp.route('/ingredients/public')
@login_required
def search_public_ingredients():
    """Search for public ingredients from all users."""
    try:
        query = request.args.get('q', '').strip()
        db_client = get_db_client()
        
        if query:
            # Search public ingredients by name, brand, or category
            ingredients = db_client.execute_query(
                """SELECT * FROM user_personal_ingredients 
                   WHERE is_public = 1 AND user_id != %s
                   AND (name LIKE %s OR brand LIKE %s OR category LIKE %s)
                   ORDER BY name ASC
                   LIMIT 50""",
                (current_user.id, f'%{query}%', f'%{query}%', f'%{query}%')
            )
        else:
            # Get all public ingredients (limit to 50)
            ingredients = db_client.execute_query(
                """SELECT * FROM user_personal_ingredients 
                   WHERE is_public = 1 AND user_id != %s
                   ORDER BY name ASC
                   LIMIT 50""",
                (current_user.id,)
            )
        
        ingredient_list = []
        for ing in ingredients:
            # Nutrition values are per serving (stored in calories_per_100g, etc. columns for backward compatibility)
            ingredient_list.append({
                'id': ing['id'],
                'name': ing['name'],
                'brand': ing.get('brand'),
                'category': ing.get('category'),
                'calories': round((ing.get('calories_per_100g') or 0), 1),
                'protein': round((ing.get('protein_per_100g') or 0), 1),
                'carbs': round((ing.get('carbs_per_100g') or 0), 1),
                'fat': round((ing.get('fat_per_100g') or 0), 1)
            })
        
        return jsonify({'ingredients': ingredient_list})
    
    except Exception as e:
        current_app.logger.error(f"Search public ingredients error: {e}")
        return jsonify({'error': 'Failed to search public ingredients'}), 500

@api_bp.route('/personal-ingredients', methods=['POST'])
@login_required
def add_personal_ingredient():
    """Add a new personal ingredient."""
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data.get('name'):
            return jsonify({'success': False, 'message': 'Ingredient name is required'}), 400
        
        db_client = get_db_client()
        
        # Prepare ingredient data
        ingredient_data = {
            'user_id': current_user.id,
            'name': data.get('name', '').strip()
        }
        
        # Handle optional fields safely
        brand = data.get('brand')
        if brand and isinstance(brand, str) and brand.strip():
            ingredient_data['brand'] = brand.strip()
        else:
            ingredient_data['brand'] = None
            
        description = data.get('description')
        if description and isinstance(description, str) and description.strip():
            ingredient_data['description'] = description.strip()
        else:
            ingredient_data['description'] = None
            
        category = data.get('category')
        if category and isinstance(category, str) and category.strip():
            ingredient_data['category'] = category.strip()
        else:
            ingredient_data['category'] = None
        
        # Handle nutrition values
        def safe_float(value):
            if value is None or value == '':
                return None
            try:
                return float(value)
            except (ValueError, TypeError):
                return None
        
        ingredient_data['calories_per_100g'] = safe_float(data.get('calories_per_100g'))
        ingredient_data['protein_per_100g'] = safe_float(data.get('protein_per_100g'))
        ingredient_data['carbs_per_100g'] = safe_float(data.get('carbs_per_100g'))
        ingredient_data['fat_per_100g'] = safe_float(data.get('fat_per_100g'))
        
        # Handle is_public field
        is_public = data.get('is_public', False)
        if isinstance(is_public, str):
            is_public = is_public.lower() in ('true', '1', 'yes', 'on')
        ingredient_data['is_public'] = bool(is_public)
        
        # Insert the ingredient
        query = """
            INSERT INTO user_personal_ingredients 
            (user_id, name, brand, description, category,
             calories_per_100g, protein_per_100g, carbs_per_100g, fat_per_100g,
             is_public, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """
        
        ingredient_id = db_client.execute_insert(query, (
            current_user.id,
            ingredient_data['name'],
            ingredient_data['brand'],
            ingredient_data['description'],
            ingredient_data['category'],
            ingredient_data['calories_per_100g'],
            ingredient_data['protein_per_100g'],
            ingredient_data['carbs_per_100g'],
            ingredient_data['fat_per_100g'],
            ingredient_data['is_public']
        ))
        
        if ingredient_id:
            return jsonify({
                'success': True,
                'message': 'Ingredient added successfully',
                'ingredient_id': ingredient_id
            })
        else:
            return jsonify({'success': False, 'message': 'Failed to add ingredient'}), 500
    
    except ValueError as e:
        current_app.logger.error(f"Add personal ingredient ValueError: {e}")
        return jsonify({'success': False, 'message': f'Invalid nutrition values. Please enter valid numbers. Error: {str(e)}'}), 400
    except Exception as e:
        current_app.logger.error(f"Add personal ingredient error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Failed to add ingredient: {str(e)}'}), 500

@api_bp.route('/personal-ingredients/<int:ingredient_id>', methods=['PUT'])
@login_required
def update_personal_ingredient(ingredient_id):
    """Update an existing personal ingredient."""
    try:
        # Verify ingredient belongs to user
        db_client = get_db_client()
        ingredient = db_client.fetch_one(
            "SELECT * FROM user_personal_ingredients WHERE id = %s AND user_id = %s",
            (ingredient_id, current_user.id)
        )
        
        if not ingredient:
            return jsonify({'success': False, 'message': 'Ingredient not found'}), 404
        
        data = request.get_json()
        
        # Prepare update data
        update_data = {}
        if 'name' in data:
            update_data['name'] = data.get('name').strip()
        if 'brand' in data:
            update_data['brand'] = data.get('brand', '').strip() or None
        if 'description' in data:
            update_data['description'] = data.get('description', '').strip() or None
        if 'category' in data:
            update_data['category'] = data.get('category', '').strip() or None
        if 'calories_per_100g' in data:
            update_data['calories_per_100g'] = float(data.get('calories_per_100g', 0)) if data.get('calories_per_100g') else None
        if 'protein_per_100g' in data:
            update_data['protein_per_100g'] = float(data.get('protein_per_100g', 0)) if data.get('protein_per_100g') else None
        if 'carbs_per_100g' in data:
            update_data['carbs_per_100g'] = float(data.get('carbs_per_100g', 0)) if data.get('carbs_per_100g') else None
        if 'fat_per_100g' in data:
            update_data['fat_per_100g'] = float(data.get('fat_per_100g', 0)) if data.get('fat_per_100g') else None
        if 'is_public' in data:
            is_public = data.get('is_public', False)
            if isinstance(is_public, str):
                is_public = is_public.lower() in ('true', '1', 'yes', 'on')
            update_data['is_public'] = bool(is_public)
        
        if not update_data:
            return jsonify({'success': False, 'message': 'No data to update'}), 400
        
        # Update the ingredient
        if update_data:
            set_parts = []
            params = []
            for key, value in update_data.items():
                set_parts.append(f"{key} = %s")
                params.append(value)
            
            set_clause = ", ".join(set_parts)
            params.append(ingredient_id)
            
            query = f"UPDATE user_personal_ingredients SET {set_clause}, updated_at = NOW() WHERE id = %s"
            success = db_client.execute_update(query, tuple(params))
        else:
            success = 0
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Ingredient updated successfully'
            })
        else:
            return jsonify({'success': False, 'message': 'Failed to update ingredient'}), 500
    
    except ValueError as e:
        return jsonify({'success': False, 'message': 'Invalid nutrition values. Please enter valid numbers.'}), 400
    except Exception as e:
        current_app.logger.error(f"Update personal ingredient error: {e}")
        return jsonify({'success': False, 'message': 'Failed to update ingredient'}), 500

@api_bp.route('/personal-ingredients/<int:ingredient_id>', methods=['DELETE'])
@login_required
def delete_personal_ingredient(ingredient_id):
    """Delete a personal ingredient."""
    try:
        db_client = get_db_client()
        
        # Verify ingredient belongs to user
        ingredient = db_client.fetch_one(
            "SELECT id FROM user_personal_ingredients WHERE id = %s AND user_id = %s",
            (ingredient_id, current_user.id)
        )
        
        if not ingredient:
            return jsonify({'success': False, 'message': 'Ingredient not found'}), 404
        
        # Delete the ingredient
        success = db_client.execute_delete(
            "DELETE FROM user_personal_ingredients WHERE id = %s", (ingredient_id,)
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Ingredient deleted successfully'
            })
        else:
            return jsonify({'success': False, 'message': 'Failed to delete ingredient'}), 500
    
    except Exception as e:
        current_app.logger.error(f"Delete personal ingredient error: {e}")
        return jsonify({'success': False, 'message': 'Failed to delete ingredient'}), 500

@api_bp.route('/personal-ingredients/<int:ingredient_id>', methods=['GET'])
@login_required
def get_personal_ingredient(ingredient_id):
    """Get a specific personal ingredient."""
    try:
        db_client = get_db_client()
        ingredient = db_client.fetch_one(
            "SELECT * FROM user_personal_ingredients WHERE id = %s AND user_id = %s",
            (ingredient_id, current_user.id)
        )
        
        if not ingredient:
            return jsonify({'success': False, 'message': 'Ingredient not found'}), 404
        
        return jsonify({
            'success': True,
            'ingredient': {
                'id': ingredient['id'],
                'name': ingredient['name'],
                'brand': ingredient.get('brand'),
                'description': ingredient.get('description'),
                'category': ingredient.get('category'),
                'calories_per_100g': float(ingredient.get('calories_per_100g') or 0),
                'protein_per_100g': float(ingredient.get('protein_per_100g') or 0),
                'carbs_per_100g': float(ingredient.get('carbs_per_100g') or 0),
                'fat_per_100g': float(ingredient.get('fat_per_100g') or 0),
                'is_public': bool(ingredient.get('is_public', False))
            }
        })
    
    except Exception as e:
        current_app.logger.error(f"Get personal ingredient error: {e}")
        return jsonify({'success': False, 'message': 'Failed to get ingredient'}), 500

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

# user_statistics() function removed - route exists but function is unused in templates