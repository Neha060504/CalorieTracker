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
            
            # 1. Check if column already exists
            cursor.execute("SHOW COLUMNS FROM water_intake LIKE 'timestamp'")
            result = cursor.fetchone()
            
            if not result:
                print("Adding 'timestamp' column to 'water_intake'...")
                # Add timestamp column with default CURRENT_TIMESTAMP
                cursor.execute("""
                    ALTER TABLE water_intake 
                    ADD COLUMN timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP AFTER amount_ml
                """)
                # Populate it with date info for old records if possible, 
                # though it will default to NOW() anyway.
                print("Column added successfully.")
            else:
                print("Column 'timestamp' already exists.")
                
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
