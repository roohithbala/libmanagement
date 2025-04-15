
# **Library Management System Documentation**

---

## **1. Project Overview**

The **Library Management System** is a web-based application designed to streamline library operations. Built using **Python Flask** and **SQLite3**, this system provides an efficient platform for managing book catalogs, user accounts, borrowing/returning books, fine management, and reporting. It ensures data integrity, security, and ease of use for librarians and patrons.

---

## **2. Features**

### **2.1 User Management**
- **Registration**: Users can register by providing personal details such as name, email, phone number, and reading interests.
- **Login/Logout**: Users can securely log in and log out of the system.
- **Profile Management**: Users can update their profile information, including passwords and personal details.

### **2.2 Book Management**
- **Add Books**: Administrators and librarians can add new books to the library catalog, specifying details like title, author, category, ISBN, and location.
- **Update Books**: Book details, including the number of copies, can be updated.
- **Delete Books**: Books can be removed from the catalog if they are no longer available.
- **Search Books**: Users can search for books by title, author, or category.

### **2.3 Borrowing and Returning**
- **Borrow Books**: Users can borrow available books. The system tracks the due date and assigns a copy of the book to the user.
- **Return Books**: Users can return borrowed books, and penalties are calculated for overdue returns.
- **Force Return**: Administrators and librarians can forcefully return books if users fail to return them on time.

### **2.4 Fine Management**
- **Penalty Calculation**: The system calculates fines for overdue books based on the number of days overdue.
- **Adjust Penalties**: Administrators and librarians can manually adjust penalties for specific cases.

### **2.5 Reporting and History**
- **Borrowing History**: Users can view their borrowing history, including returned and overdue books.
- **Book History**: Administrators and librarians can view the borrowing history of specific books.
- **Reports**: The system generates reports on book availability, user activity, and fines.

### **2.6 Chatbot Integration**
- A chatbot is integrated into the system to assist users with common queries, such as searching for books, checking borrowing history, and viewing categories.

---

## **3. System Requirements**

### **3.1 Hardware Requirements**
- **RAM**: 512 MB or higher
- **Storage**: 80 GB or more
- **Processor**: Dual-core or higher

### **3.2 Software Requirements**
- **Python**: Version 3.6 or higher
- **Flask**: Web framework
- **SQLite3**: Database
- **Bootstrap**: Frontend framework

### **3.3 Python Packages**
The required Python packages are listed in the `requirements.txt` file:

```plaintext
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
```

---

## **4. Database Schema**

The database schema includes the following tables:

1. **Users Table**  
   - Stores user details such as username, email, password, role, and personal information.

2. **Books Table**  
   - Stores book details, including title, author, category, ISBN, and location.

3. **Book Copies Table**  
   - Tracks individual copies of books and their statuses (e.g., available, borrowed).

4. **Book History Table**  
   - Logs borrowing and returning activities for each book.

5. **Reset Requests Table**  
   - Tracks password reset requests.

6. **Admin Logs Table**  
   - Logs administrative actions for auditing purposes.

---

## **5. Key Files**

1. **`app.py`**  
   - The main Flask application file that defines routes for user authentication, book management, borrowing/returning, and reporting.

2. **`book.py`**  
   - Contains functions for managing books, including adding, updating, deleting, borrowing, and returning books.

3. **`chatbot_routes.py`**  
   - Defines routes for handling chatbot queries and integrates the chatbot with the Flask application.

4. **`library_chatbot.py`**  
   - Implements the chatbot logic, including intent detection, book search, and category listing.

5. **`migrate_db.py`**  
   - A script for migrating the database schema, adding new tables and columns as needed.

6. **`init_db.py`**  
   - Initializes the database by creating the required tables.

7. **Templates**  
   - HTML templates for the frontend, including:
     - `index.html`: Homepage  
     - `register.html`: User registration page  
     - `login.html`: User login page  
     - `admin_dashboard.html`: Admin dashboard  
     - `librarian_dashboard.html`: Librarian dashboard  
     - `user_dashboard.html`: User dashboard  
     - `add_book.html`: Add book form  
     - `update_book.html`: Update book form  
     - `book_details.html`: Book details page  
     - `return_book.html`: Return book page  
     - `profile.html`: User profile page  
     - `forgot_password.html`: Password reset request page  
     - `password_reset_requests.html`: Admin password reset requests page

---

## **6. System Flow**

1. **User Registration and Login**  
   - Users register with their details and log in to access the system.  
   - Role-based access control ensures that only authorized users can access certain features.

2. **Book Management**  
   - Administrators and librarians can add, update, and delete books.  
   - Users can search for books and view their details.

3. **Borrowing and Returning**  
   - Users can borrow available books, and the system tracks the due date.  
   - Users can return books, and penalties are calculated for overdue returns.

4. **Fine Management**  
   - The system calculates fines for overdue books.  
   - Administrators and librarians can adjust fines manually.

5. **Chatbot Assistance**  
   - The chatbot assists users with common queries, such as searching for books, checking borrowing history, and viewing categories.

---

## **7. How to Run the Project**

1. **Clone the Repository**
   ```bash
   git clone <repository-url>
   cd Library
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables**
   Create a `.env` file in your project root:
   ```ini
   SECRET_KEY=your_secret_key
   DATABASE_URI=sqlite:///library.db
   ```

4. **Initialize the Database**
   ```bash
   python init_db.py
   ```

5. **Run the Application**
   ```bash
   python app.py
   ```

6. **Access the Application**  
   - Open your browser and navigate to `http://127.0.0.1:5000`

---

## **8. Security Practices**

- **Password Hashing**: All user passwords are securely hashed using `Werkzeug` before storage.
- **Role-Based Access Control**: Features are restricted based on user roles (`admin`, `librarian`, `user`).
- **Input Validation**: User inputs are validated to prevent SQL injection and XSS.
- **Environment Variables**: Sensitive data like secret keys are stored in `.env` files using `python-dotenv`.

---

## **9. Running Tests**

Run the following command to execute unit tests and check code coverage:

```bash
pytest --cov=.
```

---

## **10. Future Enhancements**

- **Email Notifications**: Notify users about due dates and penalties via email.
- **Advanced Reporting**: Generate detailed reports on library usage and trends.
- **Mobile App**: Develop a mobile app for easier access.
- **Integration with External APIs**: Fetch book details and covers from Open Library or Google Books API.

---

## **11. Conclusion**

The **Library Management System** is a comprehensive solution for managing library operations efficiently. By automating key processes such as book cataloging, user management, and borrowing/returning, the system reduces manual effort, improves data accuracy, and enhances the overall library experience for both librarians and patrons.

---
