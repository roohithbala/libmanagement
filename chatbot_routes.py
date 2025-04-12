from flask import Blueprint, jsonify, request, session, redirect, url_for
from library_chatbot import LibraryChatbot
from functools import wraps

# Create a Flask Blueprint for the chatbot
chatbot_bp = Blueprint('chatbot', __name__)

# Initialize the LibraryChatbot with the database path
chatbot = LibraryChatbot("library.db")

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({
                "type": "auth_required",
                "message": "Please login to use the chatbot.",
                "suggestions": ["Login", "Register"]
            }), 401
        return f(*args, **kwargs)
    return decorated_function

@chatbot_bp.route('/chatbot', methods=['POST'])
@login_required
def handle_chatbot_message():
    """Handle incoming chatbot messages."""
    try:
        # Parse the incoming JSON request
        data = request.get_json()
        query = data.get('message', '').strip()

        # Validate the query
        if not query:
            return jsonify({
                "type": "error",
                "message": "Please enter a message.",
                "suggestions": ["Search for books", "Show categories"]
            }), 400

        # Process the query using the LibraryChatbot
        response = chatbot.process_query(query)
        return jsonify(response)

    except Exception as e:
        # Handle unexpected errors
        print(f"Chatbot error: {e}")
        return jsonify({
            "type": "error",
            "message": "An unexpected error occurred. Please try again later.",
            "suggestions": []
        }), 500