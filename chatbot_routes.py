from flask import jsonify, session
from library_chatbot import LibraryChatbot

chatbot = LibraryChatbot("library.db")

def handle_chatbot_message(message):
    if "user_id" not in session:
        return jsonify({
            "type": "text",
            "message": "Please log in to use the chat assistant.",
            "suggestions": []
        })

    response = chatbot.process_query(message, session["user_id"])
    return jsonify(response)