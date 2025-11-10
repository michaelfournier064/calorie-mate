-- CalorieMate Database Schema
-- Complete MySQL schema to replace SQLAlchemy ORM models

-- Users table with authentication and profile
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(80) NOT NULL UNIQUE,
    email VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(50),
    last_name VARCHAR(50),
    
    -- User preferences and profile
    role ENUM('user', 'moderator', 'admin') NOT NULL DEFAULT 'user',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    email_verified BOOLEAN NOT NULL DEFAULT FALSE,
    profile_picture_url VARCHAR(255),
    bio TEXT,
    
    -- Nutritional preferences
    daily_calorie_goal DECIMAL(8,2),
    dietary_restrictions JSON,
    
    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_login TIMESTAMP NULL,
    
    -- Indexes
    INDEX idx_username (username),
    INDEX idx_email (email),
    INDEX idx_role (role),
    INDEX idx_is_active (is_active)
);

-- Products table for barcode scanning
CREATE TABLE IF NOT EXISTS products (
    id INT AUTO_INCREMENT PRIMARY KEY,
    barcode VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(200) NOT NULL,
    brand VARCHAR(100),
    description TEXT,
    category VARCHAR(100),
    image_url VARCHAR(255),
    
    -- Product validation and verification
    is_verified BOOLEAN NOT NULL DEFAULT FALSE,
    verified_by_user_id INT,
    verification_date TIMESTAMP NULL,
    
    -- Serving size information
    serving_size DECIMAL(8,2),
    serving_size_unit VARCHAR(20) NOT NULL DEFAULT 'g',
    servings_per_container DECIMAL(8,2),
    
    -- Timestamps and tracking
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_by_user_id INT,
    
    -- Foreign keys
    FOREIGN KEY (verified_by_user_id) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (created_by_user_id) REFERENCES users(id) ON DELETE SET NULL,
    
    -- Indexes
    INDEX idx_barcode (barcode),
    INDEX idx_name (name),
    INDEX idx_category (category),
    INDEX idx_is_verified (is_verified)
);

-- Product nutrition information
CREATE TABLE IF NOT EXISTS product_nutrition (
    id INT AUTO_INCREMENT PRIMARY KEY,
    product_id INT NOT NULL UNIQUE,
    
    -- Basic macronutrients (per serving)
    calories DECIMAL(8,2),
    protein_g DECIMAL(8,2),
    carbohydrates_g DECIMAL(8,2),
    fiber_g DECIMAL(8,2),
    sugars_g DECIMAL(8,2),
    fat_total_g DECIMAL(8,2),
    fat_saturated_g DECIMAL(8,2),
    fat_trans_g DECIMAL(8,2),
    
    -- Micronutrients
    sodium_mg DECIMAL(8,2),
    potassium_mg DECIMAL(8,2),
    cholesterol_mg DECIMAL(8,2),
    
    -- Vitamins (% daily value)
    vitamin_a_percent DECIMAL(5,2),
    vitamin_c_percent DECIMAL(5,2),
    calcium_percent DECIMAL(5,2),
    iron_percent DECIMAL(5,2),
    
    -- Additional nutrition data as JSON
    additional_nutrients JSON,
    
    -- Data validation and sources
    is_estimated BOOLEAN NOT NULL DEFAULT FALSE,
    data_source VARCHAR(100),
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    -- Foreign keys
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
);

-- Recipes table
CREATE TABLE IF NOT EXISTS recipes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    ingredients TEXT,
    instructions TEXT,
    prep_time_minutes INT,
    cook_time_minutes INT,
    total_time_minutes INT,
    servings INT NOT NULL DEFAULT 1,
    difficulty_level VARCHAR(20),
    
    -- Recipe categorization
    category VARCHAR(100),
    cuisine_type VARCHAR(100),
    dietary_tags JSON,
    
    -- Content and media
    image_url VARCHAR(255),
    video_url VARCHAR(255),
    
    -- Community and moderation
    is_public BOOLEAN NOT NULL DEFAULT TRUE,
    is_featured BOOLEAN NOT NULL DEFAULT FALSE,
    is_approved BOOLEAN NOT NULL DEFAULT TRUE,
    
    -- Ownership and timestamps
    created_by_user_id INT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    -- Foreign keys
    FOREIGN KEY (created_by_user_id) REFERENCES users(id) ON DELETE CASCADE,
    
    -- Indexes
    INDEX idx_name (name),
    INDEX idx_category (category),
    INDEX idx_cuisine_type (cuisine_type),
    INDEX idx_difficulty_level (difficulty_level),
    INDEX idx_is_public (is_public),
    INDEX idx_is_featured (is_featured),
    INDEX idx_is_approved (is_approved),
    INDEX idx_created_by_user_id (created_by_user_id),
    INDEX idx_created_at (created_at)
);

-- Recipe ingredients
CREATE TABLE IF NOT EXISTS recipe_ingredients (
    id INT AUTO_INCREMENT PRIMARY KEY,
    recipe_id INT NOT NULL,
    
    -- Ingredient information
    ingredient_name VARCHAR(200) NOT NULL,
    quantity DECIMAL(8,2) NOT NULL,
    unit VARCHAR(50) NOT NULL,
    preparation_note VARCHAR(200),
    
    -- Optional link to product database
    product_id INT,
    
    -- Order for display
    order_index INT NOT NULL DEFAULT 0,
    
    -- Foreign keys
    FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL,
    
    -- Indexes
    INDEX idx_recipe_id (recipe_id),
    INDEX idx_product_id (product_id),
    INDEX idx_order (recipe_id, order_index)
);

-- Recipe instructions
CREATE TABLE IF NOT EXISTS recipe_instructions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    recipe_id INT NOT NULL,
    step_number INT NOT NULL,
    instruction TEXT NOT NULL,
    time_minutes INT,
    temperature VARCHAR(20),
    
    -- Foreign keys
    FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE,
    
    -- Indexes
    INDEX idx_recipe_id (recipe_id),
    INDEX idx_step (recipe_id, step_number)
);

-- Recipe nutrition
CREATE TABLE IF NOT EXISTS recipe_nutrition (
    id INT AUTO_INCREMENT PRIMARY KEY,
    recipe_id INT NOT NULL UNIQUE,
    
    -- Nutrition per serving
    calories_per_serving DECIMAL(8,2),
    protein_g DECIMAL(8,2),
    carbohydrates_g DECIMAL(8,2),
    fiber_g DECIMAL(8,2),
    sugars_g DECIMAL(8,2),
    fat_total_g DECIMAL(8,2),
    fat_saturated_g DECIMAL(8,2),
    sodium_mg DECIMAL(8,2),
    
    -- Calculation metadata
    is_calculated BOOLEAN NOT NULL DEFAULT FALSE,
    calculation_date TIMESTAMP NULL,
    calculation_accuracy DECIMAL(3,2),
    
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    -- Foreign keys
    FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE
);

-- Recipe ratings and reviews
CREATE TABLE IF NOT EXISTS recipe_ratings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    recipe_id INT NOT NULL,
    user_id INT NOT NULL,
    
    rating INT NOT NULL,
    review_text TEXT,
    would_make_again BOOLEAN,
    
    -- Moderation
    is_approved BOOLEAN NOT NULL DEFAULT TRUE,
    flagged_count INT NOT NULL DEFAULT 0,
    
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    -- Foreign keys
    FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    
    -- Unique constraint
    UNIQUE KEY unique_user_recipe_rating (recipe_id, user_id),
    
    -- Indexes
    INDEX idx_recipe_id (recipe_id),
    INDEX idx_user_id (user_id),
    INDEX idx_rating (rating),
    INDEX idx_is_approved (is_approved)
);

-- User saved recipes
CREATE TABLE IF NOT EXISTS user_saved_recipes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    recipe_id INT NOT NULL,
    notes TEXT,
    
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign keys
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE,
    
    -- Unique constraint
    UNIQUE KEY unique_user_saved_recipe (user_id, recipe_id),
    
    -- Indexes
    INDEX idx_user_id (user_id),
    INDEX idx_recipe_id (recipe_id)
);

-- User personal ingredients
CREATE TABLE IF NOT EXISTS user_personal_ingredients (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    
    -- Ingredient details
    name VARCHAR(200) NOT NULL,
    brand VARCHAR(100),
    description TEXT,
    category VARCHAR(100),
    
    -- Nutrition per 100g
    calories_per_100g DECIMAL(8,2),
    protein_per_100g DECIMAL(8,2),
    carbs_per_100g DECIMAL(8,2),
    fat_per_100g DECIMAL(8,2),
    
    -- Public accessibility
    is_public BOOLEAN NOT NULL DEFAULT FALSE,
    
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    -- Foreign keys
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    
    -- Indexes
    INDEX idx_user_id (user_id),
    INDEX idx_name (name),
    INDEX idx_category (category)
);

-- User product history
CREATE TABLE IF NOT EXISTS user_product_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    product_id INT NOT NULL,
    
    action_type VARCHAR(50) NOT NULL,
    quantity_consumed DECIMAL(8,2),
    serving_size_consumed DECIMAL(8,2),
    
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign keys
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
    
    -- Indexes
    INDEX idx_user_id (user_id),
    INDEX idx_product_id (product_id),
    INDEX idx_action_type (action_type),
    INDEX idx_timestamp (timestamp)
);

-- Admin actions log
CREATE TABLE IF NOT EXISTS admin_actions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    admin_user_id INT NOT NULL,
    
    action_type VARCHAR(100) NOT NULL,
    target_type VARCHAR(50) NOT NULL,
    target_id INT NOT NULL,
    
    description TEXT,
    metadata_json JSON,
    
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign keys
    FOREIGN KEY (admin_user_id) REFERENCES users(id) ON DELETE CASCADE,
    
    -- Indexes
    INDEX idx_admin_user_id (admin_user_id),
    INDEX idx_action_type (action_type),
    INDEX idx_target_type (target_type),
    INDEX idx_timestamp (timestamp)
);

-- Reported content
CREATE TABLE IF NOT EXISTS reported_content (
    id INT AUTO_INCREMENT PRIMARY KEY,
    reporter_user_id INT NOT NULL,
    
    content_type ENUM('recipe', 'review', 'product', 'user_profile') NOT NULL,
    content_id INT NOT NULL,
    
    reason VARCHAR(100) NOT NULL,
    description TEXT,
    
    -- Moderation status
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    reviewed_by_user_id INT,
    resolution_notes TEXT,
    
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP NULL,
    
    -- Foreign keys
    FOREIGN KEY (reporter_user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (reviewed_by_user_id) REFERENCES users(id) ON DELETE SET NULL,
    
    -- Indexes
    INDEX idx_reporter_user_id (reporter_user_id),
    INDEX idx_content_type (content_type),
    INDEX idx_status (status),
    INDEX idx_reviewed_by_user_id (reviewed_by_user_id),
    INDEX idx_created_at (created_at)
);

-- Sponsored content
CREATE TABLE IF NOT EXISTS sponsored_content (
    id INT AUTO_INCREMENT PRIMARY KEY,
    recipe_id INT NOT NULL,
    
    content_type ENUM('sponsored', 'influencer', 'recommended') NOT NULL,
    sponsor_name VARCHAR(200),
    sponsor_logo_url VARCHAR(255),
    
    -- Campaign details
    campaign_name VARCHAR(200),
    priority_score INT NOT NULL DEFAULT 1,
    
    -- Display settings
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    start_date TIMESTAMP NULL,
    end_date TIMESTAMP NULL,
    
    -- Analytics
    view_count INT NOT NULL DEFAULT 0,
    click_count INT NOT NULL DEFAULT 0,
    
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    -- Foreign keys
    FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE,
    
    -- Indexes
    INDEX idx_recipe_id (recipe_id),
    INDEX idx_content_type (content_type),
    INDEX idx_is_active (is_active),
    INDEX idx_priority_score (priority_score),
    INDEX idx_start_date (start_date),
    INDEX idx_end_date (end_date)
);
