
from getpass import getpass
from werkzeug.security import generate_password_hash
from backend.db import get_db_connection


def main():
    name = input("Admin name: ").strip()
    email = input("Admin email: ").strip().lower()
    password = getpass("Create admin password (8+ characters): ")

    if len(name) < 2 or len(email) > 254 or "@" not in email:
        print("Enter a valid name and email.")
        return

    if len(password) < 8 or len(password) > 128:
        print("Password must contain 8 to 128 characters.")
        return

    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("""
            INSERT INTO users
                (name, email, password_hash, phone, address, role)
            VALUES (%s, %s, %s, %s, %s, 'admin')
        """, (
            name,
            email,
            generate_password_hash(password),
            "Admin account",
            "Admin office",
        ))

        connection.commit()
        print("Admin account created successfully.")
    except Exception as error:
        connection.rollback()
        if getattr(error, "errno", None) == 1062:
            print("That email is already registered.")
        else:
            print("Admin account creation failed:", error)
    finally:
        cursor.close()
        connection.close()


if __name__ == "__main__":
    main()
