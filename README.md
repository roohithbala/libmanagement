# 📚 Library Management System

A web-based application built with **Python Flask** and **SQLite3**, designed to streamline and automate library operations such as book management, user registration, borrowing/returning books, fine calculation, and chatbot assistance.

---

## 🚀 Features

### 👤 User Management
- Register, login, logout securely
- Role-based access: Admin, Librarian, User
- Update user profile and reset password

### 📚 Book Management
- Add, update, delete books
- Search books by title, author, or category
- View book availability and location

### 🔄 Borrowing & Returning
- Borrow books with due date tracking
- Return books and calculate overdue penalties
- Force return functionality for librarians/admins

### 💸 Fine Management
- Automatic fine calculation for overdue books
- Manual fine adjustments by admins/librarians

### 📊 Reports & History
- User borrowing history
- Book-specific history
- Fine and activity reports

### 🤖 Chatbot Integration
- Chatbot to answer queries like book search, borrowing status, and help

---

## 🛠 Tech Stack

- **Backend**: Python, Flask, Flask-SQLAlchemy
- **Frontend**: HTML, CSS, Bootstrap (or Tailwind/React optionally)
- **Database**: SQLite3
- **Others**: Jinja2, FuzzyWuzzy for search, dotenv for environment management

---

## 💾 Requirements

Python 3.6 or higher and the following packages:
'''
Flask==3.0.2
Flask-SQLAlchemy==3.1.1
Werkzeug==3.0.1
itsdangerous==2.1.2
Jinja2==3.1.3
click==8.1.7
requests==2.31.0
SQLAlchemy==2.0.27
fuzzywuzzy==0.18.0
python-Levenshtein==0.25.0
markdown==3.5.2
pytest==8.0.2
pytest-cov==4.1.0
python-dotenv==1.0.1
black==24.2.0
flake8==7.0.0
'''
 # Database Schema

users - User details and roles

books - Book metadata

book_copies - Tracks availability per copy

book_history - Logs borrow/return actions

reset_requests - Password reset logs

admin_logs - Admin activities


git clone https://github.com/your-username/Library-Management-System.git
cd Library-Management-System
Install Dependencies

pip install -r requirements.txt
Initialize the Database


python init_db.py
Run the Application


python app.py
Access in Browser

Go to http://127.0.0.1:5000

🌟 Future Enhancements
📧 Email notifications for due books

📱 Mobile application version

📊 Analytics and usage dashboards

📚 Integration with Open Library API for book covers

🔐 Two-factor authentication for users

🤝 Contributing
Pull requests are welcome! For major changes, open an issue first to discuss what you would like to change.

📄 License
This project is open-source and available under the MIT License.

👨‍💻 Author
Roohith Bala G – GitHub
