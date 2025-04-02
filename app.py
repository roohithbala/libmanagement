from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
app = Flask(__name__)
app.secret_key = "supersecretkey"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///library.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="user")

class Book(db.Model):
    __tablename__ = "books"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    author = db.Column(db.String(100), nullable=False)
    genre = db.Column(db.String(100), nullable=False)
    publication_year = db.Column(db.Integer, nullable=False)
    isbn = db.Column(db.String(100), unique=True, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="Available")
    added_by = db.Column(db.String(100), nullable=False)

with app.app_context():
    db.create_all()

def add_book(title, author, genre, publication_year, isbn, added_by):
    try:
        if Book.query.filter_by(isbn=isbn).first():
            return False
        new_book = Book(title=title, author=author, genre=genre, publication_year=int(publication_year), isbn=isbn, added_by=added_by)
        db.session.add(new_book)
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        return False

def get_all_books():
    return Book.query.all()

def delete_book(book_id):
    try:
        book = Book.query.get(book_id)
        if book:
            db.session.delete(book)
            db.session.commit()
            return True
        return False
    except Exception as e:
        db.session.rollback()
        return False

@app.route("/")
def home():
    books = get_all_books()
    return render_template("index.html", books=books)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]
        role = request.form["role"]

        if User.query.filter_by(username=username).first():
            flash("Username already exists!", "danger")
            return redirect(url_for("register"))
        if User.query.filter_by(email=email).first():
            flash("Email already exists!", "danger")
            return redirect(url_for("register"))
        try:
            hashed_password = generate_password_hash(password, method="pbkdf2:sha256")
            new_user = User(username=username, email=email, password=hashed_password, role=role)
            db.session.add(new_user)
            db.session.commit()

            flash("Registration successful! Please log in.", "success")
            return redirect(url_for("login"))
        except Exception as e:
            db.session.rollback()
            flash("An error occurred during registration. Please try again.", "danger")
            return redirect(url_for("register"))

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            session["user_id"] = user.id
            session["username"] = user.username
            session["role"] = user.role
            flash(f"Welcome, {user.username}!", "success")
            return redirect(url_for(f"{user.role}_dashboard"))

        flash("Invalid credentials, try again!", "danger")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("home"))

@app.route("/add_book", methods=["GET", "POST"])
def add_book_route():
    if "user_id" not in session or session.get("role") not in ["admin", "librarian"]:
        flash("Access Denied!", "danger")
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
            flash("Failed to add book.", "danger")
        return redirect(url_for("home"))
    return render_template("add_book.html")

@app.route("/delete_book/<int:book_id>")
def delete_book_route(book_id):
    if "user_id" not in session or session.get("role") not in ["admin", "librarian"]:
        flash("Access Denied!", "danger")
        return redirect(url_for("home"))
    delete_book(book_id)
    flash("Book deleted successfully!", "success")
    return redirect(url_for("home"))

@app.route("/admin")
def admin_dashboard():
    return render_template("admin_dashboard.html", books=get_all_books(), users=User.query.all())

@app.route("/update_book/<int:book_id>", methods=["GET", "POST"])
def update_book_route(book_id):
    if "user_id" not in session or session.get("role") not in ["admin", "librarian"]:
        flash("Access Denied!", "danger")
        return redirect(url_for("home"))

    book = Book.query.get_or_404(book_id)

    if request.method == "POST":
        book.title = request.form["title"]
        book.author = request.form["author"]
        book.genre = request.form["genre"]
        book.publication_year = request.form["publication_year"]
        book.isbn = request.form["isbn"]

        try:
            db.session.commit()
            flash("Book updated successfully!", "success")

            # Redirect based on user role
            if session.get("role") == "admin":
                return redirect(url_for("admin_dashboard"))
            elif session.get("role") == "librarian":
                return redirect(url_for("librarian_dashboard"))
        
        except Exception:
            db.session.rollback()
            flash("Error updating book!", "danger")

    return render_template("update_book.html", book=book)

@app.route("/librarian")
def librarian_dashboard():
    return render_template("librarian_dashboard.html", books=get_all_books())

@app.route("/user")
def user_dashboard():
    return render_template("user_dashboard.html", books=get_all_books())

@app.route("/take_book/<int:book_id>", methods=["POST"])
def take_book_route(book_id):
    """Allow a user to take a book if it is available."""
    if "user_id" not in session:
        flash("Please log in to take a book.", "danger")
        return redirect(url_for("login"))

    book = Book.query.get(book_id)
    if book and book.status == "Available":
        try:
            book.status = "Taken"
            db.session.commit()
            flash("Book taken successfully!", "success")
        except Exception as e:
            db.session.rollback()
            flash("Error taking book. Please try again.", "danger")
    else:
        flash("Book is not available.", "danger")

    return redirect(url_for("user_dashboard"))

@app.route("/unlock_book/<int:book_id>", methods=["POST"])
def unlock_book_route(book_id):
    """Unlock a book by setting its status back to 'Available'."""
    if "user_id" not in session or session.get("role") not in ["admin", "librarian"]:
        flash("Access Denied!", "danger")
        return redirect(url_for("home"))

    book = Book.query.get(book_id)
    if book and book.status == "Taken":
        try:
            book.status = "Available"
            db.session.commit()
            flash("Book unlocked successfully!", "success")
        except Exception as e:
            db.session.rollback()
            flash("Error unlocking book. Please try again.", "danger")
    else:
        flash("Book is already available or does not exist.", "danger")

    if session.get("role") == "admin":
        return redirect(url_for("admin_dashboard"))
    elif session.get("role") == "librarian":
        return redirect(url_for("librarian_dashboard"))

if __name__ == "__main__":
    app.run(debug=True)