"""
Administrative routes for user management, content moderation, and system administration.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from functools import wraps
from models import (User, Recipe, Product, RecipeRating, ReportedContent, 
                   AdminAction, SponsoredContent, UserRole, ContentType)
from db_client import get_db_client

admin_bp = Blueprint('admin', __name__)

def admin_required(f):
    """Decorator to require admin privileges."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            flash('Admin access required.', 'error')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

def moderator_required(f):
    """Decorator to require moderator or admin privileges."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_moderator():
            flash('Moderator access required.', 'error')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/')
@admin_required
def dashboard():
    """Admin dashboard with system overview."""
    # Get system statistics
    stats = {
        'total_users': User.count(),
        'active_users': User.count({'is_active': True}),
        'total_recipes': Recipe.count(),
        'pending_recipes': Recipe.count({'is_approved': False}),
        'total_products': Product.count(),
        'unverified_products': Product.count({'is_verified': False}),
        'pending_reports': ReportedContent.count({'status': 'pending'}),
        'total_ratings': RecipeRating.count()
    }
    
    # Get recent activity
    recent_users_data = User.get_all(page=1, per_page=5, order_by="created_at DESC")
    recent_users = recent_users_data['items']
    
    recent_recipes_data = Recipe.get_all(page=1, per_page=5, order_by="created_at DESC")
    recent_recipes = recent_recipes_data['items']
    
    recent_reports = ReportedContent.get_by_status('pending', limit=5, order_by="created_at DESC")
    
    return render_template('admin/dashboard.html',
                         stats=stats,
                         recent_users=recent_users,
                         recent_recipes=recent_recipes,
                         recent_reports=recent_reports)

@admin_bp.route('/users')
@admin_required
def manage_users():
    """User management interface."""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    role_filter = request.args.get('role', '')
    status_filter = request.args.get('status', '')
    
    # Build query
    query = User.query
    
    if search:
        query = query.filter(or_(
            User.username.contains(search),
            User.email.contains(search),
            User.first_name.contains(search),
            User.last_name.contains(search)
        ))
    
    if role_filter:
        query = query.filter_by(role=UserRole(role_filter))
    
    if status_filter == 'active':
        query = query.filter_by(is_active=True)
    elif status_filter == 'inactive':
        query = query.filter_by(is_active=False)
    
    users = query.order_by(desc(User.created_at)).paginate(
        page=page, per_page=20, error_out=False
    )
    
    return render_template('admin/users.html',
                         users=users,
                         search=search,
                         role_filter=role_filter,
                         status_filter=status_filter)

@admin_bp.route('/user/<int:user_id>/suspend', methods=['POST'])
@admin_required
def suspend_user(user_id):
    """Suspend a user account."""
    user = User.query.get_or_404(user_id)
    
    if user.id == current_user.id:
        flash('You cannot suspend your own account.', 'error')
        return redirect(url_for('admin.manage_users'))
    
    reason = request.form.get('reason', '').strip()
    
    try:
        user.is_active = False
        
        # Log admin action
        action = AdminAction(
            admin_user_id=current_user.id,
            action_type='user_suspended',
            target_type='user',
            target_id=user.id,
            description=f"User suspended. Reason: {reason}" if reason else "User suspended"
        )
        db.session.add(action)
        db.session.commit()
        
        flash(f'User {user.username} has been suspended.', 'success')
    
    except Exception as e:
        db.session.rollback()
        flash('Failed to suspend user.', 'error')
    
    return redirect(url_for('admin.manage_users'))

@admin_bp.route('/user/<int:user_id>/activate', methods=['POST'])
@admin_required
def activate_user(user_id):
    """Reactivate a suspended user account."""
    user = User.query.get_or_404(user_id)
    
    try:
        user.is_active = True
        
        # Log admin action
        action = AdminAction(
            admin_user_id=current_user.id,
            action_type='user_activated',
            target_type='user',
            target_id=user.id,
            description="User account reactivated"
        )
        db.session.add(action)
        db.session.commit()
        
        flash(f'User {user.username} has been reactivated.', 'success')
    
    except Exception as e:
        db.session.rollback()
        flash('Failed to reactivate user.', 'error')
    
    return redirect(url_for('admin.manage_users'))

@admin_bp.route('/recipes')
@moderator_required
def manage_recipes():
    """Recipe management and moderation."""
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', 'pending')
    
    query = Recipe.query
    
    if status_filter == 'pending':
        query = query.filter_by(is_approved=False)
    elif status_filter == 'approved':
        query = query.filter_by(is_approved=True)
    elif status_filter == 'featured':
        query = query.filter_by(is_featured=True)
    
    recipes = query.order_by(desc(Recipe.created_at)).paginate(
        page=page, per_page=20, error_out=False
    )
    
    return render_template('admin/recipes.html',
                         recipes=recipes,
                         status_filter=status_filter)

@admin_bp.route('/recipe/<int:recipe_id>/approve', methods=['POST'])
@moderator_required
def approve_recipe(recipe_id):
    """Approve a recipe for public display."""
    recipe = Recipe.query.get_or_404(recipe_id)
    
    try:
        recipe.is_approved = True
        
        # Log admin action
        action = AdminAction(
            admin_user_id=current_user.id,
            action_type='recipe_approved',
            target_type='recipe',
            target_id=recipe.id,
            description=f"Recipe '{recipe.name}' approved for public display"
        )
        db.session.add(action)
        db.session.commit()
        
        flash(f'Recipe "{recipe.name}" has been approved.', 'success')
    
    except Exception as e:
        db.session.rollback()
        flash('Failed to approve recipe.', 'error')
    
    return redirect(url_for('admin.manage_recipes'))

@admin_bp.route('/recipe/<int:recipe_id>/feature', methods=['POST'])
@admin_required
def feature_recipe(recipe_id):
    """Feature a recipe on the homepage."""
    recipe = Recipe.query.get_or_404(recipe_id)
    
    try:
        recipe.is_featured = not recipe.is_featured
        action_type = 'recipe_featured' if recipe.is_featured else 'recipe_unfeatured'
        
        # Log admin action
        action = AdminAction(
            admin_user_id=current_user.id,
            action_type=action_type,
            target_type='recipe',
            target_id=recipe.id,
            description=f"Recipe '{recipe.name}' {'featured' if recipe.is_featured else 'unfeatured'}"
        )
        db.session.add(action)
        db.session.commit()
        
        status = 'featured' if recipe.is_featured else 'unfeatured'
        flash(f'Recipe "{recipe.name}" has been {status}.', 'success')
    
    except Exception as e:
        db.session.rollback()
        flash('Failed to update recipe feature status.', 'error')
    
    return redirect(url_for('admin.manage_recipes'))

@admin_bp.route('/products')
@admin_required
def manage_products():
    """Product database management."""
    page = request.args.get('page', 1, type=int)
    verification_filter = request.args.get('verification', 'unverified')
    
    query = Product.query
    
    if verification_filter == 'unverified':
        query = query.filter_by(is_verified=False)
    elif verification_filter == 'verified':
        query = query.filter_by(is_verified=True)
    
    products = query.order_by(desc(Product.created_at)).paginate(
        page=page, per_page=20, error_out=False
    )
    
    return render_template('admin/products.html',
                         products=products,
                         verification_filter=verification_filter)

@admin_bp.route('/product/<int:product_id>/verify', methods=['POST'])
@admin_required
def verify_product(product_id):
    """Verify a product's information as accurate."""
    product = Product.query.get_or_404(product_id)
    
    try:
        product.is_verified = True
        product.verified_by_user_id = current_user.id
        product.verification_date = func.now()
        
        # Log admin action
        action = AdminAction(
            admin_user_id=current_user.id,
            action_type='product_verified',
            target_type='product',
            target_id=product.id,
            description=f"Product '{product.name}' verified"
        )
        db.session.add(action)
        db.session.commit()
        
        flash(f'Product "{product.name}" has been verified.', 'success')
    
    except Exception as e:
        db.session.rollback()
        flash('Failed to verify product.', 'error')
    
    return redirect(url_for('admin.manage_products'))

@admin_bp.route('/reports')
@moderator_required
def manage_reports():
    """Content moderation - handle user reports."""
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', 'pending')
    
    query = ReportedContent.query
    
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    
    reports = query.order_by(desc(ReportedContent.created_at)).paginate(
        page=page, per_page=20, error_out=False
    )
    
    return render_template('admin/reports.html',
                         reports=reports,
                         status_filter=status_filter)

@admin_bp.route('/report/<int:report_id>/resolve', methods=['POST'])
@moderator_required
def resolve_report(report_id):
    """Resolve a user report."""
    report = ReportedContent.query.get_or_404(report_id)
    
    action = request.form.get('action')  # 'dismiss', 'remove_content', 'warn_user'
    notes = request.form.get('notes', '').strip()
    
    try:
        report.status = 'resolved'
        report.reviewed_by_user_id = current_user.id
        report.resolved_at = func.now()
        report.resolution_notes = notes
        
        # Take action based on resolution
        if action == 'remove_content':
            if report.content_type == ContentType.RECIPE:
                recipe = Recipe.query.get(report.content_id)
                if recipe:
                    recipe.is_approved = False
                    db.session.add(AdminAction(
                        admin_user_id=current_user.id,
                        action_type='content_removed',
                        target_type='recipe',
                        target_id=recipe.id,
                        description=f"Recipe removed due to report: {report.reason}"
                    ))
            
            elif report.content_type == ContentType.REVIEW:
                rating = RecipeRating.query.get(report.content_id)
                if rating:
                    rating.is_approved = False
        
        db.session.commit()
        flash(f'Report has been resolved with action: {action}', 'success')
    
    except Exception as e:
        db.session.rollback()
        flash('Failed to resolve report.', 'error')
    
    return redirect(url_for('admin.manage_reports'))

@admin_bp.route('/sponsored-content')
@admin_required
def manage_sponsored_content():
    """Manage sponsored, influencer, and recommended content."""
    page = request.args.get('page', 1, type=int)
    
    sponsored_content = SponsoredContent.query.order_by(
        desc(SponsoredContent.created_at)
    ).paginate(page=page, per_page=20, error_out=False)
    
    return render_template('admin/sponsored_content.html',
                         sponsored_content=sponsored_content)

@admin_bp.route('/sponsored-content/add', methods=['GET', 'POST'])
@admin_required
def add_sponsored_content():
    """Add new sponsored content."""
    if request.method == 'POST':
        recipe_id = request.form.get('recipe_id')
        content_type = request.form.get('content_type')
        sponsor_name = request.form.get('sponsor_name', '').strip()
        campaign_name = request.form.get('campaign_name', '').strip()
        priority_score = request.form.get('priority_score', 1, type=int)
        
        try:
            from models import SponsorshipType
            
            sponsored = SponsoredContent(
                recipe_id=recipe_id,
                content_type=SponsorshipType(content_type),
                sponsor_name=sponsor_name if sponsor_name else None,
                campaign_name=campaign_name if campaign_name else None,
                priority_score=priority_score
            )
            
            db.session.add(sponsored)
            db.session.commit()
            
            flash('Sponsored content added successfully.', 'success')
            return redirect(url_for('admin.manage_sponsored_content'))
        
        except Exception as e:
            db.session.rollback()
            flash('Failed to add sponsored content.', 'error')
    
    # Get recipes for dropdown
    recipes = Recipe.query.filter_by(is_public=True, is_approved=True).all()
    return render_template('admin/add_sponsored_content.html', recipes=recipes)

@admin_bp.route('/analytics')
@admin_required
def analytics():
    """System analytics and reporting."""
    # User analytics
    user_stats = {
        'total_users': User.query.count(),
        'users_this_month': User.query.filter(
            User.created_at >= func.date_trunc('month', func.now())
        ).count(),
        'active_users': User.query.filter_by(is_active=True).count()
    }
    
    # Recipe analytics
    recipe_stats = {
        'total_recipes': Recipe.query.count(),
        'public_recipes': Recipe.query.filter_by(is_public=True).count(),
        'featured_recipes': Recipe.query.filter_by(is_featured=True).count()
    }
    
    # Product analytics
    product_stats = {
        'total_products': Product.query.count(),
        'verified_products': Product.query.filter_by(is_verified=True).count()
    }
    
    return render_template('admin/analytics.html',
                         user_stats=user_stats,
                         recipe_stats=recipe_stats,
                         product_stats=product_stats)