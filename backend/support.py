
from backend.db import get_db_connection


ALLOWED_CATEGORIES = {
    "missing_item",
    "damaged_item",
    "late_delivery",
    "payment_issue",
    "other",
}


def create_complaint(
    user_id, order_id, subject, category, description
):
    subject = subject.strip()
    description = description.strip()

    if not subject or len(subject) > 150:
        return False, "Enter a subject of 1–150 characters."

    if not description or len(description) > 5000:
        return False, "Enter a description of 1–5000 characters."

    if category not in ALLOWED_CATEGORIES:
        return False, "Choose a valid complaint category."

    if order_id in ("", None):
        order_id = None
    else:
        try:
            order_id = int(order_id)
            if order_id < 1:
                raise ValueError
        except (ValueError, TypeError):
            return False, "Invalid order number."

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        if order_id is not None:
            cursor.execute("""
                SELECT id FROM orders
                WHERE id = %s AND user_id = %s
            """, (order_id, user_id))

            if not cursor.fetchone():
                return False, "That order does not belong to your account."

        cursor.execute("""
            INSERT INTO complaints
                (user_id, order_id, subject, category, description)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            user_id, order_id, subject, category, description
        ))

        connection.commit()
        return True, "Your complaint was submitted successfully."

    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def get_customer_complaints(user_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT id, order_id, subject, category, description,
                   status, admin_response, created_at, updated_at
            FROM complaints
            WHERE user_id = %s
            ORDER BY created_at DESC
        """, (user_id,))

        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()


def get_all_complaints():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT
                c.id, c.user_id, c.order_id, c.subject,
                c.category, c.description, c.status,
                c.admin_response, c.created_at, c.updated_at,
                u.name AS customer_name,
                u.email AS customer_email
            FROM complaints c
            JOIN users u ON u.id = c.user_id
            ORDER BY
                CASE WHEN c.status = 'open' THEN 0 ELSE 1 END,
                c.created_at DESC
        """)

        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()


def update_complaint(complaint_id, status, response):
    allowed_statuses = {
        "open", "in_progress", "resolved", "rejected"
    }

    if status not in allowed_statuses:
        return False, "Invalid complaint status."

    response = (response or "").strip()

    if len(response) > 5000:
        return False, "The response must be 5000 characters or fewer."

    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("""
            UPDATE complaints
            SET status = %s, admin_response = %s
            WHERE id = %s
        """, (status, response or None, complaint_id))

        if cursor.rowcount == 0:
            cursor.execute(
                "SELECT id FROM complaints WHERE id = %s",
                (complaint_id,)
            )
            if not cursor.fetchone():
                connection.rollback()
                return False, "Complaint not found."

        connection.commit()
        return True, "Complaint updated successfully."

    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()
