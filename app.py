from flask import Flask, jsonify, request
import psycopg2
import time
from database import get_db_connection, validate_and_authorize
from routes.staff import staff_bp
from routes.general import general_bp

# Create Flask server
app = Flask(__name__) 

# Register staff blueprint
app.register_blueprint(staff_bp)

# Register general blueprint
app.register_blueprint(general_bp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)