
from backend.db import get_db_connection


def get_recommended_products(user_id, limit=8):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        # Find categories the customer has purchased most often.
        cursor.execute("""
            SELECT p.category_id, COUNT(*) AS purchase_count
            FROM orders o
            JOIN order_items oi ON oi.order_id = o.id
            JOIN products p ON p.id = oi.product_id
            WHERE o.user_id = %s
              AND o.order_status != 'cancelled'
            GROUP BY p.category_id
            ORDER BY purchase_count DESC
            LIMIT 5
        """, (user_id,))

        categories = [
            row["category_id"] for row in cursor.fetchall()
        ]

        # Recommend in those categories, excluding products already
        # purchased by this customer.
        if categories:
            placeholders = ",".join(["%s"] * len(categories))

            query = f"""
                SELECT
                    p.id,
                    p.name,
                    p.description,
                    p.price,
                    p.image_url,
                    p.stock_quantity,
                    c.name AS category_name
                FROM products p
                LEFT JOIN categories c ON c.id = p.category_id
                WHERE p.is_active = 1
                  AND p.stock_quantity > 0
                  AND p.category_id IN ({placeholders})
                  AND NOT EXISTS (
                      SELECT 1
                      FROM orders o
                      JOIN order_items oi ON oi.order_id = o.id
                      WHERE o.user_id = %s
                        AND o.order_status != 'cancelled'
                        AND oi.product_id = p.id
                  )
                ORDER BY p.stock_quantity DESC, p.name
                LIMIT %s
            """

            cursor.execute(
                query,
                tuple(categories) + (user_id, limit)
            )
            products = cursor.fetchall()

        else:
            # New customers receive popular products as a starting point.
            cursor.execute("""
                SELECT
                    p.id,
                    p.name,
                    p.description,
                    p.price,
                    p.image_url,
                    p.stock_quantity,
                    c.name AS category_name
                FROM products p
                LEFT JOIN categories c ON c.id = p.category_id
                WHERE p.is_active = 1
                  AND p.stock_quantity > 0
                ORDER BY p.id DESC
                LIMIT %s
            """, (limit,))
            products = cursor.fetchall()

        return products

    finally:
        cursor.close()
        connection.close()
