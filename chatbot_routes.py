from flask import Blueprint, jsonify, request
from library_chatbot import LibraryChatbot

# Create a Flask Blueprint for the chatbot
chatbot_bp = Blueprint('chatbot', __name__)

# Initialize the LibraryChatbot with the database path
chatbot = LibraryChatbot("library.db")


@chatbot_bp.route('/chatbot', methods=['POST'])
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
                "suggestions": ["Search for Fiction books", "Search for Science books"]
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