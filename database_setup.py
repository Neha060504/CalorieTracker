"""
File: database_setup.py - Database Initialization and Migration Routine

WHAT IT DOES:
- Connects to the MariaDB/MySQL server instance.
- Automatically creates the 'calorieapp' database schema if not present using UTF8MB4 encoding.
- Defines and verifies core tables:
  1. 'users': stores authentication credentials, dietary profiles, health metrics, and Gemini API keys.
  2. 'meals': logs consumed dishes, portion quantities, timestamps, and calorie counts.
  3. 'water_intake': records hydration logs (amount in ml) with hourly and daily timestamps.
  4. 'activities': tracks exercise and physical workouts with duration and calories burned.
  5. 'recipe_history': archives AI-generated custom recipes for future user reference.
  6. 'coach_history': saves personalized AI coach consultation chats and dietary insights.

WHY IT IS USED:
- Ensures database reliability, prevents schema-drift runtime crashes, and automates fresh environment setup.
"""

import os
from dotenv import load_dotenv
import mysql.connector
from mysql.connector import Error

load_dotenv()

def setup_database():
    """
    Final consolidated database setup script for MyFitness Buddy.
    Creates the database (if not exists) and all required tables with relationships
    and standard character sets for modern data compatibility.
    """
    db_host = os.environ.get('DB_HOST', '127.0.0.1')
    db_port = int(os.environ.get('DB_PORT', 3308))
    db_user = os.environ.get('DB_USER', 'root')
    db_password = os.environ.get('DB_PASSWORD', 'Shriyash@11')
    db_name = os.environ.get('DB_NAME', 'calorieapp')

    try:
        # Initial connection to create the DB if missing
        connection = mysql.connector.connect(
            host=db_host,
            port=db_port,
            user=db_user,
            password=db_password
        )
        
        if connection.is_connected():
            cursor = connection.cursor()
            
            # Create Database with UTF-8 character encoding (modern standard)
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            cursor.execute(f"USE `{db_name}`")
            
            # 1. Users Table
            # Stores authentication, profile settings, and API configuration.
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(50) UNIQUE NOT NULL,
                    password VARCHAR(255) NOT NULL,
                    email VARCHAR(100),
                    target_calories INT DEFAULT 2000,
                    gemini_api_key VARCHAR(255),
                    allergies TEXT,
                    favorite_foods TEXT,
                    diseases TEXT,
                    health_issues TEXT,
                    disability TEXT
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            
            # 2. Meals Table
            # ON DELETE CASCADE ensures if a user is deleted, their meals are also cleaned up.
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS meals (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT,
                    meal_name VARCHAR(100),
                    meal_type ENUM('Breakfast', 'Lunch', 'Dinner', 'Snack', 'Other') DEFAULT 'Other',
                    calories INT,
                    date DATE DEFAULT (CURRENT_DATE),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            
            # 3. Water Intake Table
            # Includes precision timestamp for hourly behavioral analytics.
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS water_intake (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT,
                    amount_ml INT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    date DATE DEFAULT (CURRENT_DATE),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            
            # 4. Activities Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS activities (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT,
                    activity_name VARCHAR(100),
                    calories_burned INT,
                    duration_mins INT,
                    date DATE DEFAULT (CURRENT_DATE),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            # 5. Coach History Table (For AI Coach persistence)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS coach_history (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT,
                    analysis_text LONGTEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            # 6. Recipe History Table (For Recipe Generator persistence)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS recipe_history (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT,
                    ingredients TEXT,
                    recipe_text LONGTEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            
            print("Database 'calorieapp' setup completed successfully!")
            print("Tables verified: users, meals, water_intake, activities")
            
    except Error as e:
        print(f"Error while connecting to MySQL: {e}")
    finally:
        if 'connection' in locals() and connection.is_connected():
            cursor.close()
            connection.close()

if __name__ == "__main__":
    setup_database()
