"""
Authentication routes for user registration, login, logout, and profile management.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from models import User
import re

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """User registration page."""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        
        # Validation
        errors = []
        
        if not username or len(username) < 3:
            errors.append('Username must be at least 3 characters long.')
        
        if not email or not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email):
            errors.append('Please enter a valid email address.')
        
        if not password or len(password) < 8:
            errors.append('Password must be at least 8 characters long.')
        
        if password != confirm_password:
            errors.append('Passwords do not match.')
        
        # Check if username or email already exists
        if User.get_by_username(username):
            errors.append('Username already exists.')
        
        if User.get_by_email(email):
            errors.append('Email already registered.')
        
        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('auth/register.html')
        
        # Create new user
        try:
            user = User.create(
                username=username,
                email=email,
                password=password,
                first_name=first_name if first_name else None,
                last_name=last_name if last_name else None
            )
            
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('auth.login'))
        
        except ValueError as e:
            flash(str(e), 'error')
            return render_template('auth/register.html')
        except Exception as e:
            flash('Registration failed. Please try again.', 'error')
            return render_template('auth/register.html')
    
    return render_template('auth/register.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login page."""
    if request.method == 'POST':
        username_or_email = request.form.get('username_or_email', '').strip()
        password = request.form.get('password', '')
        remember_me = bool(request.form.get('remember_me'))
        
        if not username_or_email or not password:
            flash('Please enter both username/email and password.', 'error')
            return render_template('auth/login.html')
        
        # Find user by username or email
        user = User.get_by_username_or_email(username_or_email)
        
        if user and user.check_password(password):
            if not user.is_active:
                flash('Your account has been suspended. Please contact support.', 'error')
                return render_template('auth/login.html')
            
            # Update last login
            user.update_last_login()
            
            login_user(user, remember=remember_me)
            
            # Redirect to next page or dashboard
            next_page = request.args.get('next')
            if next_page and next_page.startswith('/'):
                return redirect(next_page)
            
            flash(f'Welcome back, {user.first_name or user.username}!', 'success')
            return redirect(url_for('main.dashboard'))
        
        flash('Invalid username/email or password.', 'error')
    
    return render_template('auth/login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    """User logout."""
    logout_user()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('main.index'))

@auth_bp.route('/profile')
@login_required
def profile():
    """User profile page."""
    return render_template('auth/profile.html', user=current_user)

@auth_bp.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    """Edit user profile."""
    if request.method == 'POST':
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        bio = request.form.get('bio', '').strip()
        daily_calorie_goal = request.form.get('daily_calorie_goal')
        
        try:
            current_user.first_name = first_name if first_name else None
            current_user.last_name = last_name if last_name else None
            current_user.bio = bio if bio else None
            
            if daily_calorie_goal:
                try:
                    current_user.daily_calorie_goal = float(daily_calorie_goal)
                except ValueError:
                    flash('Invalid calorie goal. Please enter a number.', 'error')
                    return render_template('auth/edit_profile.html', user=current_user)
            
            current_user.save()
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('auth.profile'))
        
        except Exception as e:
            flash('Failed to update profile. Please try again.', 'error')
    
    return render_template('auth/edit_profile.html', user=current_user)

@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Change user password."""
    if request.method == 'POST':
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        # Validation
        if not current_password or not new_password or not confirm_password:
            flash('All fields are required.', 'error')
            return render_template('auth/change_password.html')
        
        if not current_user.check_password(current_password):
            flash('Current password is incorrect.', 'error')
            return render_template('auth/change_password.html')
        
        if len(new_password) < 8:
            flash('New password must be at least 8 characters long.', 'error')
            return render_template('auth/change_password.html')
        
        if new_password != confirm_password:
            flash('New passwords do not match.', 'error')
            return render_template('auth/change_password.html')
        
        try:
            current_user.set_password(new_password)
            current_user.save()
            flash('Password changed successfully!', 'success')
            return redirect(url_for('auth.profile'))
        
        except Exception as e:
            flash('Failed to change password. Please try again.', 'error')
    
    return render_template('auth/change_password.html')