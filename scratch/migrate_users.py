import mysql.connector
from mysql.connector import Error

def migrate():
    try:
        conn = mysql.connector.connect(
            host='localhost',
            user='root',
            password='Shriyash@11',
            database='calorieapp'
        )
        if conn.is_connected():
            cursor = conn.cursor()
            columns = [
                ('allergies', 'TEXT'),
                ('favorite_foods', 'TEXT'),
                ('diseases', 'TEXT'),
                ('health_issues', 'TEXT'),
                ('disability', 'TEXT')
            ]
            
            for col_name, col_type in columns:
                cursor.execute(f"SHOW COLUMNS FROM users LIKE '{col_name}'")
                result = cursor.fetchone()
                if not result:
                    print(f"Adding column {col_name}...")
                    cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
            
            conn.commit()
            print("Migration completed successfully.")
    except Error as e:
        print(f"Error: {e}")
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

if __name__ == "__main__":
    migrate()
