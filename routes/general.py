# All users endpoints

from flask import Blueprint, request, jsonify
from database import get_db_connection, validate_and_authorize

# Create flask blueprint
general_bp = Blueprint('general', __name__)

##### ENDPOINTS #####

# 1. Register User (POST)
# http://localhost:8080/sgdproj/user
# {"username": username, "email": email, "password": password, "role": role}
@general_bp.route("/sgdproj/user", methods=['POST'])
def user():

    data = request.get_json()

    username = data.get("username")
    email = data.get("email")
    password = data.get("password")
    role = data.get("role")

    if role == 'administrator':
        return jsonify({"status": 400, "errors": "Admins must be created directly in the database..", "results": None}), 400
    
    if role not in ['reader', 'librarian']:
        return jsonify({"status": 400, "errors": "Role must be 'reader' or 'librarian'.", "results": None}), 400
    
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # First Insert into User the new user
        cur.execute("""
                INSERT INTO users (username, email, password)
                VALUES (%s, %s, %s)
                RETURNING user_id;
            """, (username, email, password))
        
        new_user_id = cur.fetchone()

        # Second Insert to the role table
        if role == 'librarian':
            query_role = "INSERT INTO librarian (user_id) VALUES (%s);"
        else:
            query_role = "INSERT INTO reader (user_id) VALUES (%s);"
        
        cur.execute(query_role, (new_user_id,))

        conn.commit()

        return jsonify({
            "status": 200,
            "errors": None,
            "results": new_user_id
        }), 200
    
    except Exception as e:
        conn.rollback()

        return jsonify({
            "status": 500,
            "errors": f"Error registering user: {str(e)}",
            "results": None
        }), 500

    finally:
        cur.close()
        conn.close()

# 11. Available Books by Genre (GET)
# http://localhost:8080/sgdproj/available_books_by_genre
# {"username": "","password": "",“genre_id”: genre_id}
@general_bp.route("/sgdproj/available_books_by_genre", methods=['GET'])
def available_books_by_genre():
    data = request.get_json()
    
    user_info, error = validate_and_authorize(data, ['administrator', 'librarian', 'reader'])
    if error:
        return error

    genre_id = data.get("genre_id")

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # query does the calculous:
        # 1. available copies (total - active loans)
        # 2. rating (mediana of the reviwes by PERCENTILE_CONT)
        query = """
            SELECT 
                b.isbn, 
                b.book_name, 
                b.copies,
                (b.copies - (
                    SELECT count(*) FROM loans l 
                    WHERE l.isbn = b.isbn AND l.return_date IS NULL
                )) AS available_copies,
                b.book_description,
                (
                    SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY r.rating)
                    FROM reviews r 
                    WHERE r.isbn = b.isbn
                ) AS rating
            FROM books b
            JOIN book_genres bg ON b.isbn = bg.isbn
            WHERE bg.genre_id = %s
            AND (b.copies - (
                SELECT count(*) FROM loans l 
                WHERE l.isbn = b.isbn AND l.return_date IS NULL
            )) > 0;
        """
        cur.execute(query, (genre_id, ))
        rows = cur.fetchall()

        payload = []
        for row in rows:
            content = {
                'ISBN': row[0],
                'book_name': row[1],
                'copies': row[2],
                'available_copies': row[3],
                'book_description': row[4],
                'rating': float(row[5]) if row[5] is not None else 0.0
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

# 12. Check Book Reviews (GET)
# http://localhost:8080/sgdproj/check_book
# {"username": username, "password": password, "ISBN": isbn}
@general_bp.route("/sgdproj/check_book", methods=['GET'])
def check_book_reviews():
    data = request.get_json()

    user_info, error = validate_and_authorize(data, ['administrator', 'librarian', 'reader'])
    if error:
        return error

    isbn = data.get("ISBN")

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # step 1: get book name and calculate the overall median rating
        # PERCENTILE_CONT(0.5) for the median
        query_book = """
            SELECT 
                b.book_name,
                (SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY r.rating)
                 FROM reviews r 
                 WHERE r.isbn = b.isbn) AS overall_rating
            FROM books b
            WHERE b.isbn = %s;
        """
        cur.execute(query_book, (isbn,))
        book_info = cur.fetchone()

        if not book_info:
            return jsonify({"status": 400, "errors": "Book not found", "results": None}), 400

        book_name = book_info[0]
        # cases where there are no reviews yet
        overall_rating = float(book_info[1]) if book_info[1] is not None else 0.0

        # step 2: get all individual reviews for the book
        # ordered by date to show the most recent first
        query_reviews = """
            SELECT rating, comment 
            FROM reviews 
            WHERE isbn = %s
            ORDER BY review_date DESC;
        """
        cur.execute(query_reviews, (isbn,))
        review_rows = cur.fetchall()

        reviews_list = []
        for row in review_rows:
            reviews_list.append({
                "rating": row[0],
                "comment": row[1]
            })

        payload = {
            "isbn": isbn,
            "book_name": book_name,
            "overall_rating": overall_rating,
            "reviews": reviews_list
        }

        return jsonify({
            "status": 200,
            "errors": None,
            "results": [payload]
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

# 13. Borrow Book (POST)
# http://localhost:8080/sgdproj/borrow_book
# {"username": "","password": "", “user_id”: user_id, "ISBN": isbn}
@general_bp.route("/sgdproj/borrow_book", methods=['POST'])
def borrow_book():
    data = request.get_json()

    user_info, error = validate_and_authorize(data, ['administrator', 'librarian', 'reader'])
    if error:
        return error

    user_id = data.get("user_id")
    isbn = data.get("ISBN")

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # step 1: concurrency & consistency 
        # transaction and row-level locking to prevent race conditions
        # where multiple users try to borrow the last available copy
        
        cur.execute("SELECT copies FROM books WHERE isbn = %s FOR UPDATE", (isbn,))
        book_data = cur.fetchone()
        
        if not book_data:
            return jsonify({"status": 400, "errors": "Book not found", "results": None}), 400
        
        total_copies = book_data[0]

        # step 2: check current active loans for this specific book
        cur.execute("""
            SELECT count(*) FROM loans 
            WHERE isbn = %s AND return_date IS NULL
        """, (isbn,))
        active_loans_for_book = cur.fetchone()[0]

        if active_loans_for_book >= total_copies:
            return jsonify({"status": 400, "errors": "No copies available for borrowing", "results": None}), 400

        # step 3: check user loan limit 
        cur.execute("""
            SELECT count(*) FROM loans 
            WHERE user_id = %s AND return_date IS NULL
        """, (user_id,))
        user_active_loans = cur.fetchone()[0]
        if user_active_loans >= 5:
            return jsonify({"status": 400, "errors": "User has reached the maximum limit of 5 active loans", "results": None}), 400

        # step 4: record the borrowing 
        cur.execute("""
            INSERT INTO loans (user_id, isbn, loan_date, return_date)
            VALUES (%s, %s, CURRENT_DATE, NULL)
        """, (user_id, isbn))

        conn.commit()

        return jsonify({
            "status": 200,
            "errors": None,
            "results": isbn
        }), 200

    except Exception as e:
        conn.rollback()
        return jsonify({
            "status": 500, 
            "errors": f"Internal server error: {str(e)}", 
            "results": None
        }), 500
    finally:
        cur.close()
        conn.close()

# 14. Submit Review (POST)
# http://localhost:8080/sgdproj/report/submit_review
# {"username": "","password": "", “user_id”: user_id, “ISBN”: ISBN, “rating”: rating, “comment”: comment}
@general_bp.route("/sgdproj/report/submit_review", methods=['POST'])
def submit_review():
    data = request.get_json()
    user_info, error = validate_and_authorize(data, ['administrator', 'librarian', 'reader'])
    if error:
        return error

    user_id = data.get("user_id")
    isbn = data.get("ISBN")
    rating = data.get("rating")
    comment = data.get("comment")

    # rule 1: rating must be an integer between 1 and 5 
    try:
        rating_val = int(rating)
        if not (1 <= rating_val <= 5):
            return jsonify({"status": 400, "errors": "Rating must be between 1 and 5", "results": None}), 400
    except (ValueError, TypeError):
        return jsonify({"status": 400, "errors": "Invalid rating format", "results": None}), 400

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # rule 2: only users who have borrowed the book can submit a review
        cur.execute("SELECT 1 FROM loans WHERE user_id = %s AND isbn = %s", (user_id, isbn))
        if cur.fetchone() is None:
            return jsonify({"status": 400, "errors": "User must borrow the book before reviewing", "results": None}), 400

        # implement UPSERT logic using PostgreSQL's ON CONFLICT clause
        # if a review already exists for this (user_id, ISBN) pair, it updates the existing record 
        query = """
            INSERT INTO reviews (user_id, isbn, rating, comment, review_date)
            VALUES (%s, %s, %s, %s, CURRENT_DATE)
            ON CONFLICT (user_id, isbn) 
            DO UPDATE SET 
                rating = EXCLUDED.rating,
                comment = EXCLUDED.comment,
                review_date = CURRENT_DATE;
        """
        cur.execute(query, (user_id, isbn, rating_val, comment))
        
        conn.commit()
        
        return jsonify({
            "status": 200,
            "errors": None,
            "results": isbn
        }), 200

    except Exception as e:
        conn.rollback()

        return jsonify({
            "status": 500, 
            "errors": f"Database error: {str(e)}", 
            "results": None
        }), 500
    finally:
        cur.close()
        conn.close()

# 15. Return Book (POST)
# http://localhost:8080/sgdproj/return_book
# {"username": "","password": "", “user_id”: user_id, "isbn": "isbn"}
@general_bp.route("/sgdproj/return_book", methods=['POST'])
def return_book():
    data = request.get_json()
    user_info, error = validate_and_authorize(data, ['administrator', 'librarian', 'reader'])
    if error:
        return error

    user_id = data.get("user_id")
    isbn = data.get("ISBN")

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            UPDATE loans 
            SET return_date = CURRENT_DATE 
            WHERE user_id = %s 
              AND isbn = %s 
              AND return_date IS NULL;
        """, (user_id, isbn))
    
        if cur.rowcount == 0:
            conn.rollback()
            return jsonify({
                "status": 400, 
                "errors": f"Loan not found for ISBN {isbn} and user {user_id}.", 
                "results": None
            }), 400
        
        conn.commit()
    
        return jsonify({
            "status": 200,
            "errors": None,
            "results": user_id
        }), 200
    
    except Exception as e:
        conn.rollback()
        return jsonify({
            "status": 500, 
            "errors": f"Database error: {str(e)}", 
            "results": None
        }), 500
    
    finally:
        cur.close()
        conn.close()