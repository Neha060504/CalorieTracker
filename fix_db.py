import mysql.connector

def migrate():
    config = {
        'host': 'localhost',
        'user': 'root',
        'password': 'Shriyash@11',
        'database': 'calorieapp'
    }
    try:
        conn = mysql.connector.connect(**config)
        cursor = conn.cursor()
        
        # Check if column exists
        cursor.execute("SHOW COLUMNS FROM meals LIKE 'meal_type'")
        if not cursor.fetchone():
            print("Adding 'meal_type' column...")
            cursor.execute("ALTER TABLE meals ADD COLUMN meal_type ENUM('Breakfast', 'Lunch', 'Dinner', 'Snack', 'Other') DEFAULT 'Other' AFTER meal_name")
            conn.commit()
            print("Migration successful.")
        else:
            print("Column 'meal_type' already exists.")
            
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    migrate()
