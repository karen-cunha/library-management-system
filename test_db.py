from database import get_db_connection

def test_connection():
    
    try:
        # Catabase.py function to get a connection
        conn = get_db_connection()
        cur = conn.cursor()

        # Basic connection test: get DB version
        cur.execute("SELECT version();")
        db_version = cur.fetchone()
        print(f"\nSuccess!\nMotor: {db_version[0]}\n")

        # Test queries
        cur.execute("SELECT count(*) FROM users;")
        users_count = cur.fetchone()[0]
        
        cur.execute("SELECT count(*) FROM books;")
        books_count = cur.fetchone()[0]
        
        print("DB Status:")
        print(f"   - Users: {users_count}")
        print(f"   - Books: {books_count}\n")

        # Close connection
        cur.close()
        conn.close()

    except Exception as e:
        print(f"\nError connecting to DB:\n{e}")

if __name__ == '__main__':
    test_connection()