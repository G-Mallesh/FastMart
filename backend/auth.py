
from werkzeug.security import generate_password_hash, check_password_hash
from backend.db import get_db_connection


def register_user(name, email, password, phone, address, role="customer"):
    name = name.strip()
    email = email.strip().lower()
    phone = phone.strip()
    address = address.strip()

    if len(name) < 2 or len(name) > 100:
        raise ValueError("Name must contain 2 to 100 characters.")

    if len(email) > 254 or "@" not in email or "." not in email.rsplit("@", 1)[-1]:
        raise ValueError("Enter a valid email address.")

    if len(password) < 8:
        raise ValueError("Password must contain at least 8 characters.")

    if len(password) > 128:
        raise ValueError("Password is too long.")

    if not phone or len(phone) > 20:
        raise ValueError("Enter a valid phone number.")

    if len(address) < 5 or len(address) > 500:
        raise ValueError("Address must contain 5 to 500 characters.")

    if role not in ("customer", "worker"):
        raise ValueError("Invalid account type.")

    password_hash = generate_password_hash(password)
    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("""
            INSERT INTO users (name, email, password_hash, phone, address, role)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (name, email, password_hash, phone, address, role))
        connection.commit()
        return cursor.lastrowid

    except Exception as error:
        connection.rollback()
        # MySQL duplicate email error
        if getattr(error, "errno", None) == 1062:
            raise ValueError("This email is already registered.") from error
        raise

    finally:
        cursor.close()
        connection.close()


def authenticate_user(email, password):
    email = email.strip().lower()

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT id, name, email, password_hash, role
            FROM users
            WHERE email = %s
            LIMIT 1
        """, (email,))

        user = cursor.fetchone()

        if not user or not check_password_hash(
            user["password_hash"], password
        ):
            return None

        return {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"],
            "role": user["role"],
        }

    finally:
        cursor.close()
        connection.close()
