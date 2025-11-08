"""
Main application routes for homepage, dashboard, and general functionality.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import User, Recipe, Product, UserProductHistory, RecipeRating, UserSavedRecipe
from db_client import get_db_client

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """Homepage - shows app overview and featured content."""
    try:
        # Get some basic stats for homepage
        total_recipes = Recipe.count({'is_public': True, 'is_approved': True})
        total_products = Product.count()
        total_users = User.count()
        
        # Get some recent recipes (simplified)
        recent_recipes_data = Recipe.get_all(
            page=1, per_page=8,
            filters={'is_public': True, 'is_approved': True}
        )
        recent_recipes = recent_recipes_data['items']
        
        return render_template('index.html', 
                             total_recipes=total_recipes,
                             total_products=total_products,
                             total_users=total_users,
                             featured_recipes=[],  # Simplified for now
                             recent_recipes=recent_recipes)
    except Exception as e:
        print(f"Homepage error: {e}")
        # Fallback with basic info
        return render_template('index.html', 
                             total_recipes=0,
                             total_products=0,
                             total_users=0,
                             featured_recipes=[],
                             recent_recipes=[])

@main_bp.route('/dashboard')
@login_required
def dashboard():
    """User dashboard with personalized content and quick actions."""
    try:
        # Get user's created recipes
        user_recipes_data = Recipe.get_all(
            page=1, per_page=5,
            filters={'created_by_user_id': current_user.id}
        )
        user_recipes = user_recipes_data['items']
        
        # Simplified placeholders for features to be implemented
        recent_products = []  # UserProductHistory not fully implemented
        saved_recipes = []    # UserSavedRecipe not fully implemented
        today_calories = 0    # Placeholder for calorie tracking
        
        return render_template('dashboard.html',
                             recent_products=recent_products,
                             saved_recipes=saved_recipes,
                             user_recipes=user_recipes,
                             today_calories=today_calories,
                             calorie_goal=current_user.daily_calorie_goal or 2000)
    except Exception as e:
        print(f"Dashboard error: {e}")
        return render_template('dashboard.html',
                             recent_products=[],
                             saved_recipes=[],
                             user_recipes=[],
                             today_calories=0,
                             calorie_goal=2000)

@main_bp.route('/recipes')
def recipes():
    """Browse all public recipes with filtering and search."""
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 12))
        search = request.args.get('search', '').strip()
        category = request.args.get('category', '').strip()
        
        filters = {'is_public': True, 'is_approved': True}
        
        if category:
            filters['category'] = category
        
        if search:
            # Use search method for text queries
            recipes_data = Recipe.search(search, filters=filters, limit=per_page)
            # Convert to paginated format for template consistency
            recipes = {
                'items': recipes_data,
                'total': len(recipes_data),
                'page': 1,
                'per_page': per_page,
                'pages': 1
            }
        else:
            # Get paginated recipes
            recipes = Recipe.get_all(page=page, per_page=per_page, filters=filters)
        
        # Get categories for filter dropdown
        categories = Recipe.get_categories()
        
        return render_template('recipes.html',
                             recipes=recipes,
                             categories=categories,
                             current_search=search,
                             current_category=category,
                             current_page=page)
    except Exception as e:
        print(f"Recipes page error: {e}")
        import traceback
        traceback.print_exc()
        # Fallback with empty data
        return render_template('recipes.html',
                             recipes={'items': [], 'total': 0, 'page': 1, 'per_page': 12, 'pages': 0},
                             categories=[],
                             current_search='',
                             current_category='',
                             current_page=1)

@main_bp.route('/recipe/<int:recipe_id>')
def view_recipe(recipe_id):
    """View detailed recipe page."""
    try:
        recipe = Recipe.get(recipe_id)
        if not recipe:
            flash('Recipe not found.', 'error')
            return redirect(url_for('main.recipes'))
        
        # Check if recipe is viewable
        if not recipe.is_public or not recipe.is_approved:
            if not current_user.is_authenticated or (
                current_user.id != recipe.created_by_user_id
            ):
                flash('Recipe not found or not available.', 'error')
                return redirect(url_for('main.recipes'))
        
        # Simplified - these features not fully implemented yet
        is_saved = False
        user_rating = None
        recent_ratings = []
        
        return render_template('view_recipe.html',
                             recipe=recipe,
                             is_saved=is_saved,
                             user_rating=user_rating,
                             recent_ratings=recent_ratings)
    except Exception as e:
        print(f"View recipe error: {e}")
        flash('Error loading recipe.', 'error')
        return redirect(url_for('main.recipes'))

@main_bp.route('/recipes/add', methods=['GET', 'POST'])
@login_required
def add_recipe():
    """Add new recipe form."""
    if request.method == 'POST':
        # Get form data - Required fields
        name = request.form.get('name', '').strip()
        ingredients = request.form.get('ingredients', '').strip()
        instructions = request.form.get('instructions', '').strip()
        
        # Get form data - Optional fields
        description = request.form.get('description', '').strip()
        prep_time = request.form.get('prep_time', '')
        cook_time = request.form.get('cook_time', '')
        servings = request.form.get('servings', '')
        difficulty_level = request.form.get('difficulty_level', '')
        category = request.form.get('category', '')
        cuisine_type = request.form.get('cuisine_type', '')
        image_url = request.form.get('image_url', '').strip()
        video_url = request.form.get('video_url', '').strip()
        is_public = bool(request.form.get('is_public'))
        
        # Process dietary tags (multiple checkboxes)
        dietary_tags = request.form.getlist('dietary_tags')
        dietary_tags_json = dietary_tags if dietary_tags else None
        
        # Get nutrition data (optional)
        calories_per_serving = request.form.get('calories_per_serving', '').strip()
        protein_g = request.form.get('protein_g', '').strip()
        carbohydrates_g = request.form.get('carbohydrates_g', '').strip()
        fat_total_g = request.form.get('fat_total_g', '').strip()
        fiber_g = request.form.get('fiber_g', '').strip()
        sugars_g = request.form.get('sugars_g', '').strip()
        sodium_mg = request.form.get('sodium_mg', '').strip()
        
        # Calculate total time if both prep and cook times are provided
        total_time = None
        if prep_time and cook_time:
            try:
                total_time = int(prep_time) + int(cook_time)
            except ValueError:
                pass
        
        # Validate required fields
        if not name or not ingredients or not instructions:
            flash('Name, ingredients, and instructions are required.', 'error')
            return render_template('add_recipe.html')
        
        try:
            # Create the recipe with all available fields
            recipe = Recipe.create(
                name=name,
                created_by_user_id=current_user.id,
                description=description if description else None,
                ingredients=ingredients,
                instructions=instructions,
                prep_time_minutes=int(prep_time) if prep_time else None,
                cook_time_minutes=int(cook_time) if cook_time else None,
                total_time_minutes=total_time,
                servings=int(servings) if servings else 1,
                difficulty_level=difficulty_level if difficulty_level else None,
                category=category if category else None,
                cuisine_type=cuisine_type if cuisine_type else None,
                dietary_tags=dietary_tags_json,
                image_url=image_url if image_url else None,
                video_url=video_url if video_url else None,
                is_public=is_public
            )
            
            if recipe and recipe.id:
                # Create nutrition data if provided
                if calories_per_serving or protein_g or carbohydrates_g or fat_total_g or fiber_g or sugars_g or sodium_mg:
                    from db_client import get_db_client
                    db_client = get_db_client()
                    
                    nutrition_data = {
                        'recipe_id': recipe.id,
                        'is_calculated': False
                    }
                    if calories_per_serving:
                        nutrition_data['calories_per_serving'] = float(calories_per_serving)
                    if protein_g:
                        nutrition_data['protein_g'] = float(protein_g)
                    if carbohydrates_g:
                        nutrition_data['carbohydrates_g'] = float(carbohydrates_g)
                    if fat_total_g:
                        nutrition_data['fat_total_g'] = float(fat_total_g)
                    if fiber_g:
                        nutrition_data['fiber_g'] = float(fiber_g)
                    if sugars_g:
                        nutrition_data['sugars_g'] = float(sugars_g)
                    if sodium_mg:
                        nutrition_data['sodium_mg'] = float(sodium_mg)
                    
                    db_client.insert_record('recipe_nutrition', nutrition_data)
                
                flash('Recipe created successfully!', 'success')
                return redirect(url_for('main.view_recipe', recipe_id=recipe.id))
            else:
                flash('Failed to create recipe. Please try again.', 'error')
        
        except ValueError as e:
            flash('Please enter valid numbers for prep time, cook time, and servings.', 'error')
        except Exception as e:
            flash('An error occurred while creating the recipe.', 'error')
            print(f"Error creating recipe: {e}")
    
    return render_template('add_recipe.html')

@main_bp.route('/recipes/edit/<int:recipe_id>', methods=['GET', 'POST'])
@login_required
def edit_recipe(recipe_id):
    """Edit existing recipe form."""
    recipe = Recipe.get(recipe_id)
    if not recipe:
        flash('Recipe not found.', 'error')
        return redirect(url_for('main.recipes'))
    
    # Check if user can edit this recipe
    if recipe.created_by_user_id != current_user.id and not current_user.is_moderator():
        flash('You can only edit your own recipes.', 'error')
        return redirect(url_for('main.view_recipe', recipe_id=recipe_id))
    
    if request.method == 'POST':
        # Get form data
        name = request.form.get('name', '').strip()
        ingredients = request.form.get('ingredients', '').strip()
        instructions = request.form.get('instructions', '').strip()
        prep_time = request.form.get('prep_time', '')
        cook_time = request.form.get('cook_time', '')
        servings = request.form.get('servings', '')
        
        # Get nutrition data (optional)
        calories_per_serving = request.form.get('calories_per_serving', '').strip()
        protein_g = request.form.get('protein_g', '').strip()
        carbohydrates_g = request.form.get('carbohydrates_g', '').strip()
        fat_total_g = request.form.get('fat_total_g', '').strip()
        fiber_g = request.form.get('fiber_g', '').strip()
        sugars_g = request.form.get('sugars_g', '').strip()
        sodium_mg = request.form.get('sodium_mg', '').strip()
        
        # Validate required fields
        if not name or not ingredients or not instructions:
            flash('Name, ingredients, and instructions are required.', 'error')
            return render_template('edit_recipe.html', recipe=recipe)
        
        try:
            # Update the recipe
            update_data = {
                'name': name,
                'ingredients': ingredients,
                'instructions': instructions,
                'prep_time_minutes': int(prep_time) if prep_time else None,
                'cook_time_minutes': int(cook_time) if cook_time else None,
                'servings': int(servings) if servings else None
            }
            
            success = Recipe.update(recipe_id, update_data)
            
            # Update or create nutrition data if provided
            if success:
                from db_client import get_db_client
                db_client = get_db_client()
                
                # Check if nutrition data exists
                existing_nutrition = db_client.fetch_one(
                    "SELECT id FROM recipe_nutrition WHERE recipe_id = %s",
                    (recipe_id,)
                )
                
                # Prepare nutrition data
                nutrition_data = {}
                if calories_per_serving:
                    nutrition_data['calories_per_serving'] = float(calories_per_serving)
                if protein_g:
                    nutrition_data['protein_g'] = float(protein_g)
                if carbohydrates_g:
                    nutrition_data['carbohydrates_g'] = float(carbohydrates_g)
                if fat_total_g:
                    nutrition_data['fat_total_g'] = float(fat_total_g)
                if fiber_g:
                    nutrition_data['fiber_g'] = float(fiber_g)
                if sugars_g:
                    nutrition_data['sugars_g'] = float(sugars_g)
                if sodium_mg:
                    nutrition_data['sodium_mg'] = float(sodium_mg)
                
                # Update or insert nutrition data
                if nutrition_data:
                    if existing_nutrition:
                        # Update existing nutrition
                        db_client.update_record('recipe_nutrition', nutrition_data, {'recipe_id': recipe_id})
                    else:
                        # Create new nutrition record
                        nutrition_data['recipe_id'] = recipe_id
                        nutrition_data['is_calculated'] = False
                        db_client.insert_record('recipe_nutrition', nutrition_data)
                elif existing_nutrition:
                    # If no nutrition data provided but exists, we could delete it
                    # For now, we'll leave it as is
                    pass
                
                flash('Recipe updated successfully!', 'success')
                return redirect(url_for('main.view_recipe', recipe_id=recipe_id))
            else:
                flash('Failed to update recipe. Please try again.', 'error')
        
        except ValueError as e:
            flash('Please enter valid numbers for prep time, cook time, servings, and nutrition values.', 'error')
        except Exception as e:
            flash('An error occurred while updating the recipe.', 'error')
            print(f"Error updating recipe: {e}")
    
    return render_template('edit_recipe.html', recipe=recipe)

@main_bp.route('/recipes/delete/<int:recipe_id>', methods=['POST'])
@login_required
def delete_recipe(recipe_id):
    """Delete a recipe (AJAX endpoint)."""
    try:
        recipe = Recipe.get(recipe_id)
        if not recipe:
            return jsonify({'error': 'Recipe not found'}), 404
        
        # Check if user can delete this recipe
        if recipe.created_by_user_id != current_user.id and not current_user.is_moderator():
            return jsonify({'error': 'You can only delete your own recipes'}), 403
        
        # Delete the recipe
        success = Recipe.delete(recipe_id)
        if success:
            return jsonify({'success': True, 'message': 'Recipe deleted successfully'})
        else:
            return jsonify({'error': 'Failed to delete recipe'}), 500
    
    except Exception as e:
        print(f"Error deleting recipe: {e}")
        return jsonify({'error': 'An error occurred while deleting the recipe'}), 500

@main_bp.route('/barcode-scanner')
@login_required
def barcode_scanner():
    """Barcode scanner interface."""
    return render_template('barcode_scanner.html')

@main_bp.route('/nutrition-calculator')
@login_required
def nutrition_calculator():
    """Nutrition and serving size calculator."""
    return render_template('nutrition_calculator.html')

@main_bp.route('/my-ingredients')
@login_required
def my_ingredients():
    """User's personal ingredient list."""
    personal_ingredients = current_user.personal_ingredients
    return render_template('main/personal_ingredients.html', 
                         ingredients=personal_ingredients)

@main_bp.route('/search')
def search():
    """Global search functionality with tag-based searching."""
    query = request.args.get('q', '').strip()
    search_type = request.args.get('type', 'all')  # all, recipes, products
    include_all = request.args.get('include_all', 'false').lower() == 'true'  # Debug option
    
    results = {
        'recipes': [],
        'products': [],
        'query': query,
        'search_type': search_type,
        'total_results': 0
    }
    
    try:
        if query and len(query) >= 2:
            if search_type in ['all', 'recipes']:
                # Build filters - if include_all is True, don't filter by public/approved
                filters = None
                if not include_all:
                    # Try with filters first
                    filters = {'is_public': True, 'is_approved': True}
                
                # Search recipes using enhanced search method (includes tags, ingredients, etc.)
                recipe_results = Recipe.search(query, filters=filters, limit=50)
                results['recipes'] = recipe_results
                
                # If no results with filters, try without filters (for debugging)
                if not recipe_results and not include_all:
                    print(f"No results with filters, trying without filters...")
                    recipe_results_no_filter = Recipe.search(query, filters=None, limit=50)
                    if recipe_results_no_filter:
                        print(f"Found {len(recipe_results_no_filter)} recipes without filters")
                        results['recipes'] = recipe_results_no_filter
            
            if search_type in ['all', 'products']:
                # Search products using our raw SQL method
                product_results = Product.search(query)
                results['products'] = product_results[:20]  # Limit to 20
            
            results['total_results'] = len(results['recipes']) + len(results['products'])
    except Exception as e:
        print(f"Search error: {e}")
        import traceback
        traceback.print_exc()
        # Return empty results on error
    
    return render_template('search_results.html', **results)

@main_bp.route('/about')
def about():
    """About page with app information."""
    return render_template('main/about.html')

@main_bp.route('/terms')
def terms():
    """Terms of service page."""
    return render_template('main/terms.html')

@main_bp.route('/privacy')
def privacy():
    """Privacy policy page."""
    return render_template('main/privacy.html')