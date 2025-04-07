import sqlite3
import requests
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from flask import jsonify

from book import update_book_location, borrow_book, return_book, get_book_history, add_book, update_book, delete_book, unlock_book

app = Flask(__name__)
app.secret_key = "supersecretkey"
DATABASE = "library.db"

# Helper function to get a database connection
def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# Initialize the database
def init_db():
    with get_db_connection() as conn:
        # Create the 'book_history' table
        conn.execute("""
        CREATE TABLE IF NOT EXISTS book_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            borrowed_at DATETIME NOT NULL,
            returned_at DATETIME DEFAULT NULL,
            penalty INTEGER DEFAULT 0,
            FOREIGN KEY (book_id) REFERENCES books (id),
            FOREIGN KEY (user_id) REFERENCES users (id)
        );
        """)
init_db()

def fetch_book_cover(isbn):
    """Fetch the book cover image URL using Open Library API."""
    try:
        # Open Library API URL for book covers
        cover_url = f"https://covers.openlibrary.org/b/isbn/{isbn}-L.jpg"
        
        # Check if the cover image exists
        response = requests.get(cover_url)
        if response.status_code == 200:
            return cover_url  # Return the cover image URL
        else:
            # Return a placeholder image if no cover is found
            return "https://via.placeholder.com/150?text=No+Cover+Available"
    except Exception as e:
        print(f"Error fetching book cover: {e}")
        # Return a placeholder image in case of an error
        return "https://via.placeholder.com/150?text=Error"

@app.route("/")
def home():
    with get_db_connection() as conn:
        books = conn.execute("SELECT * FROM books").fetchall()
    return render_template("index.html", books=books)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]
        role = request.form["role"]

        hashed_password = generate_password_hash(password, method="pbkdf2:sha256")
        try:
            with get_db_connection() as conn:
                conn.execute(
                    "INSERT INTO users (username, email, password, role) VALUES (?, ?, ?, ?)",
                    (username, email, hashed_password, role),
                )
            flash("Registration successful! Please log in.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Username or email already exists!", "danger")
            return redirect(url_for("register"))

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        with get_db_connection() as conn:
            user = conn.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            flash(f"Welcome, {user['username']}!", "success")

            # Redirect based on role
            if user["role"] == "admin":
                return redirect(url_for("admin_dashboard"))
            elif user["role"] == "librarian":
                return redirect(url_for("librarian_dashboard"))
            else:
                return redirect(url_for("user_dashboard"))

        flash("Invalid credentials, try again!", "danger")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("home"))

@app.route("/admin")
def admin_dashboard():
    """Admin Dashboard"""
    if "user_id" not in session or session.get("role") != "admin":
        flash("Access Denied! Only Admins can access this page.", "danger")
        return redirect(url_for("home"))

    with get_db_connection() as conn:
        books = conn.execute("SELECT * FROM books").fetchall()
        users = conn.execute("SELECT * FROM users").fetchall()
    return render_template("admin_dashboard.html", books=books, users=users)


@app.route("/librarian")
def librarian_dashboard():
    """Librarian Dashboard"""
    if "user_id" not in session or session.get("role") != "librarian":
        flash("Access Denied! Only Librarians can access this page.", "danger")
        return redirect(url_for("home"))

    with get_db_connection() as conn:
        books = conn.execute("SELECT * FROM books").fetchall()
    return render_template("librarian_dashboard.html", books=books)

@app.route("/user")
def user_dashboard():
    with get_db_connection() as conn:
        books = conn.execute("SELECT * FROM books").fetchall()
    return render_template("user_dashboard.html", books=books)

@app.route("/add_book", methods=["GET", "POST"])
def add_book_route():
    """Route to add a new book."""
    if "user_id" not in session or session.get("role") not in ["admin", "librarian"]:
        flash("Access Denied! Only Admins and Librarians can add books.", "danger")
        return redirect(url_for("home"))

    if request.method == "POST":
        title = request.form.get("title")
        author = request.form.get("author")
        genre = request.form.get("genre")
        publication_year = request.form.get("publication_year")
        isbn = request.form.get("isbn")
        added_by = session.get("username")

        if add_book(title, author, genre, publication_year, isbn, added_by):
            flash("Book added successfully!", "success")
        else:
            flash("Error: Book with the same ISBN already exists.", "danger")

        return redirect(url_for("admin_dashboard"))

    return render_template("add_book.html")

@app.route("/update_book/<int:book_id>", methods=["GET", "POST"])
def update_book_route(book_id):
    """Route to update an existing book."""
    if "user_id" not in session or session.get("role") not in ["admin", "librarian"]:
        flash("Access Denied! Only Admins and Librarians can update books.", "danger")
        return redirect(url_for("home"))

    with get_db_connection() as conn:
        book = conn.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()

    if not book:
        flash("Book not found!", "danger")
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
        title = request.form.get("title")
        author = request.form.get("author")
        genre = request.form.get("genre")
        publication_year = request.form.get("publication_year")
        isbn = request.form.get("isbn")

        if update_book(book_id, title, author, genre, publication_year, isbn):
            flash("Book updated successfully!", "success")
        else:
            flash("Error: Book with the same ISBN already exists.", "danger")

        return redirect(url_for("admin_dashboard"))

    return render_template("update_book.html", book=book)

@app.route("/delete_book/<int:book_id>", methods=["POST"])
def delete_book_route(book_id):
    """Route to delete a book."""
    if "user_id" not in session or session.get("role") not in ["admin", "librarian"]:
        flash("Access Denied! Only Admins and Librarians can delete books.", "danger")
        return redirect(url_for("home"))

    if delete_book(book_id):
        flash("Book deleted successfully!", "success")
    else:
        flash("Failed to delete book.", "danger")

    return redirect(url_for("admin_dashboard"))

@app.route("/take_book/<int:book_id>", methods=["POST"])
def take_book_route(book_id):
    """Route to allow a user to take a book."""
    if "user_id" not in session or session.get("role") != "user":
        flash("Access Denied! Only Users can borrow books.", "danger")
        return redirect(url_for("home"))

    with get_db_connection() as conn:
        book = conn.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()

        if not book:
            flash("Book not found!", "danger")
            return redirect(url_for("user_dashboard"))

    if borrow_book(book_id, session["user_id"]):
        flash("Book borrowed successfully! Return within 5 days.", "success")
    else:
        flash("Failed to borrow book.", "danger")

    return redirect(url_for("user_dashboard"))

@app.route("/unlock_book/<int:book_id>", methods=["POST"])
def unlock_book_route(book_id):
    """Route to unlock a book."""
    if "user_id" not in session or session.get("role") not in ["admin", "librarian"]:
        flash("Access Denied! Only Admins and Librarians can unlock books.", "danger")
        return redirect(url_for("home"))

    if unlock_book(book_id):
        flash("Book unlocked successfully!", "success")
    else:
        flash("Failed to unlock book.", "danger")

    return redirect(url_for("admin_dashboard") if session.get("role") == "admin" else url_for("librarian_dashboard"))

@app.route("/profile", methods=["GET", "POST"])
def profile():
    if "user_id" not in session:
        flash("Please log in to access your profile.", "danger")
        return redirect(url_for("login"))

    with get_db_connection() as conn:
        user = conn.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()

    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]

        try:
            with get_db_connection() as conn:
                if password:
                    hashed_password = generate_password_hash(password, method="pbkdf2:sha256")
                    conn.execute(
                        "UPDATE users SET username = ?, email = ?, password = ? WHERE id = ?",
                        (username, email, hashed_password, session["user_id"]),
                    )
                else:
                    conn.execute(
                        "UPDATE users SET username = ?, email = ? WHERE id = ?",
                        (username, email, session["user_id"]),
                    )
                flash("Profile updated successfully!", "success")
        except sqlite3.IntegrityError:
            flash("Username or email already exists!", "danger")
        except Exception as e:
            flash(f"An error occurred: {e}", "danger")

        return redirect(url_for("profile"))

    return render_template("profile.html", user=user)

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

@app.route("/update_location/<int:book_id>", methods=["POST"])
def update_location(book_id):
    """Update the location of a book."""
    if "user_id" not in session or session.get("role") not in ["admin", "librarian"]:
        flash("Access Denied!", "danger")
        return redirect(url_for("home"))
    location = request.form.get("location")
    if update_book_location(book_id, location):
        flash("Book location updated successfully!", "success")
    else:
        flash("Failed to update book location.", "danger")
    return redirect(url_for("view_book", book_id=book_id))

@app.route("/borrow/<int:book_id>", methods=["POST"])
def borrow_book_route(book_id):
    """Borrow a book."""
    if "user_id" not in session or session.get("role") != "user":
        flash("Access Denied!", "danger")
        return redirect(url_for("home"))
    if borrow_book(book_id, session["user_id"]):
        flash("Book borrowed successfully! Return within 5 days.", "success")
    else:
        flash("Failed to borrow book.", "danger")
    return redirect(url_for("user_dashboard"))

@app.route("/return/<int:book_id>", methods=["POST"])
def return_book_route(book_id):
    """Return a book."""
    if "user_id" not in session or session.get("role") != "user":
        flash("Access Denied!", "danger")
        return redirect(url_for("home"))

    penalty = return_book(book_id, session["user_id"])
    if penalty is not None:
        flash(f"Book returned successfully! Penalty: ${penalty}", "success")
    else:
        flash("Failed to return book.", "danger")

    return redirect(url_for("user_dashboard"))

if __name__ == "__main__":
    app.run(debug=True)