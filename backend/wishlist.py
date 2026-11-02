
from backend.db import get_db_connection


def get_wishlist(user_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT
                p.id AS product_id,
                p.name,
                p.description,
                p.price,
                p.stock_quantity,
                p.image_url,
                c.name AS category,
                w.created_at
            FROM wishlist w
            JOIN products p ON p.id = w.product_id
            LEFT JOIN categories c ON c.id = p.category_id
            WHERE w.user_id = %s AND p.is_active = TRUE
            ORDER BY w.created_at DESC
        """, (user_id,))

        return cursor.fetchall()

    finally:
        cursor.close()
        connection.close()


def add_to_wishlist(user_id, product_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT id FROM products
            WHERE id = %s AND is_active = TRUE
            LIMIT 1
        """, (product_id,))

        if not cursor.fetchone():
            raise ValueError("Product not found or unavailable.")

        cursor.execute("""
            INSERT INTO wishlist (user_id, product_id)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE
                product_id = VALUES(product_id)
        """, (user_id, product_id))

        connection.commit()

    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def remove_from_wishlist(user_id, product_id):
    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("""
            DELETE FROM wishlist
            WHERE user_id = %s AND product_id = %s
        """, (user_id, product_id))

        connection.commit()
        return cursor.rowcount > 0

    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()

