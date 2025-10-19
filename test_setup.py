from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import ForeignKey
import os

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Change this in production

# MySQL Database Configuration (XAMPP)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:@localhost:3306/caloriemate'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# User Model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)

class User_Personal_Recipes(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

class User_Saved_Recipes(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id'), nullable=False)

class User_Saved_Ingredients(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    ingredient_id = db.Column(db.Integer, db.ForeignKey('ingredient.id'), nullable=False)


class Ingredient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    is_Certified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp())

class Ingredient_Nutrition(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ingredient_id = db.Column(db.Integer, db.ForeignKey('ingredient.id'), nullable=False)
    calories = db.Column(db.Float, nullable=False)
    protein = db.Column(db.Float, nullable=False)
    carbs = db.Column(db.Float, nullable=False)
    fat = db.Column(db.Float, nullable=False)

class Recipe(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    ingredients = db.Column(db.String(200), nullable=False)
    instructions = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    ratings = db.relationship('RecipeRating', backref='recipe', lazy=True)

class Recipe_Ingredients(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id'), nullable=False)
    ingredient_id = db.Column(db.Integer, db.ForeignKey('ingredient.id'), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(20), nullable=False)

class Recipe_Instructions(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id'), nullable=False)
    step = db.Column(db.Integer, nullable=False)
    description = db.Column(db.String(200), nullable=False)

class Recipe_Nutrition(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id'), nullable=False)
    calories = db.Column(db.Float, nullable=False)
    protein = db.Column(db.Float, nullable=False)
    carbs = db.Column(db.Float, nullable=False)
    fat = db.Column(db.Float, nullable=False)

class RecipeRating(db.Model):
    recipe_id = db.Column(db.Integer, ForeignKey('recipe.id'), primary_key=True)
    user_id = db.Column(db.Integer, ForeignKey('user.id'), primary_key=True)
    rating = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())


# Routes
@app.route('/')
def index():
    total_recipes = Recipe.query.count()
    return render_template('index.html', total_recipes=total_recipes)

@app.route('/recipes')
def recipes():
    recipes = Recipe.query.order_by(Recipe.created_at.desc()).all()
    return render_template('recipes.html', recipes=recipes)

@app.route('/add_recipe', methods=['GET', 'POST'])
def add_recipe():
    if request.method == 'POST':
        name = request.form['name']
        ingredients = request.form['ingredients']
        instructions = request.form['instructions']
        
        if not name or not ingredients or not instructions:
            flash('All fields are required!', 'error')
            return render_template('add_recipe.html')
        
        recipe = Recipe(
            name=name,
            ingredients=ingredients,
            instructions=instructions
        )
        
        try:
            db.session.add(recipe)
            db.session.commit()
            flash('Recipe added successfully!', 'success')
            return redirect(url_for('view_recipe', id=recipe.id))
        except Exception as e:
            db.session.rollback()
            flash('Error adding recipe. Please try again.', 'error')
            return render_template('add_recipe.html')
    
    return render_template('add_recipe.html')

@app.route('/recipe/<int:id>')
def view_recipe(id):
    recipe = Recipe.query.get_or_404(id)
    return render_template('view_recipe.html', recipe=recipe)

@app.route('/edit_recipe/<int:id>', methods=['GET', 'POST'])
def edit_recipe(id):
    recipe = Recipe.query.get_or_404(id)
    
    if request.method == 'POST':
        recipe.name = request.form['name']
        recipe.ingredients = request.form['ingredients']
        recipe.instructions = request.form['instructions']
        
        if not recipe.name or not recipe.ingredients or not recipe.instructions:
            flash('All fields are required!', 'error')
            return render_template('edit_recipe.html', recipe=recipe)
        
        try:
            db.session.commit()
            flash('Recipe updated successfully!', 'success')
            return redirect(url_for('view_recipe', id=recipe.id))
        except Exception as e:
            db.session.rollback()
            flash('Error updating recipe. Please try again.', 'error')
            return render_template('edit_recipe.html', recipe=recipe)
    
    return render_template('edit_recipe.html', recipe=recipe)

@app.route('/delete_recipe/<int:id>')
def delete_recipe(id):
    recipe = Recipe.query.get_or_404(id)
    
    try:
        db.session.delete(recipe)
        db.session.commit()
        flash('Recipe deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error deleting recipe. Please try again.', 'error')
    
    return redirect(url_for('recipes'))

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

