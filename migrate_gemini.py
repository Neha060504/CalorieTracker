import mysql.connector
from mysql.connector import Error

def migrate_database():
    try:
        connection = mysql.connector.connect(
            host='localhost',
            user='root',
            password='Shriyash@11',
            database='calorieapp'
        )
        
        if connection.is_connected():
            cursor = connection.cursor()
            
            # Check if gemini_api_key column exists
            cursor.execute("SHOW COLUMNS FROM users LIKE 'gemini_api_key'")
            result = cursor.fetchone()
            
            if not result:
                print("Adding 'gemini_api_key' column to 'users' table...")
                cursor.execute("ALTER TABLE users ADD COLUMN gemini_api_key VARCHAR(255)")
                print("Column added successfully.")
            else:
                print("Column 'gemini_api_key' already exists.")
                
            connection.commit()
            
    except Error as e:
        print(f"Error: {e}")
    finally:
        if 'connection' in locals() and connection.is_connected():
            cursor.close()
            connection.close()
            print("Migration complete.")

if __name__ == "__main__":
    migrate_database()
