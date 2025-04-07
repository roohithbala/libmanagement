import sqlite3
from datetime import datetime, timedelta
from flask import Flask, render_template, redirect, url_for, flash

DATABASE = "library.db"
app = Flask(__name__)

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def add_book(title, author, genre, publication_year, isbn, added_by):
    """Add a new book to the database."""
    try:
        with get_db_connection() as conn:
            conn.execute(
                "INSERT INTO books (title, author, genre, publication_year, isbn, added_by, status, location) VALUES (?, ?, ?, ?, ?, ?, 'Available', 'Library')",
                (title, author, genre, publication_year, isbn, added_by)
            )
        print("Book added successfully!")
        return True
    except sqlite3.IntegrityError:
        print("Error: Book with ISBN already exists.")
        return False

def update_book(book_id, title, author, genre, publication_year, isbn, modified_by):
    """Update an existing book and record modification details."""
    try:
        with get_db_connection() as conn:
            conn.execute(
                "UPDATE books SET title=?, author=?, genre=?, publication_year=?, isbn=? WHERE id=?",
                (title, author, genre, publication_year, isbn, book_id)
            )
            record_book_modification(book_id, modified_by, "Book details updated")
        print("Book updated successfully!")
        return True
    except sqlite3.IntegrityError:
        print("Error: Book with ISBN already exists.")
        return False

def delete_book(book_id):
    """Delete a book from the database by its ID."""
    try:
        with get_db_connection() as conn:
            conn.execute("DELETE FROM books WHERE id=?", (book_id,))
        print("Book deleted successfully!")
        return True
    except Exception as e:
        print(f"Error deleting book: {e}")
        return False

def update_book_location(book_id, location, modified_by=None):
    """Update the location of a book and record modification if provided."""
    try:
        with get_db_connection() as conn:
            conn.execute("UPDATE books SET location=? WHERE id=?", (location, book_id))
            if modified_by:
                record_book_modification(book_id, modified_by, f"Location updated to '{location}'")
        print("Book location updated successfully!")
        return True
    except Exception as e:
        print(f"Error updating book location: {e}")
        return False

def borrow_book(book_id, user_id):
    """Borrow a book and log the borrowing history."""
    try:
        with get_db_connection() as conn:
            book = conn.execute("SELECT * FROM books WHERE id=?", (book_id,)).fetchone()
            if book and book["status"] == "Available":
                due_date = datetime.now() + timedelta(days=5)
                conn.execute(
                    "UPDATE books SET status='Taken', borrowed_by=?, due_date=? WHERE id=?",
                    (user_id, due_date.strftime("%Y-%m-%d"), book_id)
                )
                conn.execute(
                    "INSERT INTO book_history (book_id, user_id, borrowed_at) VALUES (?, ?, ?)",
                    (book_id, user_id, datetime.now())
                )
                print("Book borrowed successfully!")
                return True
            print("Error: Book is not available.")
            return False
    except Exception as e:
        print(f"Error borrowing book: {e}")
        return False

def return_book(book_id, user_id):
    """Return a book, calculate penalties, and update history."""
    try:
        with get_db_connection() as conn:
            book = conn.execute("SELECT * FROM books WHERE id=?", (book_id,)).fetchone()
            if book and book["status"] == "Taken" and book["borrowed_by"] == user_id:
                due_date = datetime.strptime(book["due_date"], "%Y-%m-%d")
                today = datetime.now()
                penalty = max(0, (today - due_date).days * 10)  # $10 per day penalty
                conn.execute(
                    "UPDATE books SET status='Available', borrowed_by=NULL, due_date=NULL, penalty=? WHERE id=?",
                    (penalty, book_id)
                )
                conn.execute(
                    "UPDATE book_history SET returned_at=?, penalty=? WHERE book_id=? AND user_id=? AND returned_at IS NULL",
                    (datetime.now(), penalty, book_id, user_id)
                )
                print(f"Book returned successfully! Penalty: ${penalty}")
                return penalty
            print("Error: Book is not currently borrowed by this user.")
            return None
    except Exception as e:
        print(f"Error returning book: {e}")
        return None

def get_book_history(book_id):
    """Retrieve the borrowing history of a book."""
    try:
        with get_db_connection() as conn:
            history = conn.execute(
                "SELECT bh.*, u.username FROM book_history bh JOIN users u ON bh.user_id = u.id WHERE bh.book_id=? ORDER BY bh.borrowed_at DESC",
                (book_id,)
            ).fetchall()
        return history
    except Exception as e:
        print(f"Error getting book history: {e}")
        return []

def unlock_book(book_id):
    """Unlock a book by setting its status back to 'Available'."""
    try:
        with get_db_connection() as conn:
            book = conn.execute("SELECT * FROM books WHERE id=?", (book_id,)).fetchone()
            if book and book["status"] == "Taken":
                conn.execute("UPDATE books SET status='Available', borrowed_by=NULL, due_date=NULL WHERE id=?", (book_id,))
                record_book_modification(book_id, None, "Book unlocked manually")
                print("Book unlocked successfully!")
                return True
            print("Error: Book is already available.")
            return False
    except Exception as e:
        print(f"Error unlocking book: {e}")
        return False

def record_book_modification(book_id, modified_by, modification):
    """Record a modification made to the book details."""
    try:
        with get_db_connection() as conn:
            conn.execute(
                "INSERT INTO book_modifications (book_id, modified_by, modification, modified_at) VALUES (?, ?, ?, ?)",
                (book_id, modified_by if modified_by else 0, modification, datetime.now())
            )
        print(f"Modification recorded: {modification}")
    except Exception as e:
        print(f"Error recording modification: {e}")

@app.route("/book/<int:book_id>")
def view_book(book_id):
    """View book details and history."""
    with get_db_connection() as conn:
        book = conn.execute("""
            SELECT b.*, u.username AS borrowed_by_username
            FROM books b
            LEFT JOIN users u ON b.borrowed_by = u.id
            WHERE b.id = ?
        """, (book_id,)).fetchone()
        history = get_book_history(book_id)
    if not book:
        flash("Book not found!", "danger")
        return redirect(url_for("home"))
    return render_template("book_details.html", book=book, history=history)
