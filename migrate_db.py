import sqlite3
from datetime import datetime

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
            
            conn.commit()
            print("Migration completed successfully!")
            
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return False
    except Exception as e:
        print(f"Error: {e}")
        return False
    
    return True

if __name__ == "__main__":
    # Run migration
    if migrate_database():
        print("Database migration completed successfully.")
    else:
        print("Database migration failed!")