import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

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
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user'
        );

        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            genre TEXT NOT NULL,
            publication_year INTEGER NOT NULL,
            isbn TEXT UNIQUE NOT NULL,
            status TEXT NOT NULL DEFAULT 'Available',
            added_by TEXT NOT NULL
        );
        """)
init_db()

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

        try:
            with get_db_connection() as conn:
                conn.execute(
                    "INSERT INTO books (title, author, genre, publication_year, isbn, added_by) VALUES (?, ?, ?, ?, ?, ?)",
                    (title, author, genre, publication_year, isbn, added_by),
                )
            flash("Book added successfully!", "success")
        except sqlite3.IntegrityError:
            flash("Error: Book with the same ISBN already exists.", "danger")
        except Exception as e:
            flash(f"An error occurred: {e}", "danger")

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

        try:
            with get_db_connection() as conn:
                conn.execute(
                    "UPDATE books SET title = ?, author = ?, genre = ?, publication_year = ?, isbn = ? WHERE id = ?",
                    (title, author, genre, publication_year, isbn, book_id),
                )
            flash("Book updated successfully!", "success")
            return redirect(url_for("admin_dashboard"))
        except sqlite3.IntegrityError:
            flash("Error: Book with the same ISBN already exists.", "danger")
        except Exception as e:
            flash(f"An error occurred: {e}", "danger")

    return render_template("update_book.html", book=book)

@app.route("/delete_book/<int:book_id>", methods=["POST"])
def delete_book_route(book_id):
    """Route to delete a book."""
    if "user_id" not in session or session.get("role") not in ["admin", "librarian"]:
        flash("Access Denied! Only Admins and Librarians can delete books.", "danger")
        return redirect(url_for("home"))

    try:
        with get_db_connection() as conn:
            conn.execute("DELETE FROM books WHERE id = ?", (book_id,))
        flash("Book deleted successfully!", "success")
    except Exception as e:
        flash(f"An error occurred while deleting the book: {e}", "danger")

    return redirect(url_for("librarian_dashboard") if session.get("role") == "librarian" else url_for("admin_dashboard"))

@app.route("/take_book/<int:book_id>", methods=["POST"])
def take_book_route(book_id):
    """Route to allow a user to take a book."""
    if "user_id" not in session or session.get("role") != "user":
        flash("Access Denied! Only Users can take books.", "danger")
        return redirect(url_for("home"))

    with get_db_connection() as conn:
        book = conn.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()

        if not book:
            flash("Book not found!", "danger")
            return redirect(url_for("user_dashboard"))

        if book["status"] == "Available":
            try:
                conn.execute("UPDATE books SET status = 'Taken' WHERE id = ?", (book_id,))
                flash("Book taken successfully!", "success")
            except Exception as e:
                flash(f"An error occurred while taking the book: {e}", "danger")
        else:
            flash("Book is not available.", "danger")

    return redirect(url_for("user_dashboard"))

@app.route("/unlock_book/<int:book_id>", methods=["POST"])
def unlock_book_route(book_id):
    """Route to unlock a book by setting its status back to 'Available'."""
    if "user_id" not in session or session.get("role") not in ["admin", "librarian"]:
        flash("Access Denied! Only Admins and Librarians can unlock books.", "danger")
        return redirect(url_for("home"))

    with get_db_connection() as conn:
        book = conn.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()

        if not book:
            flash("Book not found!", "danger")
            return redirect(url_for("admin_dashboard"))

        if book["status"] == "Taken":
            try:
                conn.execute("UPDATE books SET status = 'Available' WHERE id = ?", (book_id,))
                flash("Book unlocked successfully!", "success")
            except Exception as e:
                flash(f"An error occurred while unlocking the book: {e}", "danger")
        else:
            flash("Book is already available.", "info")

    return redirect(url_for("admin_dashboard") if session.get("role") == "admin" else url_for("librarian_dashboard"))

if __name__ == "__main__":
    app.run(debug=True)