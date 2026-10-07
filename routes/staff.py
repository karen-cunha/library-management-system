# Administrators and Librarians Endpoints

from flask import Blueprint, request, jsonify
from database import get_db_connection, validate_and_authorize

# Create flask blueprint
staff_bp = Blueprint('staff', __name__)

##### ENDPOINTS #####

# 2. Add Book (POST)
# http://localhost:8080/sgdproj/book
# {"username": "","password": "","ISBN": "",“book_name”:"", "author":[], "book_description": "", "pages": , "copies": , "genres":[]}
@staff_bp.route("/sgdproj/book", methods=['POST'])
def book():

    data = request.get_json()

    # Admin only
    user_info, error = validate_and_authorize(data, ['administrator'])
    if error:
        return error

    isbn = data.get("ISBN")
    book_name = data.get("book_name")
    author = data.get("author")
    book_description = data.get("book_description")
    pages = data.get("pages")
    copies = data.get("copies")
    genres = data.get("genres")

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # First Insert (Books)
        cur.execute("""
            INSERT INTO books (isbn, book_name, book_description, pages, copies, registration_date)
            VALUES (%s, %s, %s, %s, %s, CURRENT_DATE);
        """, (isbn, book_name, book_description, pages, copies))

        # Second Insert (Author_Book)
        for author_id in author:
            cur.execute("""
                INSERT INTO author_books (author_id, isbn)
                VALUES (%s, %s);
            """, (author_id, isbn))

        # Third Insert (Book_Genres)
        for genre_id in genres:
            cur.execute("""
                INSERT INTO book_genres (isbn, genre_id)
                VALUES (%s, %s);
            """, (isbn, genre_id))

        conn.commit()

        return jsonify({
            "status": 200, 
            "errors": None, 
            "results": isbn
        }), 200

    except Exception as e:
        # If any insert fails, rollback
        conn.rollback()
        return jsonify({
            "status": 500, 
            "errors": f"Error inserting data in the db: {str(e)}", 
            "results": None
        }), 500

    finally:
        cur.close()
        conn.close()

# 3. Modify Copies of a Book (PUT)
# http://localhost:8080/sgdproj/update_copies
# {"username": "","password": "","ISBN": "","copies":}
@staff_bp.route("/sgdproj/update_copies", methods=['PUT'])
def update_copies():
    
    data = request.get_json()

    # Admin only
    user_info, error = validate_and_authorize(data, ['administrator'])
    if error:
        return error

    isbn = data.get("ISBN")
    copies = data.get("copies")

    new_copies = int(copies)
    if new_copies < 0:
        return jsonify({"status": 400, "errors": "Copies can not be negative", "results": None}), 400
    
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Get loaned copies
        cur.execute("""SELECT count(*) FROM loans WHERE isbn = %s AND return_date IS NULL""", (isbn,))
        active_loans = cur.fetchone()[0]

        # Check if new copies value is valid
        if new_copies < active_loans:
            return jsonify({
                "status": 400, 
                "errors": f"Can not reduce to {new_copies}. There is {active_loans} copies on loan currently.", 
                "results": None
            }), 400

        # Update copies
        cur.execute("""
                    UPDATE books
                    SET copies = %s
                    WHERE isbn = %s
                    """, (new_copies, isbn))
        
        conn.commit()

        return jsonify({
            "status": 200,
            "errors": None,
            "results": isbn
        }), 200
    
    except Exception as e:
        conn.rollback()
        return jsonify({"status": 500, "errors": f"Error updating database: {str(e)}", "results": None}), 500

    finally:
        cur.close()
        conn.close()

# 4. List Books from Genre (GET) 
# http://localhost:8080/sgdproj/list_books_by_genre
# {"username": "","password": "","genre_id": }
@staff_bp.route("/sgdproj/list_books_by_genre", methods=['GET'])
def list_books_by_genre():

    data = request.get_json()

    # Admin or Librarian
    user_info, error = validate_and_authorize(data, ['administrator', 'librarian'])
    if error:
        return error

    genre_id = data.get("genre_id")

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        query = """
            SELECT 
                b.isbn AS "ISBN", 
                b.book_name, 
                a.name AS author, 
                b.pages, 
                b.copies,
                (b.copies - (
                    SELECT count(*) FROM loans l 
                    WHERE l.isbn = b.isbn AND l.return_date IS NULL
                )) AS available_copies,
                (
                    SELECT array_agg(g.name)
                    FROM book_genres bg2
                    JOIN genres g ON bg2.genre_id = g.genre_id
                    WHERE bg2.isbn = b.isbn
                ) AS genres
            FROM books b
            JOIN author_books ab ON b.isbn = ab.isbn
            JOIN authors a ON ab.author_id = a.author_id
            JOIN book_genres bg ON b.isbn = bg.isbn
            WHERE bg.genre_id = %s;
        """
        cur.execute(query, (genre_id, ))

        rows = cur.fetchall()

        payload = []

        for row in rows:
            content = {
                'ISBN': row[0],
                'book_name': row[1],
                'author': row[2],
                'pages': row[3],
                'copies': row[4],
                'available_copies': max(row[5], 0),
                'genres': row[6]
            }
            payload.append(content)

        return jsonify({
            "status": 200,
            "errors": None,
            "results": payload
        }), 200

    except Exception as e:
        return jsonify({
            "status": 500,
            "errors": f"Database error: {str(e)}",
            "results": None
        }), 500

    finally:
        cur.close()
        conn.close()
    
# 5. Find Book by Name (GET)
# http://localhost:8080/sgdproj/find_book_by_name
# {"username": "","password": "","book_name": ""}
@staff_bp.route("/sgdproj/find_book_by_name", methods=['GET'])
def find_book_by_name():

    data = request.get_json()

    # Admin or Librarian
    user_info, error = validate_and_authorize(data, ['administrator', 'librarian'])
    if error:
        return error

    book_name = data.get("book_name")

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        query = """
            SELECT 
                b.isbn AS "ISBN", 
                b.book_name, 
                a.name AS author, 
                b.pages, 
                b.copies,
                (b.copies - (
                    SELECT count(*) FROM loans l 
                    WHERE l.isbn = b.isbn AND l.return_date IS NULL
                )) AS available_copies,
                (
                    SELECT array_agg(g.name)
                    FROM book_genres bg2
                    JOIN genres g ON bg2.genre_id = g.genre_id
                    WHERE bg2.isbn = b.isbn
                ) AS genres
            FROM books b
            JOIN author_books ab ON b.isbn = ab.isbn
            JOIN authors a ON ab.author_id = a.author_id
            JOIN book_genres bg ON b.isbn = bg.isbn
            WHERE b.book_name = %s;
        """
        cur.execute(query, (book_name, ))

        rows = cur.fetchall()

        payload = []

        for row in rows:
            content = {
                'ISBN': row[0],
                'book_name': row[1],
                'author': row[2],
                'pages': row[3],
                'copies': row[4],
                'available_copies': max(row[5], 0),
                'genres': row[6]
            }
            payload.append(content)

        return jsonify({
            "status": 200,
            "errors": None,
            "results": payload
        }), 200

    except Exception as e:
        return jsonify({
            "status": 500,
            "errors": f"Database error: {str(e)}",
            "results": None
        }), 500

    finally:
        cur.close()
        conn.close()

# 6. Find Book by ISBN (GET)
# http://localhost:8080/sgdproj/find_book_by_isbn
# {"username": "","password": "","ISBN": ""}
@staff_bp.route("/sgdproj/find_book_by_isbn", methods=['GET'])
def find_book_by_isbn():

    data = request.get_json()

    # Admin or Librarian
    user_info, error = validate_and_authorize(data, ['administrator', 'librarian'])
    if error:
        return error

    isbn = data.get("ISBN")

    conn = get_db_connection()
    cur = conn.cursor()
   
    try:
        query = """
            SELECT 
                b.isbn AS "ISBN", 
                b.book_name, 
                a.name AS author, 
                b.pages, 
                b.copies,
                (b.copies - (
                    SELECT count(*) FROM loans l 
                    WHERE l.isbn = b.isbn AND l.return_date IS NULL
                )) AS available_copies,
                (
                    SELECT array_agg(g.name)
                    FROM book_genres bg2
                    JOIN genres g ON bg2.genre_id = g.genre_id
                    WHERE bg2.isbn = b.isbn
                ) AS genres
            FROM books b
            JOIN author_books ab ON b.isbn = ab.isbn
            JOIN authors a ON ab.author_id = a.author_id
            JOIN book_genres bg ON b.isbn = bg.isbn
            WHERE b.isbn = %s;
        """
        cur.execute(query, (isbn, ))

        rows = cur.fetchall()

        payload = []

        for row in rows:
            content = {
                'ISBN': row[0],
                'book_name': row[1],
                'author': row[2],
                'pages': row[3],
                'copies': row[4],
                'available_copies': max(row[5], 0),
                'genres': row[6]
            }
            payload.append(content)

        return jsonify({
            "status": 200,
            "errors": None,
            "results": payload
        }), 200

    except Exception as e:
        return jsonify({
            "status": 500,
            "errors": f"Database error: {str(e)}",
            "results": None
        }), 500

    finally:
        cur.close()
        conn.close()

# 7. Loaned Books (GET)
# http://localhost:8080/sgdproj/loaned_books
# {"username": "","password": ""}
@staff_bp.route("/sgdproj/loaned_books", methods=['GET'])
def loaned_books():

    data = request.get_json()

    # Admin or Librarian
    user_info, error = validate_and_authorize(data, ['administrator', 'librarian'])
    if error:
        return error

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        query = """
            SELECT 
                b.isbn, 
                b.book_name, 
                l.user_id AS loaner_id, 
                u.username AS loaner_name,
                l.loan_date
            FROM books b 
            JOIN loans l ON b.isbn = l.isbn
            JOIN users u ON l.user_id = u.user_id
            WHERE l.return_date IS NULL;
        """
        cur.execute(query)

        rows = cur.fetchall()
        
        payload = []
        
        for row in rows:
            content = {
                'ISBN': row[0],
                'book_name': row[1],
                'loaner_id': row[2],
                'loaner_name': row[3],
                'loan_date': row[4]
            }
            payload.append(content)

        return jsonify({
            "status": 200,
            "errors": None,
            "results": payload
        }), 200

    except Exception as e:
        return jsonify({
            "status": 500,
            "errors": f"Database error: {str(e)}",
            "results": None
        }), 500

    finally:
        cur.close()
        conn.close()

# 8. Loaned Book (GET)
# http://localhost:8080/sgdproj/loaned_book
# {"username": "","password": "","ISBN": ""}
@staff_bp.route("/sgdproj/loaned_book", methods=['GET'])
def loaned_book():

    data = request.get_json()

    # Admin or Librarian
    user_info, error = validate_and_authorize(data, ['administrator', 'librarian'])
    if error:
        return error

    isbn = data.get("ISBN")

    conn = get_db_connection()
    cur = conn.cursor()
   
    try:
        query = """
            SELECT 
                l.user_id,
                u.username,
                l.loan_date
            FROM loans l JOIN users u ON l.user_id = u.user_id
            WHERE l.isbn = %s
            ORDER BY loan_date DESC;
        """
        cur.execute(query, (isbn, ))

        rows = cur.fetchall()

        payload = []

        for row in rows:
            content = {
                'loaner_id': row[0],
                'loaner_name': row[1],
                'loan_date': row[2],
            }
            payload.append(content)

        return jsonify({
            "status": 200,
            "errors": None,
            "results": payload
        }), 200

    except Exception as e:
        return jsonify({
            "status": 500,
            "errors": f"Database error: {str(e)}",
            "results": None
        }), 500

    finally:
        cur.close()
        conn.close()

# 9. Generate a Report of Top N Loaned Books (GET)
# http://localhost:8080/sgdproj/TopLoanedBooks/{N}
# {"username": "","password": ""}
@staff_bp.route("/sgdproj/TopLoanedBooks/<int:n>", methods=['GET'])
def top_loaned_books(n):    
    data = request.get_json()

    user_info, error = validate_and_authorize(data, ['administrator', 'librarian'])
    if error:
        return error

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        query = """
            SELECT 
                b.isbn, 
                b.book_name, 
                COUNT(l.isbn) AS loaned_times, 
                MAX(l.loan_date) AS last_loaned
            FROM books b
            LEFT JOIN loans l ON b.isbn = l.isbn
            GROUP BY b.isbn, b.book_name
            ORDER BY loaned_times DESC, last_loaned DESC
            LIMIT %s;
        """
        cur.execute(query, (n,))
        rows = cur.fetchall()

        payload = []
        
        # Generate ranking in python
        for index, row in enumerate(rows):
            content = {
                'ISBN': row[0],
                'book_name': row[1],
                'loaned_times': row[2],
                'last_loaned': row[3].strftime('%Y-%m-%d') if row[3] else None,
                'rank': index + 1
            }
            payload.append(content)

        return jsonify({
            "status": 200,
            "errors": None,
            "results": payload
        }), 200

    except Exception as e:
        return jsonify({
            "status": 500, 
            "errors": f"Database error: {str(e)}", 
            "results": None
        }), 500

    finally:
        cur.close()
        conn.close()

# 10. Generate a Report of Top N Loaners (GET)
# http://localhost:8080/sgdproj/TopLoaners/{N}
# {"username": "","password": ""}
@staff_bp.route("/sgdproj/TopLoaners/<int:n>", methods=['GET'])
def top_loaners(n):    
    data = request.get_json()

    user_info, error = validate_and_authorize(data, ['administrator', 'librarian'])
    if error:
        return error

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        query = """
            SELECT 
                u.user_id, 
                u.username, 
                COUNT(l.isbn) AS loaned_books_quantity,
                array_agg(b.book_name) AS loaned_books,
                (SELECT b2.book_name FROM loans l2 
                 JOIN books b2 ON l2.isbn = b2.isbn 
                 WHERE l2.user_id = u.user_id 
                 ORDER BY l2.loan_date DESC LIMIT 1) AS last_loaned_book,
                MAX(l.loan_date) AS last_loaned_book_date
            FROM users u
            JOIN loans l ON u.user_id = l.user_id
            JOIN books b ON l.isbn = b.isbn
            GROUP BY u.user_id, u.username
            ORDER BY loaned_books_quantity DESC, last_loaned_book_date DESC
            LIMIT %s;
        """ 
        cur.execute(query, (n,))
        rows = cur.fetchall()

        payload = []
        
        for index, row in enumerate(rows):
            content = {
                'loaner_id': row[0],
                'loaner_name': row[1],
                'loaned_books_quantity': row[2],
                'loaned_books': row[3],
                'last_loaned_book': row[4],
                'last_loaned_book_date': row[5].strftime('%Y-%m-%d') if row[5] else None
            }
            payload.append(content)

        return jsonify({
            "status": 200,
            "errors": None,
            "results": payload
        }), 200

    except Exception as e:
        return jsonify({
            "status": 500, 
            "errors": f"Database error: {str(e)}", 
            "results": None
        }), 500
    finally:
        cur.close()
        conn.close()

# 16. Generate a Report of Top N Borrowed Genres in the Last 12 Months
# http://localhost:8080/sgdproj/report/TopLoanedGenres12Months/{N}
# {"username": "","password": ""}
@staff_bp.route("/sgdproj/report/TopLoanedGenres12Months/<int:n>", methods=['GET'])
def top_loaned_genres_12_months(n):    
    data = request.get_json()

    user_info, error = validate_and_authorize(data, ['administrator', 'librarian'])
    if error:
        return error

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        query = """
            SELECT
                g.name AS genre_name,
                COUNT(l.loan_id) AS borrow_count
            FROM genres g 
            JOIN book_genres bg ON g.genre_id = bg.genre_id
            JOIN loans l ON bg.isbn = l.isbn
            WHERE l.loan_date >= CURRENT_DATE - INTERVAL '12 months'
            GROUP BY g.name
            ORDER BY borrow_count DESC
            LIMIT %s;
        """
        cur.execute(query, (n,))
        rows = cur.fetchall()

        payload = []
        
        # Generate ranking in python
        for index, row in enumerate(rows):
            content = {
                'genre': row[0],
                'borrow_count': row[1],
                'rank': index + 1
            }
            payload.append(content)

        return jsonify({
            "status": 200,
            "errors": None,
            "results": payload
        }), 200

    except Exception as e:
        return jsonify({
            "status": 500, 
            "errors": f"Database error: {str(e)}", 
            "results": None
        }), 500

    finally:
        cur.close()
        conn.close()