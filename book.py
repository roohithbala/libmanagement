from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

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

def add_book(title, author, genre, publication_year, isbn, added_by):
    try:
        if Book.query.filter_by(isbn=isbn).first():
            print(" Error: Book with ISBN already exists.")
            return False
        
        new_book = Book(
            title=title,
            author=author,
            genre=genre,
            publication_year=int(publication_year),
            isbn=isbn,
            added_by=added_by
        )
        db.session.add(new_book)
        db.session.commit()
        print("Book added successfully!")
        return True
    except Exception as e:
        print(f"Error adding book: {e}")
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
        print(f" Error deleting book: {e}")
        db.session.rollback()
        return False
