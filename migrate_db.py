import sqlite3
from datetime import datetime

def add_admin_logs_table():
    DATABASE = "library.db"
    with sqlite3.connect(DATABASE) as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS admin_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            performed_by INTEGER NOT NULL,
            affected_user INTEGER NOT NULL,
            timestamp DATETIME NOT NULL,
            FOREIGN KEY (performed_by) REFERENCES users(id),
            FOREIGN KEY (affected_user) REFERENCES users(id)
        )
        """)
        print("Created admin_logs table")

def add_reset_requests_table():
    """Add table for password reset requests"""
    DATABASE = "library.db"
    with sqlite3.connect(DATABASE) as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS reset_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            email TEXT NOT NULL,
            reason TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            requested_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            processed_at DATETIME,
            processed_by INTEGER,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (processed_by) REFERENCES users(id)
        )
        """)
        print("Created reset_requests table")

def migrate_database():
    """Add processed_by, return_note, and return_type columns to book_history table"""
    DATABASE = "library.db"
    
    try:
        with sqlite3.connect(DATABASE) as conn:
            # Check if columns already exist
            cursor = conn.execute("PRAGMA table_info(book_history)")
            columns = [column[1] for column in cursor.fetchall()]
            
            # Add processed_by column if it doesn't exist
            if 'processed_by' not in columns:
                conn.execute("""
                    ALTER TABLE book_history 
                    ADD COLUMN processed_by INTEGER 
                    REFERENCES users(id)
                """)
                print("Added processed_by column")
            
            # Add return_note column if it doesn't exist
            if 'return_note' not in columns:
                conn.execute("""
                    ALTER TABLE book_history 
                    ADD COLUMN return_note TEXT
                """)
                print("Added return_note column")
            
            # Add return_type column if it doesn't exist
            if 'return_type' not in columns:
                conn.execute("""
                    ALTER TABLE book_history 
                    ADD COLUMN return_type TEXT
                """)
                print("Added return_type column")
            
            # Update existing records with default values
            conn.execute("""
                UPDATE book_history 
                SET processed_by = NULL, 
                    return_note = 'Migration: No previous note'
                WHERE processed_by IS NULL
            """)
            
            # Update existing records with default return type
            conn.execute("""
                UPDATE book_history 
                SET return_type = CASE
                    WHEN processed_by IS NOT NULL THEN 'Force Return'
                    WHEN penalty > 0 THEN 'Returned with Penalty'
                    ELSE 'Normal Return'
                END
                WHERE return_type IS NULL AND returned_at IS NOT NULL
            """)
            
            # Add reset_token and reset_token_expiry columns to users table
            cursor = conn.execute("PRAGMA table_info(users)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'reset_token' not in columns:
                conn.execute("""
                    ALTER TABLE users 
                    ADD COLUMN reset_token TEXT
                """)
                print("Added reset_token column")
            
            if 'reset_token_expiry' not in columns:
                conn.execute("""
                    ALTER TABLE users 
                    ADD COLUMN reset_token_expiry DATETIME
                """)
                print("Added reset_token_expiry column")
            
            conn.commit()
            print("Migration completed successfully!")
            
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return False
    except Exception as e:
        print(f"Error: {e}")
        return False
    
    add_admin_logs_table()
    add_reset_requests_table()
    return True

def migrate_users():
    conn = sqlite3.connect('library.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # Create backup of current users
        cursor.execute("CREATE TABLE users_backup AS SELECT * FROM users")
        
        # Drop existing table
        cursor.execute("DROP TABLE users")
        
        # Create new table with updated schema
        cursor.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            first_name TEXT,
            last_name TEXT,
            date_of_birth DATE,
            gender TEXT,
            phone TEXT,
            address TEXT,
            occupation TEXT,
            reading_interests TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Copy existing data
        cursor.execute("""
        INSERT INTO users (id, username, email, password, role, created_at)
        SELECT id, username, email, password, role, CURRENT_TIMESTAMP
        FROM users_backup
        """)
        
        conn.commit()
        print("Migration completed successfully!")
        
    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
        
    finally:
        conn.close()

if __name__ == "__main__":
    # Run migration
    if migrate_database():
        print("Database migration completed successfully.")
    else:
        print("Database migration failed!")
    
    migrate_users()