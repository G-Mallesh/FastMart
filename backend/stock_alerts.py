
from backend.db import get_db_connection


def get_low_stock_products():
    """Return active products at or below their stock threshold."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT
                id,
                name,
                stock_quantity,
                low_stock_threshold,
                price
            FROM products
            WHERE is_active = 1
              AND stock_quantity <= low_stock_threshold
            ORDER BY stock_quantity ASC, name ASC
        """)

        return cursor.fetchall()

    finally:
        cursor.close()
        connection.close()


def update_stock_threshold(product_id, threshold):
    """Update the low-stock threshold for a product."""
    if not isinstance(threshold, int) or threshold < 0:
        raise ValueError("Threshold must be a non-negative integer.")

    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("""
            UPDATE products
            SET low_stock_threshold = %s
            WHERE id = %s
        """, (threshold, product_id))

        connection.commit()
        return cursor.rowcount > 0

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()
