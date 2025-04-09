from datetime import datetime
import sqlite3

class LibraryChatbot:
    def __init__(self, db_path):
        self.db_path = db_path
        self.context = {}
        
    def get_db_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_book_details(self, book):
        """Format book details for display with clickable link"""
        status_badge = "🟢 Available" if book['status'] == 'Available' else "🔴 Taken"
        location = f"{book['main_area']} - Rack {book['rack_no']}, Column {book['column_no']}"
        details = (
            f"📚 {book['title']}\n"
            f"👤 by {book['author']}\n"
            f"📂 Category: {book['category']}\n"
            f"📍 Location: {location}\n"
            f"Status: {status_badge}\n"
        )
        if book['status'] == 'Available':
            details += f"\n<a href='/book/{book['id']}' class='btn btn-primary btn-sm'>Borrow this book</a>"
        return details

    def process_query(self, query, user_id):
        query = query.lower().strip()
        response = {
            "type": "text",
            "message": "",
            "suggestions": []
        }

        try:
            # Handle "my books" query
            if "my books" in query or "borrowed books" in query:
                with self.get_db_connection() as conn:
                    books = conn.execute("""
                        SELECT b.*, u.username 
                        FROM books b 
                        JOIN users u ON b.borrowed_by = u.id 
                        WHERE b.borrowed_by = ?
                        """, (user_id,)).fetchall()
                    
                    if books:
                        response["type"] = "borrowed_books"
                        response["message"] = "📚 Your borrowed books:\n\n"
                        for book in books:
                            due_date = book['due_date'] or "No due date"
                            penalty = f"₹{book['penalty']}" if book['penalty'] > 0 else "No penalty"
                            response["message"] += (
                                f"📖 {book['title']}\n"
                                f"Due: {due_date}\n"
                                f"Penalty: {penalty}\n"
                                f"Location: {book['main_area']} - Rack {book['rack_no']}\n\n"
                            )
                    else:
                        response["message"] = "You haven't borrowed any books yet."
                    
                    response["suggestions"] = [
                        "Find a book",
                        "Check due dates",
                        "Search by category"
                    ]

            # Handle book search
            elif "find" in query or "search" in query:
                # Remove search keywords and clean the query
                search_terms = query.replace("find", "").replace("search", "").replace("a book", "").replace("book", "").strip()
                
                if not search_terms:  # Empty search terms
                    response["type"] = "search_prompt"
                    response["message"] = "What kind of book are you looking for? You can search by:\n- Title (e.g., 'find Harry Potter')\n- Author (e.g., 'find books by Rowling')\n- Category (e.g., 'find Science books')"
                    response["suggestions"] = [
                        "Search Science books",
                        "Search Fiction books",
                        "Search Mystery books"
                    ]
                    return response

                with self.get_db_connection() as conn:
                    # First try exact matches
                    books = conn.execute("""
                        SELECT * FROM books 
                        WHERE LOWER(title) LIKE ? 
                        OR LOWER(author) LIKE ? 
                        OR LOWER(category) = ?
                        LIMIT 5
                        """, 
                        (f"%{search_terms}%", f"%{search_terms}%", search_terms)
                    ).fetchall()
                    
                    if books:
                        response["type"] = "search_results"
                        response["message"] = f"📚 Found {len(books)} books matching '{search_terms}':\n\n"
                        for book in books:
                            response["message"] += self.get_book_details(book) + "\n\n"
                        response["suggestions"] = [
                            "Search another book",
                            "Show my books",
                            f"Find more {search_terms} books"
                        ]
                    else:
                        response["message"] = (
                            f"No books found matching '{search_terms}'\n\n"
                            "Try:\n"
                            "- Using more specific terms\n"
                            "- Searching by category (e.g., 'find Science books')\n"
                            "- Searching by author (e.g., 'find books by [author name]')"
                        )
                        response["suggestions"] = [
                            "Show all categories",
                            "Search by author",
                            "Show available books"
                        ]

            # Handle location query
            elif "where" in query or "location" in query:
                if "book_id" in self.context:
                    with self.get_db_connection() as conn:
                        book = conn.execute(
                            "SELECT * FROM books WHERE id = ?",
                            (self.context["book_id"],)
                        ).fetchone()
                        if book:
                            response["message"] = (
                                f"📍 Location for '{book['title']}':\n"
                                f"Area: {book['main_area']}\n"
                                f"Rack: {book['rack_no']}\n"
                                f"Column: {book['column_no']}"
                            )
                        else:
                            response["message"] = "Book not found."
                else:
                    response["message"] = "Which book's location do you want to know? Try searching for a book first."
                    response["suggestions"] = ["Find a book"]

            else:
                response["message"] = (
                    "Hi! I can help you with:\n"
                    "📚 Finding books\n"
                    "📖 Checking your borrowed books\n"
                    "📍 Finding book locations\n"
                    "\nWhat would you like to do?"
                )
                response["suggestions"] = [
                    "Find a book",
                    "Show my books",
                    "Check locations"
                ]

            return response

        except Exception as e:
            print(f"Error processing query: {e}")
            return {
                "type": "text",
                "message": "Sorry, I encountered an error. Please try again.",
                "suggestions": ["Find a book", "Show my books"]
            }