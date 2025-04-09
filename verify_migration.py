import sqlite3

def verify_migration():
    """Verify that the new columns were added correctly"""
    DATABASE = "library.db"
    
    try:
        with sqlite3.connect(DATABASE) as conn:
            # Check table structure
            cursor = conn.execute("PRAGMA table_info(book_history)")
            columns = {column[1]: column for column in cursor.fetchall()}
            
            # Verify columns exist
            if 'processed_by' not in columns:
                print("ERROR: processed_by column is missing!")
                return False
                
            if 'return_note' not in columns:
                print("ERROR: return_note column is missing!")
                return False
            
            # Verify foreign key constraint
            cursor = conn.execute("PRAGMA foreign_key_list(book_history)")
            foreign_keys = cursor.fetchall()
            has_processed_by_fk = any(fk[3] == 'processed_by' and fk[2] == 'users' for fk in foreign_keys)
            
            if not has_processed_by_fk:
                print("WARNING: processed_by foreign key constraint is missing!")
            
            print("Column verification completed successfully!")
            print("\nCurrent table structure:")
            for name, info in columns.items():
                print(f"{name}: {info[2]} {info[3]}")
            
            return True
            
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return False

if __name__ == "__main__":
    if verify_migration():
        print("\nMigration verification completed successfully!")
    else:
        print("\nMigration verification failed!")