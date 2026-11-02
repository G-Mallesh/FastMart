
from backend.db import get_db_connection


def get_product_with_rating(product_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT
                p.id, p.name, p.description, p.price,
                p.stock_quantity, p.image_url,
                c.name AS category,
                COALESCE(AVG(r.rating), 0) AS average_rating,
                COUNT(r.id) AS review_count
            FROM products p
            LEFT JOIN categories c ON c.id = p.category_id
            LEFT JOIN product_reviews r ON r.product_id = p.id
            WHERE p.id = %s AND p.is_active = TRUE
            GROUP BY p.id, p.name, p.description, p.price,
                     p.stock_quantity, p.image_url, c.name
            LIMIT 1
        """, (product_id,))

        return cursor.fetchone()
    finally:
        cursor.close()
        connection.close()


def get_product_reviews(product_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT r.rating, r.comment, r.created_at,
                   u.name AS customer_name
            FROM product_reviews r
            JOIN users u ON u.id = r.user_id
            WHERE r.product_id = %s
            ORDER BY r.created_at DESC, r.id DESC
        """, (product_id,))

        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()


def add_product_review(product_id, user_id, rating, comment):
    comment = (comment or "").strip()

    if not 1 <= rating <= 5:
        raise ValueError("Please choose a rating from 1 to 5.")

    if not comment or len(comment) > 1000:
        raise ValueError("Write a review of 1 to 1000 characters.")

    connection = get_db_connection()
    cursor = None

    try:
        connection.start_transaction()
        cursor = connection.cursor(dictionary=True)

        # Only customers who have received this product can review it.
        cursor.execute("""
            SELECT oi.id
            FROM order_items oi
            JOIN orders o ON o.id = oi.order_id
            WHERE oi.product_id = %s
              AND o.user_id = %s
              AND o.order_status = 'delivered'
            LIMIT 1
            FOR UPDATE
        """, (product_id, user_id))

        if not cursor.fetchone():
            raise ValueError(
                "You can review this product after your order is delivered."
            )

        cursor.execute("""
            SELECT id FROM products
            WHERE id = %s AND is_active = TRUE
            LIMIT 1
        """, (product_id,))

        if not cursor.fetchone():
            raise ValueError("This product is unavailable.")

        cursor.execute("""
            INSERT INTO product_reviews
                (product_id, user_id, rating, comment)
            VALUES (%s, %s, %s, %s)
        """, (product_id, user_id, rating, comment))

        connection.commit()

    except Exception as error:
        connection.rollback()

        if getattr(error, "errno", None) == 1062:
            raise ValueError(
                "You have already reviewed this product."
            ) from error

        raise
    finally:
        if cursor:
            cursor.close()
        connection.close()
