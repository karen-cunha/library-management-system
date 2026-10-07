import psycopg2
from flask import jsonify

# ==========================================
# DB Settings
# ==========================================
DB_CONFIG = {
    'dbname': 'dbfichas',
    'user': 'aulaspl',
    'password': 'aulaspl',
    'host': 'localhost',
    'port': '5432'
}

def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)

def validate_and_authorize(data, allowed_roles):
    """
    Validetes credentials, get user roles and check for permissions
    """

    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return None, (jsonify({"status": 400, "errors": "Invalid Credentials", "results": None}), 400)

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Obtain ID for authentication
        cur.execute("SELECT user_id FROM users WHERE username = %s AND password = %s", (username, password))
        user_row = cur.fetchone()

        if not user_row:
            return None, (jsonify({"status": 403, "errors": "Invalid Credentials", "results": None}), 403)
        
        user_id = user_row[0]
        user_role = None

        # Get user role
        cur.execute("SELECT 1 FROM administrator WHERE user_id = %s", (user_id,))
        if cur.fetchone():
            user_role = 'administrator'
        else:
            cur.execute("SELECT 1 FROM librarian WHERE user_id = %s", (user_id,))
            if cur.fetchone():
                user_role = 'librarian'
            else:
                cur.execute("SELECT 1 FROM reader WHERE user_id = %s", (user_id,))
                if cur.fetchone():
                    user_role = 'reader'

        # If user has no role:
        if not user_role:
            return None, (jsonify({"status": 500, "errors": "Error internal server error: User without assigned role", "results": None}), 500)

        # Check if role is in the allowed list
        if user_role not in allowed_roles:
            return None, (jsonify({"status": 403, "errors": f"Access Denied. Actual role: {user_role}", "results": None}), 403)

        # Return ID and role
        return {'user_id': user_id, 'role': user_role}, None

    finally:
        cur.close()
        conn.close()