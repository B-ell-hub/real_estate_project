"""
Check if featured column exists and what values it has
"""
import mysql.connector
from mysql.connector import Error

# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'port': 3306,
    'database': 'Real estate'
}

def check_featured():
    """Check featured column status"""
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        cursor = connection.cursor(dictionary=True)
        
        # Check if column exists
        cursor.execute("""
            SELECT COUNT(*) as exists_col
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = 'Real estate' 
            AND TABLE_NAME = 'properties' 
            AND COLUMN_NAME = 'featured'
        """)
        
        result = cursor.fetchone()
        if result['exists_col'] == 0:
            print("Column 'featured' does NOT exist in properties table")
            return False
        else:
            print("Column 'featured' EXISTS in properties table")
        
        # Check current values
        cursor.execute("SELECT id, title, featured FROM properties LIMIT 10")
        properties = cursor.fetchall()
        
        print("\nCurrent featured values:")
        for prop in properties:
            print(f"ID: {prop['id']}, Title: {prop['title'][:30]}, Featured: {prop['featured']}")
        
        # Count featured vs non-featured
        cursor.execute("SELECT COUNT(*) as total FROM properties WHERE featured = 1")
        featured_count = cursor.fetchone()['total']
        
        cursor.execute("SELECT COUNT(*) as total FROM properties WHERE featured = 0 OR featured IS NULL")
        non_featured_count = cursor.fetchone()['total']
        
        print(f"\nFeatured properties: {featured_count}")
        print(f"Non-featured properties: {non_featured_count}")
        
        cursor.close()
        connection.close()
        return True
        
    except Error as e:
        print(f"Error: {e}")
        return False

if __name__ == '__main__':
    print("Checking featured column status...\n")
    check_featured()

