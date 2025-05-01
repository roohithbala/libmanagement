import sqlite3
from datetime import datetime

DATABASE = "library.db"

def get_db_connection():
    return sqlite3.connect(DATABASE)

def init_db():
    with get_db_connection() as conn:
        # Users table
        conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
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
        );
        """)
        
        # Books table
        conn.execute("""
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            category TEXT NOT NULL,
            publication_year INTEGER,
            isbn TEXT UNIQUE NOT NULL,
            added_by TEXT,
            main_area TEXT,
            rack_no TEXT,
            column_no TEXT,
            total_copies INTEGER DEFAULT 1,
            available_copies INTEGER DEFAULT 1
        );
        """)
        
        # Book copies
        conn.execute("""
        CREATE TABLE IF NOT EXISTS book_copies (
            copy_id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'Available',
            borrowed_by INTEGER,
            due_date TEXT,
            penalty REAL DEFAULT 0,
            FOREIGN KEY (book_id) REFERENCES books(id),
            FOREIGN KEY (borrowed_by) REFERENCES users(id)
        );
        """)

        # Book history
        conn.execute("""
        CREATE TABLE IF NOT EXISTS book_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id INTEGER NOT NULL,
            copy_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            borrowed_at DATETIME NOT NULL,
            due_date DATETIME,
            returned_at DATETIME,
            penalty REAL DEFAULT 0,
            processed_by INTEGER,
            return_note TEXT,
            return_type TEXT,
            FOREIGN KEY (book_id) REFERENCES books(id),
            FOREIGN KEY (copy_id) REFERENCES book_copies(copy_id),
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (processed_by) REFERENCES users(id)
        );
        """)
        
        # Book modifications
        conn.execute("""
        CREATE TABLE IF NOT EXISTS book_modifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id INTEGER NOT NULL,
            modified_by INTEGER NOT NULL,
            modification TEXT NOT NULL,
            modified_at DATETIME NOT NULL,
            FOREIGN KEY (book_id) REFERENCES books(id),
            FOREIGN KEY (modified_by) REFERENCES users(id)
        );
        """)

        # Reset requests
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
        );
        """)
        
        print("✅ Tables created successfully.")
        conn.commit()

def insert_sample_user():
    username = "roohithbalaexample"
    email = "roohith@example.com"
    password = "hashedpassword123"
    role = "user"
    first_name = "Roohith"
    last_name = "Bala"
    date_of_birth = "2003-07-10"
    gender = "Male"
    phone = "9876543210"
    address = "Erode, Tamil Nadu"
    occupation = "Student"
    reading_interests = "Tech, Fiction, AI"

    with get_db_connection() as conn:
        conn.execute("""
            INSERT INTO users (
                username, email, password, role,
                first_name, last_name, date_of_birth, gender,
                phone, address, occupation, reading_interests
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            username, email, password, role,
            first_name, last_name, date_of_birth, gender,
            phone, address, occupation, reading_interests
        ))
        conn.commit()
        print("✅ Sample user inserted.")

def insert_sample_book():
    with get_db_connection() as conn:
        conn.execute("""
            INSERT INTO books (
                title, author, category, publication_year,
                isbn, added_by, main_area, rack_no, column_no,
                total_copies, available_copies
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "Deep Learning", "Ian Goodfellow", "AI", 2016,
            "9780262035613", "roohithbala", "A1", "R3", "C2", 5, 5
        ))
        conn.commit()
        print("✅ Sample book inserted.")

def view_users():
    print("\n📋 Full Users Table:")
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT * FROM users")
        columns = [description[0] for description in cursor.description]
        rows = cursor.fetchall()
        print(f"{' | '.join(columns)}")
        print("-" * 100)
        for row in rows:
            print(" | ".join(str(item) if item is not None else "" for item in row))

def view_books():
    print("\n📚 Full Books Table:")
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT * FROM books")
        columns = [description[0] for description in cursor.description]
        rows = cursor.fetchall()
        print(f"{' | '.join(columns)}")
        print("-" * 100)
        for row in rows:
            print(" | ".join(str(item) if item is not None else "" for item in row))

if __name__ == "__main__":
    init_db()
    insert_sample_user()
    insert_sample_book()
    view_users()
    view_books()
