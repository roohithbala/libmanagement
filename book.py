import sqlite3

DATABASE = "library.db"

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def add_book(title, author, genre, publication_year, isbn, added_by):
    """Add a new book to the database."""
    try:
        with get_db_connection() as conn:
            conn.execute(
                "INSERT INTO books (title, author, genre, publication_year, isbn, added_by) VALUES (?, ?, ?, ?, ?, ?)",
                (title, author, genre, publication_year, isbn, added_by),
            )
        print("Book added successfully!")
        return True
    except sqlite3.IntegrityError:
        print("Error: Book with ISBN already exists.")
        return False

def get_all_books():
    """Retrieve all books from the database."""
    with get_db_connection() as conn:
        return conn.execute("SELECT * FROM books").fetchall()

def delete_book(book_id):
    """Delete a book from the database by its ID."""
    try:
        with get_db_connection() as conn:
            conn.execute("DELETE FROM books WHERE id = ?", (book_id,))
        print("Book deleted successfully!")
        return True
    except Exception as e:
        print(f"Error deleting book: {e}")
        return False

def take_book(book_id):
    """Mark a book as 'Taken' if it is available."""
    try:
        with get_db_connection() as conn:
            book = conn.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
            if book and book["status"] == "Available":
                conn.execute("UPDATE books SET status = 'Taken' WHERE id = ?", (book_id,))
                print("Book taken successfully!")
                return True
            print("Error: Book is not available.")
            return False
    except Exception as e:
        print(f"Error taking book: {e}")
        return False

def unlock_book(book_id):
    """Unlock a book by setting its status back to 'Available'."""
    try:
        with get_db_connection() as conn:
            book = conn.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
            if book and book["status"] == "Taken":
                conn.execute("UPDATE books SET status = 'Available' WHERE id = ?", (book_id,))
                print("Book unlocked successfully!")
                return True
            print("Error: Book is already available.")
            return False
    except Exception as e:
        print(f"Error unlocking book: {e}")
        return False
