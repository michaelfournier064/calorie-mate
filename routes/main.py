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
    # Get some stats for homepage
    total_recipes = Recipe.count({'is_public': True, 'is_approved': True})
    total_products = Product.count()
    total_users = User.count()
    
    # Get featured recipes
    featured_recipes_data = Recipe.get_all(
        page=1, per_page=6, 
        filters={'is_public': True, 'is_featured': True, 'is_approved': True}
    )
    featured_recipes = featured_recipes_data['items']
    
    # Get recently added recipes
    recent_recipes_data = Recipe.get_all(
        page=1, per_page=8,
        filters={'is_public': True, 'is_approved': True},
        order_by="created_at DESC"
    )
    recent_recipes = recent_recipes_data['items']
    
    return render_template('main/index.html', 
                         total_recipes=total_recipes,
                         total_products=total_products,
                         total_users=total_users,
                         featured_recipes=featured_recipes,
                         recent_recipes=recent_recipes)

@main_bp.route('/dashboard')
@login_required
def dashboard():
    """User dashboard with personalized content and quick actions."""
    # Get user's recent activity
    recent_scanned_products = UserProductHistory.get_by_user(
        current_user.id, 
        action_type='scanned', 
        limit=5, 
        order_by="timestamp DESC"
    )
    
    # Get user's saved recipes
    saved_recipes = UserSavedRecipe.get_saved_recipes_for_user(current_user.id, limit=8)
    
    # Get user's created recipes
    user_recipes_data = Recipe.get_all(
        page=1, per_page=5,
        filters={'created_by_user_id': current_user.id},
        order_by="created_at DESC"
    )
    user_recipes = user_recipes_data['items']
    
    # Get today's nutrition summary (if implemented)
    today_calories = 0  # Placeholder for calorie tracking
    
    return render_template('main/dashboard.html',
                         recent_products=recent_scanned_products,
                         saved_recipes=saved_recipes,
                         user_recipes=user_recipes,
                         today_calories=today_calories,
                         calorie_goal=current_user.daily_calorie_goal or 2000)

@main_bp.route('/recipes')
def recipes():
    """Browse all public recipes with filtering and search."""
    # Get query parameters
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    category = request.args.get('category', '')
    cuisine = request.args.get('cuisine', '')
    difficulty = request.args.get('difficulty', '')
    sort_by = request.args.get('sort', 'newest')  # newest, oldest, rating, popular
    
    # Build filters
    filters = {'is_public': True, 'is_approved': True}
    
    if category:
        filters['category'] = category
    
    if cuisine:
        filters['cuisine_type'] = cuisine
    
    if difficulty:
        filters['difficulty_level'] = difficulty
    
    # Set sort order
    order_by = "created_at DESC"  # default newest
    if sort_by == 'oldest':
        order_by = "created_at ASC"
    elif sort_by == 'rating':
        order_by = "rating DESC"  # Assuming average rating is calculated
    elif sort_by == 'popular':
        order_by = "saves_count DESC"  # Assuming saves count is tracked
    
    # Get recipes with search and filters
    if search:
        recipes_data = Recipe.search(search, page=page, per_page=12, filters=filters, order_by=order_by)
    else:
        recipes_data = Recipe.get_all(page=page, per_page=12, filters=filters, order_by=order_by)
    
    # Get filter options for dropdowns
    categories = Recipe.get_distinct_values('category', {'is_public': True, 'is_approved': True})
    cuisines = Recipe.get_distinct_values('cuisine_type', {'is_public': True, 'is_approved': True})
    difficulties = ['Easy', 'Medium', 'Hard']
    
    return render_template('main/recipes.html',
                         recipes=recipes_data,
                         search=search,
                         current_category=category,
                         current_cuisine=cuisine,
                         current_difficulty=difficulty,
                         current_sort=sort_by,
                         categories=categories,
                         cuisines=cuisines,
                         difficulties=difficulties)

@main_bp.route('/recipe/<int:recipe_id>')
def view_recipe(recipe_id):
    """View detailed recipe page."""
    recipe = Recipe.get(recipe_id)
    if not recipe:
        flash('Recipe not found.', 'error')
        return redirect(url_for('main.recipes'))
    
    # Check if recipe is viewable
    if not recipe.is_public or not recipe.is_approved:
        if not current_user.is_authenticated or (
            current_user.id != recipe.created_by_user_id and 
            not current_user.is_moderator()
        ):
            flash('Recipe not found or not available.', 'error')
            return redirect(url_for('main.recipes'))
    
    # Check if current user has saved this recipe
    is_saved = False
    user_rating = None
    if current_user.is_authenticated:
        is_saved = UserSavedRecipe.is_saved(current_user.id, recipe_id)
        
        # Get user's rating for this recipe
        user_rating = RecipeRating.get_by_user_and_recipe(current_user.id, recipe_id)
    
    # Get recent ratings/reviews
    recent_ratings = RecipeRating.get_for_recipe(recipe_id, approved_only=True, limit=10)
    
    return render_template('main/recipe_detail.html',
                         recipe=recipe,
                         is_saved=is_saved,
                         user_rating=user_rating,
                         recent_ratings=recent_ratings)

@main_bp.route('/barcode-scanner')
@login_required
def barcode_scanner():
    """Barcode scanner interface."""
    return render_template('main/barcode_scanner.html')

@main_bp.route('/nutrition-calculator')
@login_required
def nutrition_calculator():
    """Nutrition and serving size calculator."""
    return render_template('main/nutrition_calculator.html')

@main_bp.route('/my-ingredients')
@login_required
def my_ingredients():
    """User's personal ingredient list."""
    personal_ingredients = current_user.personal_ingredients
    return render_template('main/personal_ingredients.html', 
                         ingredients=personal_ingredients)

@main_bp.route('/search')
def search():
    """Global search functionality."""
    query = request.args.get('q', '').strip()
    search_type = request.args.get('type', 'all')  # all, recipes, products
    
    results = {
        'recipes': [],
        'products': [],
        'query': query
    }
    
    if query and len(query) >= 2:
        if search_type in ['all', 'recipes']:
            # Search recipes
            recipe_results = Recipe.query.filter(
                Recipe.is_public==True,
                Recipe.is_approved==True,
                Recipe.name.contains(query)
            ).limit(20).all()
            results['recipes'] = recipe_results
        
        if search_type in ['all', 'products']:
            # Search products
            product_results = Product.query.filter(
                Product.name.contains(query)
            ).limit(20).all()
            results['products'] = product_results
    
    return render_template('main/search_results.html', **results)

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