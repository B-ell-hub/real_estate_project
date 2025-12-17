"""
Database initialization script
Run this to set up the database schema
"""
import mysql.connector
from mysql.connector import Error

# Database configuration (without database name for initial connection)
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'port': 3307
}

def init_database():
    """Initialize the database and create tables"""
    try:
        # Connect without database first
        connection = mysql.connector.connect(**DB_CONFIG)
        cursor = connection.cursor()
        
        # Create database if it doesn't exist
        cursor.execute("CREATE DATABASE IF NOT EXISTS `Real estate`")
        print("✓ Database 'Real estate' created or already exists")
        
        # Use the database
        cursor.execute("USE `Real estate`")
        
        # Create properties table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS properties (
                id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                description TEXT,
                property_type ENUM('sale', 'rent', 'airbnb') NOT NULL,
                address VARCHAR(255),
                city VARCHAR(100) NOT NULL,
                state VARCHAR(100),
                zip_code VARCHAR(20),
                price DECIMAL(12, 2) NOT NULL,
                bedrooms INT,
                bathrooms DECIMAL(3, 1),
                area DECIMAL(10, 2) COMMENT 'Square feet or square meters',
                amenities TEXT COMMENT 'JSON or comma-separated amenities',
                units_available INT DEFAULT 1 COMMENT 'Number of available units',
                check_in TIME COMMENT 'For AirBnB',
                check_out TIME COMMENT 'For AirBnB',
                max_guests INT COMMENT 'For AirBnB',
                featured TINYINT(1) DEFAULT 0 COMMENT 'Whether property is featured (0=no, 1=yes)',
                status ENUM('active', 'sold', 'rented', 'inactive') DEFAULT 'active',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_property_type (property_type),
                INDEX idx_city (city),
                INDEX idx_status (status),
                INDEX idx_price (price),
                INDEX idx_created_at (created_at)
            )
        """)
        print("✓ Properties table created")
        
        # Create property_images table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS property_images (
                id INT AUTO_INCREMENT PRIMARY KEY,
                property_id INT NOT NULL,
                image_path VARCHAR(255) NOT NULL,
                is_primary BOOLEAN DEFAULT FALSE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE,
                INDEX idx_property_id (property_id)
            )
        """)
        print("✓ Property images table created")
        
        # Create users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(100) NOT NULL UNIQUE,
                email VARCHAR(255) NOT NULL UNIQUE,
                phone VARCHAR(50) NULL,
                password_hash VARCHAR(255) NOT NULL,
                full_name VARCHAR(255),
                role ENUM('admin', 'manager', 'user') DEFAULT 'user',
                status ENUM('active', 'suspended', 'deleted') DEFAULT 'active',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_username (username),
                INDEX idx_email (email),
                INDEX idx_role (role)
            )
        """)
        print("✓ Users table created")
        
        # Create bookings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bookings (
                id INT AUTO_INCREMENT PRIMARY KEY,
                property_id INT NOT NULL,
                user_id INT NULL COMMENT 'NULL for guest bookings (AirBnB)',
                booking_type ENUM('sale', 'rent', 'airbnb') NOT NULL,
                start_date DATE,
                end_date DATE,
                status ENUM('pending', 'confirmed', 'cancelled', 'completed') DEFAULT 'pending',
                message TEXT,
                guest_name VARCHAR(255) NULL COMMENT 'Guest name for non-registered users',
                guest_email VARCHAR(255) NULL COMMENT 'Guest email for non-registered users',
                guest_phone VARCHAR(50) NULL COMMENT 'Guest phone for non-registered users',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
                INDEX idx_property_id (property_id),
                INDEX idx_user_id (user_id),
                INDEX idx_status (status),
                INDEX idx_created_at (created_at)
            )
        """)
        print("✓ Bookings table created")

        # Create rentals table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rentals (
                id INT AUTO_INCREMENT PRIMARY KEY,
                booking_id INT,
                property_id INT NOT NULL,
                tenant_id INT NOT NULL,
                rent_amount DECIMAL(12, 2) NOT NULL,
                deposit_amount DECIMAL(12, 2) DEFAULT 0,
                lease_start DATE NOT NULL,
                lease_end DATE,
                payment_cycle ENUM('monthly', 'quarterly', 'yearly') DEFAULT 'monthly',
                unit_number VARCHAR(50) NULL COMMENT 'Unit/Apartment number (e.g., A1, 101, Unit 5)',
                floor_number VARCHAR(50) NULL COMMENT 'Floor number (e.g., 1st Floor, Ground Floor, 2)',
                door_number VARCHAR(50) NULL COMMENT 'Door/Entrance number (e.g., Door 1, Entrance A)',
                building_name VARCHAR(255) NULL COMMENT 'Building name (for apartment complexes)',
                block_number VARCHAR(50) NULL COMMENT 'Block number (for multi-block properties)',
                next_due_date DATE,
                last_payment_date DATE,
                status ENUM('active', 'ended', 'paused') DEFAULT 'active',
                notes TEXT,
                assigned_by INT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (booking_id) REFERENCES bookings(id) ON DELETE SET NULL,
                FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE,
                FOREIGN KEY (tenant_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (assigned_by) REFERENCES users(id) ON DELETE SET NULL,
                INDEX idx_rental_status (status),
                INDEX idx_tenant_id (tenant_id)
            )
        """)
        print("✓ Rentals table created")

        # Create rental payments table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rental_payments (
                id INT AUTO_INCREMENT PRIMARY KEY,
                rental_id INT NOT NULL,
                period_label VARCHAR(150) NOT NULL,
                amount DECIMAL(12, 2) NOT NULL,
                payment_date DATE,
                payment_method VARCHAR(50),
                reference VARCHAR(100),
                notes TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (rental_id) REFERENCES rentals(id) ON DELETE CASCADE,
                INDEX idx_rental_payment_rental (rental_id),
                INDEX idx_rental_payment_date (payment_date)
            )
        """)
        print("✓ Rental payments table created")
        
        # Create booking payments table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS booking_payments (
                id INT AUTO_INCREMENT PRIMARY KEY,
                booking_id INT NOT NULL,
                property_id INT NOT NULL,
                amount DECIMAL(12, 2) NOT NULL COMMENT 'Total payment amount',
                payment_date DATE NOT NULL COMMENT 'Date when booking was confirmed (payment date)',
                booking_type ENUM('sale', 'rent', 'airbnb') NOT NULL,
                start_date DATE,
                end_date DATE,
                nights INT NULL COMMENT 'Number of nights (for AirBnB)',
                customer_name VARCHAR(255),
                customer_email VARCHAR(255),
                payment_method VARCHAR(50) DEFAULT 'booking_confirmation' COMMENT 'How payment was made',
                reference VARCHAR(100) DEFAULT 'AUTO',
                notes TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (booking_id) REFERENCES bookings(id) ON DELETE CASCADE,
                FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE,
                INDEX idx_booking_payment_booking (booking_id),
                INDEX idx_booking_payment_property (property_id),
                INDEX idx_booking_payment_date (payment_date),
                INDEX idx_booking_payment_type (booking_type)
            )
        """)
        print("✓ Booking payments table created")

        # Create rental reports table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rental_reports (
                id INT AUTO_INCREMENT PRIMARY KEY,
                rental_id INT NOT NULL,
                reported_by INT NOT NULL,
                subject VARCHAR(150) NOT NULL,
                report_type ENUM('maintenance', 'billing', 'general', 'other') DEFAULT 'general',
                description TEXT,
                cost DECIMAL(12, 2) DEFAULT 0.00,
                status ENUM('open', 'in_progress', 'resolved', 'closed') DEFAULT 'open',
                resolution_notes TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (rental_id) REFERENCES rentals(id) ON DELETE CASCADE,
                FOREIGN KEY (reported_by) REFERENCES users(id) ON DELETE CASCADE,
                INDEX idx_rental_report_status (status),
                INDEX idx_rental_report_rental (rental_id)
            )
        """)
        print("✓ Rental reports table created")
        
        # Create property_favorites table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS property_favorites (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                property_id INT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE,
                UNIQUE KEY unique_user_property (user_id, property_id),
                INDEX idx_user_id (user_id),
                INDEX idx_property_id (property_id)
            )
        """)
        print("✓ Property favorites table created")
        
        # Create reminders_sent table (to track sent reminders and prevent duplicates)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reminders_sent (
                id INT AUTO_INCREMENT PRIMARY KEY,
                reminder_type ENUM('check_in', 'check_out', 'payment_due', 'lease_expiration') NOT NULL,
                reference_id INT NOT NULL COMMENT 'booking_id, rental_id, or payment_id',
                reference_type ENUM('booking', 'rental', 'payment') NOT NULL,
                reminder_date DATE NOT NULL COMMENT 'Date the reminder is for',
                sent_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                recipient_email VARCHAR(255) NOT NULL,
                recipient_name VARCHAR(255),
                UNIQUE KEY unique_reminder (reminder_type, reference_id, reference_type, reminder_date),
                INDEX idx_reminder_date (reminder_date),
                INDEX idx_sent_at (sent_at)
            )
        """)
        print("✓ Reminders sent table created")
        
        connection.commit()
        print("\n✓ Database initialization completed successfully!")
        
        cursor.close()
        connection.close()
        
    except Error as e:
        print(f"✗ Error: {e}")
        return False
    
    return True

if __name__ == '__main__':
    print("Initializing Property Management Database...\n")
    init_database()

