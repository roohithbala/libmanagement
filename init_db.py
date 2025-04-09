from app import init_db
import os

# Remove existing database file if it exists
if os.path.exists("library.db"):
    os.remove("library.db")

# Initialize fresh database
init_db()
print("Database initialized successfully!")