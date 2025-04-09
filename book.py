import sqlite3
from datetime import datetime, timedelta
from flask import Flask, render_template, redirect, url_for, flash

DATABASE = "library.db"
app = Flask(__name__)

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def add_book(title, author, category, publication_year, isbn, added_by, main_area, rack_no, column_no):
    """Add a new book."""
    try:
        with get_db_connection() as conn:
            conn.execute(
                """INSERT INTO books 
                   (title, author, category, publication_year, isbn, 
                    added_by, status, main_area, rack_no, column_no)
                   VALUES (?, ?, ?, ?, ?, ?, 'Available', ?, ?, ?)""",
                (title, author, category, publication_year, isbn,
                 added_by, main_area, rack_no, column_no)
            )
            conn.commit()
            print("Book added successfully!")
            return True
    except sqlite3.IntegrityError:
        print("Error: Book with ISBN already exists.")
        return False

def update_book(book_id, title, author, category, publication_year, isbn, num_copies, modified_by):
    """Update an existing book and record modification details."""
    try:
        with get_db_connection() as conn:
            # First get current book details and copy counts
            current = conn.execute("""
                SELECT b.*, 
                       COUNT(bc.copy_id) as total_copies,
                       SUM(CASE WHEN bc.status = 'Available' THEN 1 ELSE 0 END) as available_copies
                FROM books b
                LEFT JOIN book_copies bc ON b.id = bc.book_id
                WHERE b.id = ?
                GROUP BY b.id
            """, (book_id,)).fetchone()
            
            if not current:
                return False, "Book not found"
                
            # Calculate copies in use
            copies_in_use = current['total_copies'] - (current['available_copies'] or 0)
            
            # Ensure new copy count isn't less than copies currently in use
            if num_copies < copies_in_use:
                return False, f"Cannot reduce copies below {copies_in_use} (currently borrowed)"
                
            # Track modifications
            modifications = []
            if current['title'] != title:
                modifications.append(f"Title changed from '{current['title']}' to '{title}'")
            if current['author'] != author:
                modifications.append(f"Author changed from '{current['author']}' to '{author}'")
            if current['category'] != category:
                modifications.append(f"Category changed from '{current['category']}' to '{category}'")
            if current['publication_year'] != publication_year:
                modifications.append(f"Publication year changed from {current['publication_year']} to {publication_year}")
            if current['isbn'] != isbn:
                modifications.append(f"ISBN changed from '{current['isbn']}' to '{isbn}'")
            if current['total_copies'] != num_copies:
                modifications.append(f"Number of copies changed from {current['total_copies']} to {num_copies}")
            
            # Update book details
            conn.execute(
                """UPDATE books 
                   SET title=?, author=?, category=?, publication_year=?, isbn=?,
                       total_copies=?, available_copies=?
                   WHERE id=?""",
                (title, author, category, publication_year, isbn,
                 num_copies, num_copies - copies_in_use, book_id)
            )
            
            # Handle copy adjustments
            if num_copies > current['total_copies']:
                # Add new copies
                for _ in range(num_copies - current['total_copies']):
                    conn.execute(
                        "INSERT INTO book_copies (book_id, status) VALUES (?, 'Available')",
                        (book_id,)
                    )
            elif num_copies < current['total_copies']:
                # Remove excess available copies
                conn.execute("""
                    DELETE FROM book_copies 
                    WHERE book_id = ? 
                    AND status = 'Available' 
                    AND copy_id IN (
                        SELECT copy_id 
                        FROM book_copies 
                        WHERE book_id = ? 
                        AND status = 'Available' 
                        LIMIT ?
                    )""", (book_id, book_id, current['total_copies'] - num_copies))
            
            # Record each modification in the log
            for mod in modifications:
                conn.execute(
                    """INSERT INTO book_modifications 
                       (book_id, modified_by, modification, modified_at)
                       VALUES (?, ?, ?, ?)""",
                    (book_id, modified_by, mod, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                )
            
            conn.commit()
            return True, "Book updated successfully"
            
    except sqlite3.IntegrityError:
        return False, "Book with this ISBN already exists"
    except Exception as e:
        return False, f"Error updating book: {str(e)}"

def delete_book(book_id):
    """Delete a book from the database by its ID."""
    try:
        with get_db_connection() as conn:
            conn.execute("DELETE FROM books WHERE id=?", (book_id,))
            conn.commit()
        print("Book deleted successfully!")
        return True
    except Exception as e:
        print(f"Error deleting book: {e}")
        return False

def update_book_location(book_id, main_area, rack_no, column_no, modified_by=None):
    """Update the location of a book and record the modification if provided."""
    try:
        with get_db_connection() as conn:
            conn.execute(
                "UPDATE books SET main_area=?, rack_no=?, column_no=? WHERE id=?",
                (main_area, rack_no, column_no, book_id)
            )
            conn.commit()
            if modified_by:
                record_book_modification(book_id, modified_by, f"Location updated to {main_area}, Rack {rack_no}, Column {column_no}")
        print("Book location updated successfully!")
        return True
    except Exception as e:
        print(f"Error updating book location: {e}")
        return False

def borrow_book(book_id, user_id):
    """Borrow an available copy of a book."""
    conn = None
    try:
        conn = get_db_connection()
        # Check if there are available copies
        book = conn.execute("""
            SELECT b.*, 
                   COUNT(DISTINCT CASE WHEN bc.status = 'Available' THEN bc.copy_id END) as available_copies
            FROM books b
            LEFT JOIN book_copies bc ON b.id = bc.book_id
            WHERE b.id = ?
            GROUP BY b.id
        """, (book_id,)).fetchone()

        if not book or book['available_copies'] == 0:
            return False

        # Get an available copy
        copy = conn.execute("""
            SELECT copy_id 
            FROM book_copies 
            WHERE book_id = ? AND status = 'Available' 
            LIMIT 1""", (book_id,)).fetchone()

        if copy:
            # Set due date to 14 days from now
            due_date = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")
            
            # Update copy status
            conn.execute("""
                UPDATE book_copies 
                SET status = 'Taken', 
                    borrowed_by = ?,
                    due_date = ?
                WHERE copy_id = ?""", 
                (user_id, due_date, copy['copy_id']))

            # Update available copies count in books table
            conn.execute("""
                UPDATE books 
                SET available_copies = available_copies - 1
                WHERE id = ?""", (book_id,))

            # Record in history (without due_date)
            conn.execute("""
                INSERT INTO book_history 
                (book_id, copy_id, user_id, borrowed_at)
                VALUES (?, ?, ?, ?)""",
                (book_id, copy['copy_id'], user_id, 
                 datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

            # Record the modification
            conn.execute("""
                INSERT INTO book_modifications 
                (book_id, modified_by, modification, modified_at)
                VALUES (?, ?, ?, ?)""",
                (book_id, user_id, "Book borrowed", 
                 datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

            conn.commit()
            return True

        return False

    except Exception as e:
        print(f"Error borrowing book: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def calculate_penalty(days_overdue):
    """Calculate penalty in Rupees based on days overdue"""
    if days_overdue <= 0:
        return 0
    
    # First week: ₹10 per day
    if days_overdue <= 7:
        return days_overdue * 10
    
    # Second week: ₹20 per day
    elif days_overdue <= 14:
        first_week = 7 * 10
        remaining_days = days_overdue - 7
        return first_week + (remaining_days * 20)
    
    # After two weeks: ₹50 per day
    else:
        first_week = 7 * 10
        second_week = 7 * 20
        remaining_days = days_overdue - 14
        return first_week + second_week + (remaining_days * 50)

def return_book(book_id, user_id):
    """Return a book and calculate any penalties."""
    try:
        with get_db_connection() as conn:
            # Get the book copy that was borrowed by this user
            copy = conn.execute("""
                SELECT bc.*, b.id as book_id, b.title,
                       u.username as borrower_name 
                FROM book_copies bc 
                JOIN books b ON bc.book_id = b.id 
                LEFT JOIN users u ON bc.borrowed_by = u.id
                WHERE bc.book_id = ? AND bc.borrowed_by = ? 
                AND bc.status = 'Taken'
                LIMIT 1""", (book_id, user_id)).fetchone()

            if not copy:
                return False, "No borrowed copy found"

            # Calculate penalty if overdue
            penalty = 0
            return_type = "Normal Return"
            days_overdue = 0
            if copy['due_date']:
                due_date = datetime.strptime(copy['due_date'], "%Y-%m-%d")
                days_overdue = (datetime.now() - due_date).days
                if days_overdue > 0:
                    penalty = calculate_penalty(days_overdue)
                    return_type = "Returned with Penalty"

            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return_note = (
                f"{return_type} by {copy['borrower_name']}" + 
                (f" | Penalty: ₹{penalty} for {days_overdue} days overdue" if penalty > 0 else "")
            )

            # Update copy status
            conn.execute("""
                UPDATE book_copies 
                SET status = 'Available', 
                    borrowed_by = NULL, 
                    due_date = NULL, 
                    penalty = ?
                WHERE copy_id = ?""", (penalty, copy['copy_id']))

            # Update available copies count
            conn.execute("""
                UPDATE books 
                SET available_copies = available_copies + 1 
                WHERE id = ?""", (book_id,))

            # Update history with detailed return note
            conn.execute("""
                UPDATE book_history 
                SET returned_at = ?, 
                    penalty = ?,
                    return_note = ?,
                    return_type = ?
                WHERE copy_id = ? AND returned_at IS NULL""",
                (current_time, penalty, return_note, return_type, copy['copy_id']))

            # Record modification
            modification = (
                f"Book '{copy['title']}' {return_type.lower()}" +
                (f" with penalty ₹{penalty} ({days_overdue} days overdue)" if penalty > 0 else "")
            )
            conn.execute("""
                INSERT INTO book_modifications 
                (book_id, modified_by, modification, modified_at)
                VALUES (?, ?, ?, ?)""",
                (book_id, user_id, modification, current_time))

            conn.commit()
            return True, f"Book {return_type.lower()}" + (f" with penalty ₹{penalty}" if penalty > 0 else "")

    except Exception as e:
        print(f"Error returning book: {e}")
        return False, str(e)

def force_return_book(book_id, processed_by):
    """Force return a book and record who processed it."""
    conn = None
    try:
        conn = get_db_connection()
        # Get book copy details with more information
        copy = conn.execute("""
            SELECT bc.*, b.id as book_id, b.title,
                   u.username as borrower_name,
                   p.username as processor_name
            FROM book_copies bc 
            JOIN books b ON bc.book_id = b.id
            LEFT JOIN users u ON bc.borrowed_by = u.id 
            LEFT JOIN users p ON p.id = ?
            WHERE bc.book_id = ? AND bc.status = 'Taken'
            LIMIT 1""", (processed_by, book_id)).fetchone()

        if not copy:
            return False

        # Calculate penalty if overdue
        penalty = 0
        return_type = "Force Return"
        if copy['due_date']:
            due_date = datetime.strptime(copy['due_date'], "%Y-%m-%d")
            days_overdue = (datetime.now() - due_date).days
            if days_overdue > 0:
                penalty = calculate_penalty(days_overdue)
                return_type = "Force Return with Penalty"

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return_note = (
            f"{return_type} by {copy['processor_name']}" +
            (f" | Penalty: ₹{penalty} for {days_overdue} days overdue" if penalty > 0 else "")
        )

        # Update copy status
        conn.execute("""
            UPDATE book_copies 
            SET status='Available', borrowed_by=NULL, 
                due_date=NULL, penalty=? 
            WHERE copy_id=?""", (penalty, copy['copy_id']))

        # Update available copies count
        conn.execute("""
            UPDATE books 
            SET available_copies = available_copies + 1 
            WHERE id=?""", (book_id,))

        # Record the force return in history with detailed note
        conn.execute("""
            UPDATE book_history 
            SET returned_at=?, 
                penalty=?, 
                processed_by=?,
                return_note=?,
                return_type=?
            WHERE copy_id=? AND returned_at IS NULL""",
            (current_time, penalty, processed_by, return_note, return_type, copy['copy_id']))

        # Record modification with detailed note
        modification = (
            f"Book '{copy['title']}' force returned from {copy['borrower_name']}" +
            (f" with penalty ₹{penalty} ({days_overdue} days overdue)" if penalty > 0 else "")
        )
        conn.execute("""
            INSERT INTO book_modifications 
            (book_id, modified_by, modification, modified_at)
            VALUES (?, ?, ?, ?)""",
            (book_id, processed_by, modification, current_time))

        conn.commit()
        return True

    except Exception as e:
        print(f"Error force returning book: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def adjust_penalty(book_id, new_penalty, adjusted_by):
    """Adjust the penalty amount for a book by admin/librarian without day restrictions."""
    try:
        with get_db_connection() as conn:
            # Get the most recent history entry and copy details
            copy = conn.execute("""
                SELECT bc.*, bh.id as history_id, bh.penalty as current_penalty,
                       u.username as borrower_name
                FROM book_copies bc
                JOIN book_history bh ON bc.copy_id = bh.copy_id
                LEFT JOIN users u ON bc.borrowed_by = u.id
                WHERE bc.book_id = ? AND bc.status = 'Taken'
                ORDER BY bh.borrowed_at DESC LIMIT 1
            """, (book_id,)).fetchone()

            if not copy:
                return False

            # Update penalty in book_copies
            conn.execute("""
                UPDATE book_copies 
                SET penalty = ?
                WHERE copy_id = ?""", 
                (new_penalty, copy['copy_id']))

            # Update penalty in history with a note about manual adjustment
            conn.execute("""
                UPDATE book_history 
                SET penalty = ?,
                    return_note = CASE 
                        WHEN return_note IS NULL THEN ?
                        ELSE return_note || ' | ' || ?
                    END
                WHERE id = ?""",
                (new_penalty, 
                 f"Manual penalty adjustment to ₹{new_penalty}",
                 f"Manual penalty adjustment to ₹{new_penalty}",
                 copy['history_id']))

            # Get adjuster's username
            adjuster = conn.execute(
                "SELECT username FROM users WHERE id = ?", 
                (adjusted_by,)
            ).fetchone()

            # Record modification with detailed note
            modification = (
                f"Manual penalty adjustment for {copy['borrower_name']} "
                f"from ₹{copy['current_penalty']} to ₹{new_penalty} "
                f"by {adjuster['username']}"
            )
            
            conn.execute("""
                INSERT INTO book_modifications 
                (book_id, modified_by, modification, modified_at)
                VALUES (?, ?, ?, ?)""",
                (book_id, adjusted_by, modification, 
                 datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

            conn.commit()
            return True

    except Exception as e:
        print(f"Error adjusting penalty: {e}")
        return False

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

def record_book_modification(book_id, modified_by, modification):
    """Record a modification made to the book details."""
    try:
        with get_db_connection() as conn:
            conn.execute(
                "INSERT INTO book_modifications (book_id, modified_by, modification, modified_at) VALUES (?, ?, ?, ?)",
                (book_id, modified_by if modified_by else 0, modification, datetime.now())
            )
            conn.commit()
        print(f"Modification recorded: {modification}")
    except Exception as e:
        print(f"Error recording modification: {e}")

def unlock_book(book_id):
    """Unlock a book that is currently marked as taken."""
    try:
        with get_db_connection() as conn:
            # First check if the book exists and is taken
            book = conn.execute("""
                SELECT b.*, bc.copy_id 
                FROM books b
                JOIN book_copies bc ON b.id = bc.book_id
                WHERE b.id = ? AND bc.status = 'Taken'
                LIMIT 1""", (book_id,)).fetchone()

            if not book:
                print("Book not found or not currently taken")
                return False

            # Update the book copy status
            conn.execute("""
                UPDATE book_copies 
                SET status = 'Available',
                    borrowed_by = NULL,
                    due_date = NULL,
                    penalty = 0
                WHERE copy_id = ?""", (book['copy_id'],))

            # Update available copies count
            conn.execute("""
                UPDATE books 
                SET available_copies = available_copies + 1
                WHERE id = ?""", (book_id,))

            # Close any open history records
            conn.execute("""
                UPDATE book_history
                SET returned_at = CURRENT_TIMESTAMP,
                    penalty = 0
                WHERE copy_id = ? AND returned_at IS NULL""", 
                (book['copy_id'],))

            conn.commit()
            print("Book unlocked successfully!")
            return True

    except Exception as e:
        print(f"Error unlocking book: {e}")
        return False

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
