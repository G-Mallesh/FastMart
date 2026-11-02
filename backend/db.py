
import os

import mysql.connector
from dotenv import load_dotenv

# Load environment variables from the project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, ".env"))


def get_db_connection():
    """Create a connection to the FAST MART database."""
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", "root"),
        database=os.getenv("DB_NAME", "fastmart"),
    )


def test_db_connection():
    """Check whether the database connection works."""
    connection = None

    try:
        connection = get_db_connection()

        cursor = connection.cursor()
        cursor.execute("SELECT DATABASE()")
        database_name = cursor.fetchone()[0]
        cursor.close()

        return True, f"Connected to database: {database_name}"

    except mysql.connector.Error as error:
        return False, str(error)

    finally:
        if connection and connection.is_connected():
            connection.close()
