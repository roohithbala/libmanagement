from datetime import datetime, timedelta
import sqlite3
import re
from typing import Dict, List, Any, Optional
from collections import defaultdict
from fuzzywuzzy import fuzz

class LibraryChatbot:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.context: Dict[str, Any] = {}
        self.user_sessions: Dict[int, Dict[str, Any]] = defaultdict(dict)
        
        # Enhanced intent patterns
        self.intents = {
            'greet': r'\b(hi|hello|hey|good\s*(morning|afternoon|evening)|namaste|welcome|howdy|hola)\b',
            'find_book': r'\b(find|search|look\s*for|get|where\s*is|show|available)\b.*?\b(book|books|copy|copies|title|read)\b',
            'my_books': r'\b(my|borrowed|checked\s*out|current|active)\s*(book|books|borrowing|items)\b',
            'due_dates': r'\b(due|return|deadline|when|dates|overdue)\b',
            'location': r'\b(where|location|place|shelf|rack|section|area)\b',
            'help': r'\b(help|assist|support|guide|how|what|explain)\b',
            'categories': r'\b(categories|genres|types|subjects|topics)\b',
            'penalties': r'\b(penalty|penalties|fine|fines|charges|overdue|payment|fee|fees)\b',
            'recommend': r'\b(recommend|suggest|similar|like|related)\b'
        }

    def get_db_connection(self) -> sqlite3.Connection:
        """Get database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def detect_intent_and_entities(self, query: str) -> Dict[str, Any]:
        """Detect the user's intent and extract entities from the query."""
        query = query.lower().strip()

        # Intent detection
        if re.search(r'\b(find|search|look\s*for|get|show|available)\b', query):
            intent = 'search_books'
        elif re.search(r'\b(categories|genres|types|subjects|topics)\b', query):
            intent = 'list_categories'
        else:
            intent = 'unknown'

        # Entity extraction
        title_match = re.search(r'"([^"]+)"', query)  # Extract text in quotes
        category_match = re.search(r'\b(fiction|non-fiction|science|history|biography|children|mystery|fantasy|romance|others)\b', query)
        author_match = re.search(r'by\s+([\w\s]+)', query)

        entities = {
            'title': title_match.group(1) if title_match else None,
            'category': category_match.group(0) if category_match else None,
            'author': author_match.group(1) if author_match else None
        }

        return {'intent': intent, 'entities': entities}

    def search_books(self, title: str = None, category: str = None, author: str = None) -> Dict[str, Any]:
        """Search for books based on title, category, or author."""
        try:
            with self.get_db_connection() as conn:
                query = """
                    SELECT 
                        title, 
                        author, 
                        category, 
                        main_area, 
                        rack_no, 
                        column_no, 
                        available_copies 
                    FROM books 
                    WHERE 1=1
                """
                params = []

                # Improved title search
                if title:
                    query += """ AND (
                        LOWER(title) LIKE ? 
                        OR LOWER(title) LIKE ?
                        OR LOWER(author) LIKE ?
                    )"""
                    search_term = f"%{title.lower()}%"
                    params.extend([search_term, f"%{title.lower().replace(' ', '%')}%", search_term])
                
                # Category search
                if category:
                    query += " AND LOWER(category) = ?"
                    params.append(category.lower())

                books = conn.execute(query, params).fetchall()

                if not books:
                    return {
                        "type": "not_found",
                        "message": (
                            "# No Books Found\n\n"
                            f"I couldn't find any books matching '{title or category}'.\n\n"
                            "## Suggestions:\n"
                            "- Try different keywords\n"
                            "- Check the spelling\n"
                            "- Browse by category\n"
                        ),
                        "suggestions": ["Show categories", "Popular books", "Help"]
                    }

                message = "# Search Results\n\n"
                for book in books:
                    status = "🟢 Available" if book["available_copies"] > 0 else "🔴 Not Available"
                    message += (
                        f"## {book['title']}\n"
                        f"**Author**: {book['author']}\n"
                        f"**Category**: {book['category']}\n"
                        f"**Location**: {book['main_area']} - Rack {book['rack_no']}, Column {book['column_no']}\n"
                        f"**Status**: {status}\n\n"
                        "---\n\n"
                    )

                return {
                    "type": "books",
                    "message": message,
                    "suggestions": ["Search again", "Show categories", "Popular books"]
                }

        except Exception as e:
            print(f"Error searching books: {e}")
            return {
                "type": "error",
                "message": "Sorry, I couldn't search for books. Please try again.",
                "suggestions": ["Show categories", "Help"]
            }

    def list_categories(self) -> Dict[str, Any]:
        """List all available book categories."""
        try:
            with self.get_db_connection() as conn:
                categories = conn.execute("""
                    SELECT category, COUNT(*) as count 
                    FROM books 
                    GROUP BY category
                    ORDER BY count DESC
                """).fetchall()

                if not categories:
                    return {
                        "type": "not_found",
                        "message": "No categories found in the library.",
                        "suggestions": []
                    }

                message = "📚 Available Categories:\n\n"
                for cat in categories:
                    message += f"🏷️ {cat['category']} ({cat['count']} books)\n"

                return {
                    "type": "categories",
                    "message": message,
                    "suggestions": ["Search books in Fiction", "Search books in Science"]
                }

        except Exception as e:
            print(f"Error listing categories: {e}")
            return {
                "type": "error",
                "message": "An error occurred while fetching categories. Please try again later.",
                "suggestions": []
            }

    def detect_intent(self, query: str) -> str:
        """Detect the user's intent from the query."""
        query = query.lower().strip()
        for intent, pattern in self.intents.items():
            if re.search(pattern, query):
                return intent
        return 'unknown'

    def format_book_details(self, book: Dict[str, Any]) -> str:
        """Format book details with rich formatting and emojis."""
        status = "Available" if book.get('available_copies', 0) > 0 else "Borrowed"
        status_emoji = "🟢" if status == "Available" else "🔴"
        
        details = [
            f"📚 *{book['title']}*",
            f"✍️ by _{book['author']}_",
            f"🏷️ {book['category']}",
            f"📍 {book['main_area']} - Rack {book['rack_no']}, Column {book['column_no']}",
            f"{status_emoji} {status}"
        ]

        if book.get('due_date'):
            due_date = datetime.strptime(book['due_date'], "%Y-%m-%d")
            days_remaining = (due_date - datetime.now()).days
            details.append(f"📅 Due in {days_remaining} days")
            if days_remaining < 0:
                details.append(f"⚠️ Overdue by {abs(days_remaining)} days!")

        return "\n".join(details)

    def get_recommendations(self, user_id: int) -> List[Dict[str, Any]]:
        """Get personalized book recommendations based on user's history."""
        try:
            with self.get_db_connection() as conn:
                # Get user's reading history
                history = conn.execute("""
                    SELECT b.category, COUNT(*) as count
                    FROM book_history bh
                    JOIN books b ON bh.book_id = b.id
                    WHERE bh.user_id = ?
                    GROUP BY b.category
                    ORDER BY count DESC
                    LIMIT 3
                """, (user_id,)).fetchall()

                if not history:
                    return []

                # Get recommended books based on preferred categories
                preferred_categories = [h['category'] for h in history]
                placeholders = ','.join('?' * len(preferred_categories))
                
                recommendations = conn.execute(f"""
                    SELECT b.*, 
                           COUNT(DISTINCT bc.copy_id) as total_copies,
                           SUM(CASE WHEN bc.status = 'Available' THEN 1 ELSE 0 END) as available_copies
                    FROM books b
                    LEFT JOIN book_copies bc ON b.id = bc.book_id
                    WHERE b.category IN ({placeholders})
                    AND b.id NOT IN (
                        SELECT book_id 
                        FROM book_history 
                        WHERE user_id = ?
                    )
                    AND available_copies > 0
                    GROUP BY b.id
                    LIMIT 5
                """, (*preferred_categories, user_id)).fetchall()

                return [dict(r) for r in recommendations]

        except Exception as e:
            print(f"Error getting recommendations: {e}")
            return []

    def handle_unknown(self, query: str, user_id: int) -> Dict[str, Any]:
        """Handle unknown queries with helpful suggestions."""
        return {
            "type": "help",
            "message": (
                "I'm not sure what you're looking for. Here are some things you can try:\n\n"
                "• Search for books by saying 'find [book title]'\n"
                "• Browse categories by saying 'show categories'\n"
                "• Get help by saying 'help'\n"
                "\nOr click one of the suggestions below:"
            ),
            "suggestions": [
                "Show all categories",

                "Help"
            ]
        }

    def handle_help(self, query: str, user_id: int) -> Dict[str, Any]:
        return {
            "type": "help",
            "message": (
                "Here's what I can do for you:\n\n"
                "1️⃣ Find books: 'find python books'\n"
                "2️⃣ Check your books: 'show my books'\n"
                "3️⃣ Browse categories: 'show categories'\n"
                "4️⃣ Check penalties: 'show my fines'\n"
                "5️⃣ Find locations: 'where is book id 5'\n"
                "\nJust type what you need!"
            ),
            "suggestions": ["Find a book", "My books", "Show categories"]
        }

    def handle_categories(self, query: str, user_id: int) -> Dict[str, Any]:
        """Handle category listing with markdown formatting."""
        try:
            with self.get_db_connection() as conn:
                # Get categories with book counts and available copies
                categories = conn.execute("""
                    SELECT 
                        category,
                        COUNT(*) as total_books,
                        SUM(CASE WHEN available_copies > 0 THEN 1 ELSE 0 END) as available_books
                    FROM books 
                    GROUP BY category
                """).fetchall()

                if not categories:
                    return {
                        "type": "categories",
                        "message": "No categories found in the library system.",
                        "suggestions": ["Help"]
                    }

                message = "# Library Categories\n\n"
                suggestions = []

                for cat in categories:
                    message += (
                        f"## {cat['category']}\n"
                        f"📚 Total Books: {cat['total_books']}\n"
                        f"🟢 Available: {cat['available_books']}\n\n"
                    )
                    suggestions.append(f"Search {cat['category']} books")

                return {
                    "type": "categories",
                    "message": message,
                    "suggestions": suggestions[:3]  # Limit to top 3 suggestions
                }

        except Exception as e:
            print(f"Error fetching categories: {e}")
            return {
                "type": "error",
                "message": "Sorry, I couldn't fetch the categories. Please try again.",
                "suggestions": ["Help"]
            }

    def handle_find_book(self, query: str, user_id: int) -> Dict[str, Any]:
        """Handle book search queries."""
        try:
            # Extract search terms
            search_terms = re.sub(
                r'\b(find|search|book|books|for|me|the|a|an)\b', 
                '', 
                query
            ).strip()

            if not search_terms:
                return {
                    "type": "prompt",
                    "message": "What kind of book are you looking for? You can search by:\n\n"
                               "📖 Title (e.g., 'Harry Potter')\n"
                               "✍️ Author (e.g., 'books by Rowling')\n"
                               "🏷️ Category (e.g., 'Science books')",
                    "suggestions": ["Fiction books", "Science books", "Show categories"]
                }

            with self.get_db_connection() as conn:
                # Enhanced search query with fuzzy matching
                books = conn.execute("""
                    SELECT b.*, 
                           COUNT(DISTINCT bc.copy_id) as total_copies,
                           SUM(CASE WHEN bc.status = 'Available' THEN 1 ELSE 0 END) as available_copies
                    FROM books b
                    LEFT JOIN book_copies bc ON b.id = bc.book_id
                    GROUP BY b.id
                """).fetchall()

                # Fuzzy match search terms
                matched_books = [
                    book for book in books
                    if fuzz.partial_ratio(search_terms.lower(), book['title'].lower()) > 60
                    or fuzz.partial_ratio(search_terms.lower(), book['author'].lower()) > 60
                    or fuzz.partial_ratio(search_terms.lower(), book['category'].lower()) > 60
                ]

                if not matched_books:
                    return {
                        "type": "not_found",
                        "message": f"📚 I couldn't find any books matching '{search_terms}'.\n\n"
                                 "Try:\n"
                                 "• Using different keywords\n"
                                 "• Checking the spelling\n"
                                 "• Browsing by category",
                        "suggestions": ["Show categories", "Popular books", "New arrivals"]
                    }

                message = f"📚 Found {len(matched_books)} books matching '{search_terms}':\n\n"
                for book in matched_books[:5]:  # Limit to top 5 results
                    message += self.format_book_details(dict(book)) + "\n\n"

                return {
                    "type": "books",
                    "message": message,
                    "suggestions": ["Show categories", f"More like {matched_books[0]['title']}", "Another search"]
                }

        except Exception as e:
            print(f"Error searching books: {e}")
            return {
                "type": "error",
                "message": "Sorry, I encountered an error while searching. Please try again.",
                "suggestions": ["Help", "Show categories"]
            }

    def handle_greet(self, query: str, user_id: int) -> Dict[str, Any]:
        """Handle greeting intents with personalized response."""
        hour = datetime.now().hour
        if 5 <= hour < 12:
            greeting = "Good morning! 🌅"
        elif 12 <= hour < 17:
            greeting = "Good afternoon! ☀️"
        elif 17 <= hour < 21:
            greeting = "Good evening! 🌆"
        else:
            greeting = "Hello! 👋"

        return {
            "type": "greeting",
            "message": (
                f"{greeting}\n\n"
                "I can help you:\n"
                "📚 Find books by title, author, or category\n"
                "📖 Browse available categories\n"
                "📍 Locate books in the library\n"
                "\nWhat would you like to do?"
            ),
            "suggestions": [
                "Show all categories",
                "Help"
            ]
        }

    def process_query(self, query: str) -> Dict[str, Any]:
        """Process user query and return a response."""
        query = query.lower().strip()
        
        # Handle location queries
        location_match = re.search(r'(?:where|location|find|locate)\s+(?:is|are|can\s+i\s+find)?\s*(.*?)(?:\?|\s*$)', query)
        if location_match:
            search_term = location_match.group(1).strip()
            if search_term:
                return self.search_book_location(search_term)
        
        # Handle explicit commands first
        if re.search(r'\b(show|list|browse|view)\s+categories\b', query):
            return self.handle_categories(query, 0)
        
        if re.search(r'\bsearch\s+by\s+title\b', query):
            return {
                "type": "prompt",
                "message": (
                    "# Search by Title\n\n"
                    "Please enter the title you're looking for. For example:\n"
                    "- `find Harry Potter`\n"
                    "- `search Python Programming`\n"
                    "- `looking for Lord of the Rings`\n\n"
                    "You can also search by typing the title directly."
                ),
                "suggestions": [
                    "Find Harry Potter",
                    "Search Fiction books",
                    "Show categories"
                ]
            }
        
        # Handle category search
        category_match = re.search(r'(?:search|find|show)\s+(\w+)\s+books?', query)
        if category_match:
            category = category_match.group(1)
            if category.lower() not in ['by', 'for', 'me', 'search']:  # Skip common words
                return self.fetch_books_by_category(category)
        
        # Handle title search
        if any(word in query for word in ['find', 'search', 'looking']):
            search_terms = re.sub(r'\b(find|search|looking|for|books?|by|title)\b', '', query).strip()
            if search_terms:
                return self.search_books(title=search_terms)
        
        # Handle "show categories" command
        if re.search(r'\b(show|list|browse|view)\s+categories\b', query):
            return self.handle_categories(query, 0)
        
        # Handle "Search [Category] books" pattern
        category_match = re.search(r'(?:search|find|show)\s+(\w+)\s+books?', query)
        if category_match:
            return self.fetch_books_by_category(category_match.group(1))
        
        # Handle "Popular books" command
        if re.search(r'\b(popular|top|best)\s+books?\b', query):
            return self.popular_books()
        
        # Detect intent
        intent = self.detect_intent(query)
        
        # Handle each intent with dedicated methods
        if intent == 'greet':
            return self.handle_greet(query, 0)
        
        elif intent == 'my_books':
            return self.handle_my_books(query, 0)
        
        elif intent == 'find_book':
            # Extract search terms
            search_terms = re.sub(r'\b(find|search|get|books?|by|for|me)\b', '', query).strip()
            if not search_terms:
                return self.handle_help(query, 0)
            return self.search_books(title=search_terms)
        
        elif intent == 'categories':
            return self.handle_categories(query, 0)
        
        elif intent == 'penalties':
            return self.handle_penalties(query, 0)
        
        elif intent == 'help':
            return self.handle_help(query, 0)
        
        # Check for category-specific searches
        category = self.detect_category(query)
        if category != "unknown":
            return self.fetch_books_by_category(category)
        
        # Handle direct title searches for queries > 2 chars
        if len(query) > 2:
            return self.search_books(title=query)
        
        # Default to unknown handler
        return self.handle_unknown(query, 0)

    def search_fiction_books(self) -> Dict[str, Any]:
        """Search for fiction books and return their details."""
        try:
            with self.get_db_connection() as conn:
                books = conn.execute("""
                    SELECT 
                        title, 
                        author, 
                        main_area, 
                        rack_no, 
                        column_no, 
                        available_copies 
                    FROM books 
                    WHERE LOWER(category) = 'fiction'
                """).fetchall()

                if not books:
                    return {
                        "type": "not_found",
                        "message": "No fiction books found in the library.",
                        "suggestions": []
                    }

                message = "📚 Fiction Books Available:\n\n"
                for book in books:
                    status = "🟢 Available" if book["available_copies"] > 0 else "🔴 Not Available"
                    message += (
                        f"📖 Title: {book['title']}\n"
                        f"✍️ Author: {book['author']}\n"
                        f"📍 Location: {book['main_area']} - Rack {book['rack_no']}, Column {book['column_no']}\n"
                        f"{status}\n\n"
                    )

                return {
                    "type": "books",
                    "message": message,
                    "suggestions": []
                }

        except Exception as e:
            print(f"Error fetching fiction books: {e}")
            return {
                "type": "error",
                "message": "An error occurred while fetching fiction books. Please try again later.",
                "suggestions": []
            }

    def popular_books(self) -> Dict[str, Any]:
        """List popular books."""
        try:
            with self.get_db_connection() as conn:
                books = conn.execute("""
                    SELECT 
                        title, 
                        author, 
                        category, 
                        main_area, 
                        rack_no, 
                        column_no, 
                        available_copies 
                    FROM books 
                    ORDER BY RANDOM() LIMIT 5
                """).fetchall()

                if not books:
                    return {
                        "type": "not_found",
                        "message": "No popular books found.",
                        "suggestions": []
                    }

                message = "📚 Popular Books:\n\n"
                for book in books:
                    status = "🟢 Available" if book["available_copies"] > 0 else "🔴 Not Available"
                    message += (
                        f"📖 Title: {book['title']}\n"
                        f"✍️ Author: {book['author']}\n"
                        f"🏷️ Category: {book['category']}\n"
                        f"📍 Location: {book['main_area']} - Rack {book['rack_no']}, Column {book['column_no']}\n"
                        f"{status}\n\n"
                    )

                return {
                    "type": "books",
                    "message": message,
                    "suggestions": ["Search for another book", "List categories"]
                }

        except Exception as e:
            print(f"Error fetching popular books: {e}")
            return {
                "type": "error",
                "message": "An error occurred while fetching popular books. Please try again later.",
                "suggestions": []
            }

    def detect_category(self, query: str) -> str:
        """Detect the category from the user's query dynamically."""
        query = query.lower().strip()

        try:
            with self.get_db_connection() as conn:
                categories = conn.execute("SELECT DISTINCT LOWER(category) as category FROM books").fetchall()
                category_list = [cat["category"] for cat in categories]

                for category in category_list:
                    if category in query:
                        return category
        except Exception as e:
            print(f"Error fetching categories: {e}")

        return "unknown"

    def fetch_books_by_category(self, category: str) -> Dict[str, Any]:
        """Fetch books for a specific category."""
        try:
            with self.get_db_connection() as conn:
                # Search for books in the category
                books = conn.execute("""
                    SELECT 
                        title,
                        author,
                        category,
                        main_area,
                        rack_no,
                        column_no,
                        available_copies
                    FROM books 
                    WHERE LOWER(category) = LOWER(?)
                """, (category,)).fetchall()

                if not books:
                    return {
                        "type": "not_found",
                        "message": (
                            f"# No Books Found\n\n"
                            f"Sorry, I couldn't find any books in the '{category}' category.\n\n"
                            "## Suggestions:\n"
                            "- Check the category spelling\n"
                            "- Browse all categories\n"
                            "- Try searching by title instead"
                        ),
                        "suggestions": ["Show categories", "Search by title"]
                    }

                message = f"# Books in {category.title()} Category\n\n"
                for book in books:
                    status = "🟢 Available" if book['available_copies'] > 0 else "🔴 Unavailable"
                    message += (
                        f"## {book['title']}\n"
                        f"**Author**: {book['author']}\n"
                        f"**Location**: {book['main_area']} - Rack {book['rack_no']}, Column {book['column_no']}\n"
                        f"**Status**: {status}\n\n"
                        "---\n\n"
                    )

                return {
                    "type": "books",
                    "message": message,
                    "suggestions": ["Show all categories", f"More {category} books", "Search by title"]
                }

        except Exception as e:
            print(f"Error fetching books by category: {e}")
            return {
                "type": "error",
                "message": "Sorry, I couldn't fetch the books. Please try again.",
                "suggestions": ["Show categories", "Help"]
            }

    def handle_penalties(self, query: str, user_id: int) -> Dict[str, Any]:
        """Handle penalty/fine related queries."""
        try:
            with self.get_db_connection() as conn:
                # Get user's fines
                fines = conn.execute("""
                    SELECT 
                        b.title,
                        bh.borrowed_at,
                        bh.returned_at,
                        bh.penalty
                    FROM book_history bh
                    JOIN books b ON b.id = bh.book_id
                    WHERE bh.user_id = ?
                    AND bh.penalty > 0
                """, (user_id,)).fetchall()

                if not fines:
                    return {
                        "type": "fines",
                        "message": "🎉 Good news! You don't have any outstanding fines.",
                        "suggestions": ["Show my books", "Search for books", "Show categories"]
                    }

                total_fine = sum(fine["penalty"] for fine in fines)
                message = "📋 Your Current Fines:\n\n"
                
                for fine in fines:
                    status = "⏳ Ongoing" if fine["returned_at"] is None else "📥 Returned"
                    message += (
                        f"📚 {fine['title']}\n"
                        f"📅 Borrowed: {fine['borrowed_at']}\n"
                        f"💰 Fine Amount: ${fine['penalty']:.2f}\n"
                        f"📌 Status: {status}\n\n"
                    )
                
                message += f"\n💵 Total Outstanding: ${total_fine:.2f}"

                return {
                    "type": "fines",
                    "message": message,
                    "suggestions": ["Show my books", "Pay fines", "Show categories"]
                }

        except Exception as e:
            print(f"Error fetching fines: {e}")
            return {
                "type": "error",
                "message": "Sorry, I couldn't fetch your fines. Please try again later.",
                "suggestions": ["Show my books", "Show categories", "Help"]
            }

    def handle_my_books(self, query: str, user_id: int) -> Dict[str, Any]:
        """Handle queries about user's borrowed books."""
        try:
            with self.get_db_connection() as conn:
                borrowed_books = conn.execute("""
                    SELECT 
                        b.title,
                        b.author,
                        bh.borrowed_at,
                        bh.returned_at,
                        bc.status,
                        bc.copy_id
                    FROM book_history bh
                    JOIN books b ON b.id = bh.book_id
                    JOIN book_copies bc ON bc.copy_id = bh.copy_id
                    WHERE bh.user_id = ?
                    AND bh.returned_at IS NULL
                    ORDER BY bh.borrowed_at DESC
                """, (user_id,)).fetchall()

                if not borrowed_books:
                    return {
                        "type": "books",
                        "message": "📚 You don't have any books checked out at the moment.",
                        "suggestions": [
                            "Search for books",
                            "Show categories",
                            "Show my fines"
                        ]
                    }

                message = "📚 Your Borrowed Books:\n\n"
                for book in borrowed_books:
                    borrow_date = datetime.strptime(book['borrowed_at'], '%Y-%m-%d %H:%M:%S')
                    days_borrowed = (datetime.now() - borrow_date).days
                    
                    message += (
                        f"📖 {book['title']}\n"
                        f"✍️ by {book['author']}\n"
                        f"📅 Borrowed: {borrow_date.strftime('%B %d, %Y')}\n"
                        f"⏳ Days borrowed: {days_borrowed}\n"
                        f"🔖 Copy ID: {book['copy_id']}\n\n"
                    )

                return {
                    "type": "books",
                    "message": message,
                    "suggestions": [
                        "Search for new books",
                        "Show my fines",
                        "Return a book"
                    ]
                }

        except Exception as e:
            print(f"Error fetching borrowed books: {e}")
            return {
                "type": "error",
                "message": "Sorry, I couldn't fetch your borrowed books. Please try again later.",
                "suggestions": ["Show categories", "Search for books", "Help"]
            }

    def search_book_location(self, title: str) -> Dict[str, Any]:
        """Search for a book's location in the library."""
        try:
            with self.get_db_connection() as conn:
                book = conn.execute("""
                    SELECT 
                        title,
                        author,
                        category,
                        main_area,
                        rack_no,
                        column_no,
                        available_copies
                    FROM books 
                    WHERE LOWER(title) LIKE ?
                """, (f"%{title.lower()}%",)).fetchone()

                if not book:
                    return {
                        "type": "not_found",
                        "message": (
                            f"# Book Not Found\n\n"
                            f"I couldn't find '{title}' in our library.\n\n"
                            "## Try:\n"
                            "- Checking the spelling\n"
                            "- Using the full title\n"
                            "- Browsing by category"
                        ),
                        "suggestions": ["Show categories", "Search by title", "Help"]
                    }

                status = "🟢 Available" if book["available_copies"] > 0 else "🔴 Not Available"
                message = (
                    f"# 📍 Location of '{book['title']}'\n\n"
                    f"## Book Details\n"
                    f"**Title**: {book['title']}\n"
                    f"**Author**: {book['author']}\n"
                    f"**Category**: {book['category']}\n\n"
                    f"## Location\n"
                    f"**Area**: {book['main_area']}\n"
                    f"**Rack**: {book['rack_no']}\n"
                    f"**Column**: {book['column_no']}\n"
                    f"**Status**: {status}\n\n"
                )

                return {
                    "type": "location",
                    "message": message,
                    "suggestions": ["Find another book", "Show categories", "Show map"]
                }

        except Exception as e:
            print(f"Error searching book location: {e}")
            return {
                "type": "error",
                "message": "Sorry, I couldn't find the book's location. Please try again.",
                "suggestions": ["Show categories", "Help"]
            }