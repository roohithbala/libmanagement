import sqlite3
import requests
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import secrets
from functools import wraps

from book import (update_book_location, borrow_book, return_book, get_book_history,
                 add_book, update_book, delete_book, unlock_book, force_return_book, 
                 adjust_penalty)
from chatbot_routes import chatbot_bp

app = Flask(__name__)
app.secret_key = "supersecretkey"
DATABASE = "library.db"

# Auth decorator
def admin_librarian_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            flash('Please login to access this page.', 'warning')
            return redirect(url_for('login'))
        if session.get('role') not in ['admin', 'librarian']:
            flash('Access denied. Admin or librarian privileges required.', 'danger')
            return redirect(url_for('user_dashboard'))
        return f(*args, **kwargs)
    return decorated_function

app.register_blueprint(chatbot_bp)

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db_connection() as conn:
        # Update users table with new fields
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
        
        # Create books table
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
        
        # Create book_copies table
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
        
        # Create book_history table with return_type column
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
            return_type TEXT,  -- Added return_type column
            FOREIGN KEY (book_id) REFERENCES books(id),
            FOREIGN KEY (copy_id) REFERENCES book_copies(copy_id),
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (processed_by) REFERENCES users(id)
        );
        """)
        
        # Create book_modifications table
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
        
        # Create reset_requests table
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
        
        print("Updated users table schema")
        conn.commit()

init_db()

def fetch_book_cover(title, author):
    try:
        search_query = f"{title} {author}".replace(" ", "+")
        search_url = f"https://openlibrary.org/search.json?q={search_query}"
        response = requests.get(search_url)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('docs') and len(data['docs']) > 0:
                first_result = data['docs'][0]
                if (first_result.get('cover_i')):
                    return f"https://covers.openlibrary.org/b/id/{first_result['cover_i']}-L.jpg"
        return "https://via.placeholder.com/150?text=No+Cover+Available"
    except Exception as e:
        print(f"Error fetching book cover: {e}")
        return "https://via.placeholder.com/150?text=Error"

def update_copy_counts(book_id):
    """Update the total and available copy counts for a book"""
    try:
        with get_db_connection() as conn:
            # Get current counts
            counts = conn.execute("""
                SELECT 
                    COUNT(copy_id) as total,
                    SUM(CASE WHEN status = 'Available' THEN 1 ELSE 0 END) as available
                FROM book_copies 
                WHERE book_id = ?
            """, (book_id,)).fetchone()
            
            # Update book record
            conn.execute("""
                UPDATE books 
                SET total_copies = ?, available_copies = ?
                WHERE id = ?
            """, (counts['total'], counts['available'], book_id))
            
            conn.commit()
            return True
    except Exception as e:
        print(f"Error updating copy counts: {e}")
        return False

@app.route("/")
def home():
    search_query = request.args.get('search', '').strip()
    category = request.args.get('category', '').strip()
    
    with get_db_connection() as conn:
        # Base query with filters
        query = """
            SELECT b.*, 
                   COUNT(DISTINCT bc.copy_id) as total_copies,
                   SUM(CASE WHEN bc.status = 'Available' THEN 1 ELSE 0 END) as available_copies,
                   COALESCE(MAX(CASE WHEN bc.status = 'Taken' THEN bc.penalty END), 0) as penalty
            FROM books b
            LEFT JOIN book_copies bc ON b.id = bc.book_id
        """
        params = []
        
        where_clauses = []
        if search_query:
            where_clauses.append("(b.title LIKE ? OR b.author LIKE ?)")
            params.extend([f'%{search_query}%', f'%{search_query}%'])
        
        if category:
            where_clauses.append("b.category = ?")
            params.append(category)
            
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
            
        query += " GROUP BY b.id"
        
        books = conn.execute(query, params).fetchall()

    book_list = []
    for book in books:
        book_dict = dict(book)
        book_dict["location"] = f"{book_dict.get('main_area', '')} - Rack {book_dict.get('rack_no', '')} Column {book_dict.get('column_no', '')}"
        book_dict["cover_url"] = fetch_book_cover(
            book_dict.get("title", ""),
            book_dict.get("author", "")
        )
        book_dict["status"] = "Available" if book_dict.get("available_copies", 0) > 0 else "Taken"
        book_list.append(book_dict)

    return render_template(
        "index.html", 
        books=book_list,
        search_query=search_query,
        selected_category=category
    )

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        # Basic Information
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]
        role = request.form["role"]
        
        # Personal Information
        first_name = request.form.get("first_name")
        last_name = request.form.get("last_name")
        date_of_birth = request.form.get("date_of_birth")
        gender = request.form.get("gender")
        
        # Contact Information
        phone = request.form.get("phone")
        address = request.form.get("address")
        
        # Additional Information
        occupation = request.form.get("occupation")
        reading_interests = request.form.get("interests")

        # Password hashing
        hashed_password = generate_password_hash(password, method="pbkdf2:sha256")

        try:
            with get_db_connection() as conn:
                conn.execute("""
                    INSERT INTO users (
                        username, email, password, role,
                        first_name, last_name, date_of_birth, gender,
                        phone, address, occupation, reading_interests
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    username, email, hashed_password, role,
                    first_name, last_name, date_of_birth, gender,
                    phone, address, occupation, reading_interests
                ))
                conn.commit()
                flash("Registration successful! Please log in.", "success")
                return redirect(url_for("login"))
                
        except sqlite3.IntegrityError as e:
            if "username" in str(e):
                flash("Username already exists!", "danger")
            elif "email" in str(e):
                flash("Email already exists!", "danger")
            else:
                flash("Registration failed! Please try again.", "danger")
            return redirect(url_for("register"))
            
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        with get_db_connection() as conn:
            user = conn.execute(
                "SELECT * FROM users WHERE username=?", 
                (username,)
            ).fetchone()
            
        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            flash(f"Welcome back, {user['username']}!", "success")
            
            # Handle redirect after login
            next_page = session.pop('next', None)
            if (next_page):
                return redirect(next_page)
                
            if user["role"] == "admin":
                return redirect(url_for("admin_dashboard"))
            elif user["role"] == "librarian":
                return redirect(url_for("librarian_dashboard"))
            else:
                return redirect(url_for("user_dashboard"))
                
        flash("Invalid username or password!", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("home"))

@app.route("/admin")
def admin_dashboard():
    if "user_id" not in session or session.get("role") != "admin":
        flash("Access Denied! Only Admins can access this page.", "danger")
        return redirect(url_for("home"))

    with get_db_connection() as conn:
        # Get books with borrower information
        books = conn.execute("""
            SELECT b.*, 
                   COUNT(DISTINCT bc.copy_id) as total_copies,
                   SUM(CASE WHEN bc.status = 'Available' THEN 1 ELSE 0 END) as available_copies,
                   GROUP_CONCAT(DISTINCT 
                       CASE WHEN bc.status = 'Taken' 
                       THEN u.username || ' (Due: ' || bc.due_date || 
                            CASE WHEN date(bc.due_date) < date('now') 
                                 THEN ', Overdue)' ELSE ')' END
                       END) as current_borrowers,
                   MAX(CASE WHEN bc.status = 'Taken' THEN bc.penalty ELSE 0 END) as max_penalty
            FROM books b
            LEFT JOIN book_copies bc ON b.id = bc.book_id
            LEFT JOIN users u ON bc.borrowed_by = u.id
            GROUP BY b.id
        """).fetchall()
        
        # Get user information
        users = conn.execute("""
            SELECT u.*, 
                   COUNT(DISTINCT bc.copy_id) as borrowed_books,
                   SUM(bc.penalty) as total_penalties
            FROM users u
            LEFT JOIN book_copies bc ON u.id = bc.borrowed_by
            GROUP BY u.id
        """).fetchall()

    return render_template("admin_dashboard.html", books=books, users=users)

@app.route("/librarian")
def librarian_dashboard():
    if "user_id" not in session or session.get("role") != "librarian":
        flash("Access Denied! Only Librarians can access this page.", "danger")
        return redirect(url_for("home"))
        
    with get_db_connection() as conn:
        # Get books with borrower information
        books = conn.execute("""
            SELECT b.*, 
                   COUNT(DISTINCT bc.copy_id) as total_copies,
                   SUM(CASE WHEN bc.status = 'Available' THEN 1 ELSE 0 END) as available_copies,
                   GROUP_CONCAT(DISTINCT 
                       CASE WHEN bc.status = 'Taken' 
                       THEN u.username || ' (Due: ' || bc.due_date || 
                            CASE WHEN date(bc.due_date) < date('now') 
                                 THEN ', Overdue)' ELSE ')' END
                       END) as current_borrowers,
                   MAX(CASE WHEN bc.status = 'Taken' THEN bc.penalty ELSE 0 END) as max_penalty
            FROM books b
            LEFT JOIN book_copies bc ON b.id = bc.book_id
            LEFT JOIN users u ON bc.borrowed_by = u.id
            GROUP BY b.id
        """).fetchall()
        
    return render_template("librarian_dashboard.html", books=books)

@app.route("/user")
def user_dashboard():
    if "user_id" not in session:
        flash("Please login to view your dashboard.", "warning")
        return redirect(url_for("login"))

    search_query = request.args.get('search', '').strip()
    category = request.args.get('category', '').strip()
    
    with get_db_connection() as conn:
        # Get all books with borrowing information
        query = """
            SELECT b.*, 
                   COUNT(DISTINCT bc.copy_id) as total_copies,
                   SUM(CASE WHEN bc.status = 'Available' THEN 1 ELSE 0 END) as available_copies,
                   COUNT(DISTINCT CASE WHEN bc.status = 'Taken' AND bc.borrowed_by = ? THEN bc.copy_id END) as my_borrowed,
                   MAX(CASE WHEN bc.status = 'Taken' AND bc.borrowed_by = ? THEN bc.due_date END) as my_due_date,
                   COALESCE(MAX(CASE WHEN bc.status = 'Taken' AND bc.borrowed_by = ? THEN bc.penalty END), 0) as my_penalty,
                   COALESCE(MAX(CASE WHEN bc.status = 'Taken' THEN bc.penalty END), 0) as penalty,
                   CASE WHEN MAX(CASE WHEN bc.status = 'Taken' AND bc.borrowed_by = ? 
                        THEN CASE WHEN date(bc.due_date) < date('now') THEN 1 ELSE 0 END END) = 1
                        THEN 1 ELSE 0 END as is_overdue
            FROM books b
            LEFT JOIN book_copies bc ON b.id = bc.book_id
        """
        params = [session["user_id"]] * 4

        # Add search filters
        where_clauses = []
        if search_query:
            where_clauses.append("(b.title LIKE ? OR b.author LIKE ?)")
            params.extend([f'%{search_query}%', f'%{search_query}%'])
        
        if category:
            where_clauses.append("b.category = ?")
            params.append(category)
            
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
            
        query += " GROUP BY b.id"
        all_books = conn.execute(query, params).fetchall()

        # Get currently borrowed books with penalties
        current_books = conn.execute("""
            SELECT b.*, bc.due_date, bc.penalty,
                   bh.borrowed_at,
                   CASE WHEN date(bc.due_date) < date('now') THEN 1 ELSE 0 END as is_overdue,
                   CAST((julianday('now') - julianday(bc.due_date)) as INTEGER) as days_overdue
            FROM book_copies bc
            JOIN books b ON bc.book_id = b.id
            JOIN book_history bh ON bc.copy_id = bh.copy_id
            WHERE bc.borrowed_by = ? AND bc.status = 'Taken'
            ORDER BY bh.borrowed_at DESC
        """, (session["user_id"],)).fetchall()

        # Get borrowing history with penalties
        history = conn.execute("""
            SELECT b.title, bh.borrowed_at, bh.returned_at, bh.penalty,
                   CASE WHEN bh.returned_at IS NOT NULL 
                        AND julianday(bh.returned_at) > julianday(bc.due_date)
                        THEN 1 ELSE 0 END as was_overdue
            FROM book_history bh
            JOIN books b ON bh.book_id = b.id
            JOIN book_copies bc ON bh.copy_id = bc.copy_id
            WHERE bh.user_id = ? AND bh.returned_at IS NOT NULL
            ORDER BY bh.borrowed_at DESC
        """, (session["user_id"],)).fetchall()

    # Process books for display
    book_list = []
    for book in all_books:
        book_dict = dict(book)
        book_dict["location"] = f"{book_dict.get('main_area', '')} - Rack {book_dict.get('rack_no', '')} Column {book_dict.get('column_no', '')}"
        book_dict["cover_url"] = fetch_book_cover(
            book_dict.get("title", ""),
            book_dict.get("author", "")
        )
        book_dict["status"] = "Available" if book_dict.get("available_copies", 0) > 0 else "Taken"
        book_dict["is_borrowed_by_me"] = bool(book_dict.get("my_borrowed", 0))
        book_dict["is_overdue"] = bool(book_dict.get("is_overdue", 0))
        book_dict["penalty"] = float(book_dict.get("penalty", 0))
        book_dict["my_penalty"] = float(book_dict.get("my_penalty", 0))
        book_list.append(book_dict)

    return render_template(
        "user_dashboard.html",
        books=book_list,
        current_books=current_books,
        history=history,
        search_query=search_query,
        selected_category=category
    )

@app.route("/add_book", methods=["GET", "POST"])
def add_book_route():
    if "user_id" not in session or session.get("role") not in ["admin", "librarian"]:
        flash("Access Denied! Only Admins and Librarians can add books.", "danger")
        return redirect(url_for("home"))
    if request.method == "POST":
        title = request.form.get("title")
        author = request.form.get("author")
        category = request.form.get("category")
        publication_year = request.form.get("publication_year")
        isbn = request.form.get("isbn")
        added_by = session.get("username")
        main_area = request.form.get("main_area")
        rack_no = request.form.get("rack_no")
        column_no = request.form.get("column_no")
        num_copies = int(request.form.get("num_copies", 1))

        try:
            with get_db_connection() as conn:
                cursor = conn.execute(
                    """INSERT INTO books 
                       (title, author, category, publication_year, isbn, 
                        added_by, main_area, rack_no, column_no, 
                        total_copies, available_copies)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (title, author, category, publication_year, isbn,
                     added_by, main_area, rack_no, column_no,
                     num_copies, num_copies)
                )
                book_id = cursor.lastrowid
                
                # Create individual copies
                for _ in range(num_copies):
                    conn.execute(
                        "INSERT INTO book_copies (book_id, status) VALUES (?, 'Available')",
                        (book_id,)
                    )
                
                conn.commit()
                flash("Book added successfully!", "success")
        except sqlite3.IntegrityError:
            flash("Book with this ISBN already exists!", "danger")
        
        return redirect(url_for("admin_dashboard" if session["role"] == "admin" else "librarian_dashboard"))
        
    return render_template("add_book.html")

@app.route("/update_book/<int:book_id>", methods=["GET", "POST"])
def update_book_route(book_id):
    if "user_id" not in session or session.get("role") not in ["admin", "librarian"]:
        flash("Access Denied!", "danger")
        return redirect(url_for("home"))
        
    with get_db_connection() as conn:
        book = conn.execute("""
            SELECT b.*, 
                   COUNT(bc.copy_id) as total_copies,
                   SUM(CASE WHEN bc.status = 'Available' THEN 1 ELSE 0 END) as available_copies
            FROM books b
            LEFT JOIN book_copies bc ON b.id = bc.book_id
            WHERE b.id = ?
            GROUP BY b.id
        """, (book_id,)).fetchone()
        
    if not book:
        flash("Book not found!", "danger")
        return redirect(url_for("admin_dashboard"))
        
    if request.method == "POST":
        title = request.form.get("title")
        author = request.form.get("author")
        category = request.form.get("category")
        publication_year = request.form.get("publication_year")
        isbn = request.form.get("isbn")
        num_copies = int(request.form.get("num_copies", 1))
        
        success, message = update_book(
            book_id, title, author, category, 
            publication_year, isbn, num_copies, 
            session["user_id"]
        )
        
        if success:
            flash("Book updated successfully!", "success")
        else:
            flash(f"Error: {message}", "danger")
            
        return redirect(url_for("admin_dashboard"))
        
    return render_template("update_book.html", book=book)

@app.route("/delete_book/<int:book_id>", methods=["POST"])
def delete_book_route(book_id):
    if "user_id" not in session or session.get("role") not in ["admin", "librarian"]:
        flash("Access Denied!", "danger")
        return redirect(url_for("home"))
    if delete_book(book_id):
        flash("Book deleted successfully!", "success")
    else:
        flash("Failed to delete book.", "danger")
    return redirect(url_for("admin_dashboard"))

@app.route("/take_book/<int:book_id>", methods=["POST"])
def take_book_route(book_id):
    if "user_id" not in session:
        flash("Please log in to borrow books.", "info")
        session['next'] = url_for('take_book_route', book_id=book_id)
        return redirect(url_for("login"))
        
    if session.get("role") != "user":
        flash("Only users can borrow books.", "danger")
        return redirect(url_for("home"))
        
    if borrow_book(book_id, session["user_id"]):
        flash("Book borrowed successfully!", "success")
    else:
        flash("Failed to borrow book. It may not be available.", "danger")
    
    return redirect(url_for("user_dashboard"))

@app.route("/return/<int:book_id>", methods=["POST"])
def return_book_route(book_id):
    if "user_id" not in session or session.get("role") != "user":
        flash("Access Denied!", "danger")
        return redirect(url_for("home"))
    
    success, result = return_book(book_id, session["user_id"])
    if success:
        if isinstance(result, (int, float)) and result > 0:
            flash(f"Book returned successfully! Penalty: ₹{result:.2f}", "success")
        else:
            flash("Book returned successfully!", "success")
    else:
        flash(f"Failed to return book: {result}", "danger")
    return redirect(url_for("user_dashboard"))

@app.route("/unlock_book/<int:book_id>", methods=["POST"])
def unlock_book_route(book_id):
    if "user_id" not in session or session.get("role") not in ["admin", "librarian"]:
        flash("Access Denied!", "danger")
        return redirect(url_for("home"))
        
    if unlock_book(book_id):
        flash("Book unlocked successfully!", "success")
    else:
        flash("Failed to unlock book.", "danger")
        
    if session.get("role") == "admin":
        return redirect(url_for("admin_dashboard"))
    else:
        return redirect(url_for("librarian_dashboard"))
@app.route("/force_return/<int:book_id>", methods=["POST"])
def force_return_route(book_id):
    if "user_id" not in session or session.get("role") not in ["admin", "librarian"]:
        flash("Access Denied!", "danger")
        return redirect(url_for("home"))
    
    if force_return_book(book_id, session["user_id"]):
        flash("Book force returned successfully!", "success")
    else:
        flash("Failed to force return book.", "danger")
    
    return redirect(url_for("view_book", book_id=book_id))

@app.route("/adjust_penalty/<int:book_id>", methods=["POST"])
def adjust_penalty_route(book_id):
    if "user_id" not in session or session.get("role") not in ["admin", "librarian"]:
        flash("Access Denied!", "danger")
        return redirect(url_for("home"))
    
    new_penalty = float(request.form.get("new_penalty", 0))
    if adjust_penalty(book_id, new_penalty, session["user_id"]):
        flash(f"Penalty adjusted to ₹{new_penalty:.2f}", "success")
    else:
        flash("Failed to adjust penalty.", "danger")
    
    return redirect(url_for("view_book", book_id=book_id))

@app.route("/profile", methods=["GET", "POST"])
def profile():
    if "user_id" not in session:
        flash("Please login to view your profile.", "warning")
        return redirect(url_for("login"))
        
    with get_db_connection() as conn:
        user = conn.execute("""
            SELECT u.*, 
                   COUNT(DISTINCT CASE WHEN bc.status = 'Taken' THEN bc.copy_id END) as current_books,
                   COUNT(DISTINCT bh.id) as total_borrowed,
                   COALESCE(SUM(bc.penalty), 0) as current_penalties
            FROM users u
            LEFT JOIN book_copies bc ON u.id = bc.borrowed_by
            LEFT JOIN book_history bh ON u.id = bh.user_id
            WHERE u.id = ?
            GROUP BY u.id
        """, (session["user_id"],)).fetchone()

    if request.method == "POST":
        # Update all fields
        updates = {
            "username": request.form["username"],
            "email": request.form["email"],
            "first_name": request.form.get("first_name"),
            "last_name": request.form.get("last_name"),
            "date_of_birth": request.form.get("date_of_birth"),
            "gender": request.form.get("gender"),
            "phone": request.form.get("phone"),
            "address": request.form.get("address"),
            "occupation": request.form.get("occupation"),
            "reading_interests": request.form.get("interests")
        }
        
        new_password = request.form.get("password")
        if new_password:
            updates["password"] = generate_password_hash(new_password, method="pbkdf2:sha256")

        try:
            with get_db_connection() as conn:
                query = "UPDATE users SET " + ", ".join(f"{k}=?" for k in updates.keys()) + " WHERE id=?"
                conn.execute(query, list(updates.values()) + [session["user_id"]])
                conn.commit()
                
                session["username"] = updates["username"]
                flash("Profile updated successfully!", "success")
                return redirect(url_for("profile"))
                
        except sqlite3.IntegrityError:
            flash("Username or email already exists!", "danger")

    return render_template("profile.html", user=user)

# Password Reset Routes
@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form["email"]
        username = request.form["username"]
        reason = request.form["reason"]
        
        with get_db_connection() as conn:
            user = conn.execute(
                "SELECT * FROM users WHERE email = ? AND username = ?", 
                (email, username)
            ).fetchone()
            
            if not user:
                flash("No account found with those credentials.", "danger")
                return redirect(url_for("forgot_password"))
            
            existing = conn.execute(
                "SELECT * FROM reset_requests WHERE user_id = ? AND status = 'pending'",
                (user["id"],)
            ).fetchone()
            
            if existing:
                flash("You already have a pending reset request.", "warning")
                return redirect(url_for("login"))
            
            conn.execute("""
                INSERT INTO reset_requests (user_id, username, email, reason)
                VALUES (?, ?, ?, ?)
            """, (user["id"], username, email, reason))
            conn.commit()
            
            flash("Password reset request submitted. Library staff will process it shortly.", "success")
            return redirect(url_for("login"))
                
    return render_template("forgot_password.html")

@app.route("/admin/password-requests")
@admin_librarian_required
def password_reset_requests():
    with get_db_connection() as conn:
        requests = conn.execute("""
            SELECT r.*, u.role as user_role,
                   datetime(r.requested_at) as formatted_date
            FROM reset_requests r
            JOIN users u ON r.user_id = u.id
            WHERE r.status = 'pending'
            ORDER BY r.requested_at DESC
        """).fetchall()
        
    return render_template("password_reset_requests.html", requests=requests)

@app.route("/admin/process-reset/<int:request_id>", methods=["POST"])
@admin_librarian_required
def process_reset_request(request_id):
    action = request.form.get("action")
    
    with get_db_connection() as conn:
        reset_request = conn.execute("""
            SELECT r.*, u.role as user_role 
            FROM reset_requests r
            JOIN users u ON r.user_id = u.id
            WHERE r.id = ? AND r.status = 'pending'
        """, (request_id,)).fetchone()
        
        if not reset_request:
            flash("Reset request not found or already processed.", "warning")
            return redirect(url_for("password_reset_requests"))

        if session['role'] == 'librarian' and reset_request['user_role'] != 'user':
            flash("Librarians can only process user password resets.", "danger")
            return redirect(url_for("password_reset_requests"))
            
        try:
            if action == "approve":
                temp_password = secrets.token_urlsafe(8)
                hashed_password = generate_password_hash(temp_password, method="pbkdf2:sha256")
                
                conn.execute(
                    "UPDATE users SET password = ? WHERE id = ?",
                    (hashed_password, reset_request['user_id'])
                )
                
                conn.execute("""
                    UPDATE reset_requests 
                    SET status = 'approved',
                        processed_at = CURRENT_TIMESTAMP,
                        processed_by = ?
                    WHERE id = ?
                """, (session['user_id'], request_id))
                
                conn.execute("""
                    INSERT INTO admin_logs 
                    (action, performed_by, affected_user, timestamp)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                """, ('password_reset_approved', session['user_id'], reset_request['user_id']))
                
                conn.commit()
                flash(f"Password reset approved. Temporary password: {temp_password}", "success")
                
            elif action == "deny":
                conn.execute("""
                    UPDATE reset_requests 
                    SET status = 'denied',
                        processed_at = CURRENT_TIMESTAMP,
                        processed_by = ?
                    WHERE id = ?
                """, (session['user_id'], request_id))
                
                conn.execute("""
                    INSERT INTO admin_logs 
                    (action, performed_by, affected_user, timestamp)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                """, ('password_reset_denied', session['user_id'], reset_request['user_id']))
                
                conn.commit()
                flash("Password reset request denied.", "info")
                
        except Exception as e:
            print(f"Error processing reset: {e}")
            conn.rollback()
            flash("An error occurred while processing the request.", "danger")
            
    return redirect(url_for("password_reset_requests"))

@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    if not token:
        return redirect(url_for("login"))
        
    with get_db_connection() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE reset_token = ?", 
            (token,)
        ).fetchone()
        
        if not user:
            flash("Invalid or expired reset link.", "danger")
            return redirect(url_for("login"))
            
        if request.method == "POST":
            password = request.form["password"]
            confirm_password = request.form["confirm_password"]
            
            if password != confirm_password:
                flash("Passwords do not match!", "danger")
            else:
                hashed_password = generate_password_hash(password, method="pbkdf2:sha256")
                conn.execute(
                    "UPDATE users SET password = ?, reset_token = NULL WHERE id = ?",
                    (hashed_password, user["id"])
                )
                conn.commit()
                flash("Password updated successfully!", "success")
                return redirect(url_for("login"))
                
    return render_template("reset_password.html")
@app.route("/book/<int:book_id>")
def view_book(book_id):
    with get_db_connection() as conn:
        # Get book details with current availability
        book = conn.execute("""
            SELECT b.*, 
                   COUNT(DISTINCT bc.copy_id) as total_copies,
                   SUM(CASE WHEN bc.status = 'Available' THEN 1 ELSE 0 END) as available_copies,
                   MAX(CASE WHEN bc.status = 'Taken' AND bc.borrowed_by = ? THEN 1 ELSE 0 END) as is_borrowed_by_me,
                   MAX(CASE WHEN bc.status = 'Taken' AND bc.borrowed_by = ? THEN bc.due_date END) as due_date,
                   MAX(CASE WHEN bc.status = 'Taken' AND bc.borrowed_by = ? THEN bc.penalty END) as penalty,
                   MAX(CASE WHEN bc.status = 'Taken' THEN u.username END) as borrowed_by_username
            FROM books b
            LEFT JOIN book_copies bc ON b.id = bc.book_id
            LEFT JOIN users u ON bc.borrowed_by = u.id
            WHERE b.id = ?
            GROUP BY b.id""", 
            (session.get('user_id'), session.get('user_id'), session.get('user_id'), book_id)
        ).fetchone()

        if not book:
            flash("Book not found!", "danger")
            return redirect(url_for("home"))

        book = dict(book)
        book["status"] = "Available" if book["available_copies"] > 0 else "Taken"
        book["location"] = f"{book['main_area']} - Rack {book['rack_no']} Column {book['column_no']}"

        # Get current borrowers
        current_borrowers = conn.execute("""
            SELECT u.username as borrower_name, 
                   bc.due_date, bc.penalty, bc.copy_id,
                   CASE WHEN date(bc.due_date) < date('now') THEN 1 ELSE 0 END as is_overdue,
                   CAST((julianday('now') - julianday(bc.due_date)) as INTEGER) as days_overdue
            FROM book_copies bc
            JOIN users u ON bc.borrowed_by = u.id
            WHERE bc.book_id = ? AND bc.status = 'Taken'
            ORDER BY bc.due_date""", (book_id,)).fetchall()

        # Get borrowing history
        history = conn.execute("""
            SELECT bh.*, u.username, up.username as processed_by_username
            FROM book_history bh
            JOIN users u ON bh.user_id = u.id
            LEFT JOIN users up ON bh.processed_by = up.id
            WHERE bh.book_id = ?
            ORDER BY bh.borrowed_at DESC""", (book_id,)).fetchall()

        current_date = datetime.now().strftime("%Y-%m-%d")

        return render_template(
            "book_details.html",
            book=book,
            current_borrowers=current_borrowers,
            history=history,
            current_date=current_date
        )

@app.route("/update_location/<int:book_id>", methods=["POST"])
def update_location(book_id):
    if "user_id" not in session or session.get("role") not in ["admin", "librarian"]:
        flash("Access Denied!", "danger")
        return redirect(url_for("home"))
    main_area = request.form.get("main_area")
    rack_no = request.form.get("rack_no")
    column_no = request.form.get("column_no")
    if update_book_location(book_id, main_area, rack_no, column_no, session["user_id"]):
        flash("Book location updated successfully!", "success")
    else:
        flash("Failed to update book location.", "danger")
    return redirect(url_for("view_book", book_id=book_id))

@app.route("/search")
def search():
    query = request.args.get("q", "")
    category = request.args.get("category", "")
    with get_db_connection() as conn:
        if (category):
            books = conn.execute(
                "SELECT * FROM books WHERE (title LIKE ? OR author LIKE ?) AND category = ?",
                (f"%{query}%", f"%{query}%", category)
            ).fetchall()
        else:
            books = conn.execute(
                "SELECT * FROM books WHERE title LIKE ? OR author LIKE ?",
                (f"%{query}%", f"%{query}%")
            ).fetchall()
    book_list = []
    for book in books:
        book_dict = dict(book)
        book_dict["location"] = f"{book_dict.get('main_area', '')} - Rack {book_dict.get('rack_no', '')} Column {book_dict.get('column_no', '')}"
        book_dict["cover_url"] = fetch_book_cover(
            book_dict.get("title", ""),
            book_dict.get("author", "")
        )
        book_list.append(book_dict)
    return render_template("index.html", books=book_list)

@app.route("/chatbot", methods=["POST"])
def chatbot():
    from chatbot_routes import handle_chatbot_message
    message = request.json.get("message", "")
    return handle_chatbot_message(message)

@app.route("/my-history")
def my_history():
    if "user_id" not in session:
        flash("Please login to view your history.", "warning")
        return redirect(url_for("login"))
        
    with get_db_connection() as conn:
        # Get currently borrowed books
        current_books = conn.execute("""
            SELECT b.title, bh.borrowed_at, bc.due_date, bc.penalty,
                   CASE WHEN date(bc.due_date) < date('now') THEN 1 ELSE 0 END as is_overdue
            FROM book_copies bc
            JOIN books b ON bc.book_id = b.id
            JOIN book_history bh ON bc.copy_id = bh.copy_id
            WHERE bc.borrowed_by = ? AND bc.status = 'Taken'
            ORDER BY bh.borrowed_at DESC
        """, (session["user_id"],)).fetchall()

        # Get historical records
        history = conn.execute("""
            SELECT b.title, bh.borrowed_at, bh.returned_at, bh.penalty,
                   CASE WHEN bh.returned_at > bh.due_date THEN 1 ELSE 0 END as was_overdue
            FROM book_history bh
            JOIN books b ON bh.book_id = b.id
            WHERE bh.user_id = ? AND bh.returned_at IS NOT NULL
            ORDER BY bh.borrowed_at DESC
        """, (session["user_id"],)).fetchall()

    return render_template(
        "my_history.html",
        current_books=current_books,
        history=history
    )

@app.route("/admin/reset-password", methods=["GET", "POST"])
@admin_librarian_required
def admin_reset_password():
    if request.method == "POST":
        username = request.form.get("username")
        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")

        if not all([username, new_password, confirm_password]):
            flash("All fields are required!", "danger")
            return redirect(url_for("admin_reset_password"))

        if new_password != confirm_password:
            flash("Passwords do not match!", "danger")
            return redirect(url_for("admin_reset_password"))

        try:
            with get_db_connection() as conn:
                # Check if user exists and get their current reset request if any
                user = conn.execute("""
                    SELECT u.*, r.id as request_id 
                    FROM users u 
                    LEFT JOIN reset_requests r ON u.id = r.user_id AND r.status = 'pending'
                    WHERE u.username = ?
                """, (username,)).fetchone()

                if not user:
                    flash("User not found!", "danger")
                    return redirect(url_for("admin_reset_password"))

                # Librarians can only reset regular user passwords
                if session['role'] == 'librarian' and user['role'] != 'user':
                    flash("Librarians can only reset regular user passwords!", "warning")
                    return redirect(url_for("admin_reset_password"))

                # Update password
                hashed_password = generate_password_hash(new_password, method="pbkdf2:sha256")
                conn.execute(
                    "UPDATE users SET password = ? WHERE id = ?",
                    (hashed_password, user['id'])
                )

                # Update reset request if exists
                if user['request_id']:
                    conn.execute("""
                        UPDATE reset_requests 
                        SET status = 'approved', 
                            processed_at = CURRENT_TIMESTAMP,
                            processed_by = ?
                        WHERE id = ?
                    """, (session['user_id'], user['request_id']))

                # Log the action
                conn.execute("""
                    INSERT INTO admin_logs (action, performed_by, affected_user, timestamp)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                """, ('password_reset', session['user_id'], user['id']))

                conn.commit()
                flash(f"Password reset successful for user: {username}", "success")
                return redirect(url_for('password_reset_requests'))

        except Exception as e:
            print(f"Password reset error: {e}")
            flash("An error occurred while resetting the password.", "danger")

    return render_template("admin_reset_password.html")

@app.route("/admin/create-reset-request", methods=["POST"])
@admin_librarian_required
def create_reset_request():
    username = request.form.get("username")
    email = request.form.get("email")
    reason = request.form.get("reason")
    
    with get_db_connection() as conn:
        # Verify user exists and matches email
        user = conn.execute(
            "SELECT * FROM users WHERE username = ? AND email = ?", 
            (username, email)
        ).fetchone()
        
        if not user:
            flash("No account found with those credentials.", "danger")
            return redirect(url_for("password_reset_requests"))
            
        # Check for existing pending request
        existing = conn.execute(
            "SELECT * FROM reset_requests WHERE user_id = ? AND status = 'pending'",
            (user["id"],)
        ).fetchone()
        
        if existing:
            flash("User already has a pending reset request.", "warning")
            return redirect(url_for("password_reset_requests"))
        
        try:
            # Create reset request
            conn.execute("""
                INSERT INTO reset_requests 
                (user_id, username, email, reason, status, requested_at)
                VALUES (?, ?, ?, ?, 'pending', CURRENT_TIMESTAMP)
            """, (user["id"], username, email, reason))
            
            # Log the action
            conn.execute("""
                INSERT INTO admin_logs 
                (action, performed_by, affected_user, timestamp)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """, ('reset_request_created', session['user_id'], user["id"]))
            
            conn.commit()
            flash("Password reset request created successfully.", "success")
            
        except Exception as e:
            print(f"Error creating reset request: {e}")
            conn.rollback()
            flash("Error creating reset request.", "danger")
    
    return redirect(url_for("password_reset_requests"))

if __name__ == "__main__":
    app.run(debug=True)