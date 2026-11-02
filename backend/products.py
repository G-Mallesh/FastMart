
from backend.db import get_db_connection


from backend.db import get_db_connection


def search_products(keyword="", category_id=None,
                    min_price=None, max_price=None):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        conditions = ["p.is_active = 1"]
        params = []

        if keyword.strip():
            conditions.append("p.name LIKE %s")
            params.append("%" + keyword.strip() + "%")

        if category_id:
            conditions.append("p.category_id = %s")
            params.append(category_id)

        if min_price is not None:
            conditions.append("p.price >= %s")
            params.append(min_price)

        if max_price is not None:
            conditions.append("p.price <= %s")
            params.append(max_price)

        where_clause = " AND ".join(conditions)

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
            WHERE {where_clause}
            ORDER BY p.name ASC
            LIMIT 100
        """

        cursor.execute(query, tuple(params))
        return cursor.fetchall()

    finally:
        cursor.close()
        connection.close()


def autocomplete_products(keyword, limit=8):
    keyword = keyword.strip()

    if len(keyword) < 2:
        return []

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT id, name, price, image_url
            FROM products
            WHERE is_active = 1
              AND name LIKE %s
            ORDER BY name ASC
            LIMIT %s
        """, ("%" + keyword + "%", limit))

        return cursor.fetchall()

    finally:
        cursor.close()
        connection.close()

def get_all_products():
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                p.id,
                p.name,
                p.description,
                p.price,
                p.stock_quantity,
                p.image_url,
                c.name AS category,

                (
                    SELECT AVG(r.rating)
                    FROM product_reviews AS r
                    WHERE r.product_id = p.id
                ) AS average_rating,

                (
                    SELECT COUNT(*)
                    FROM product_reviews AS r
                    WHERE r.product_id = p.id
                ) AS review_count

            FROM products AS p

            LEFT JOIN categories AS c
                ON p.category_id = c.id

            WHERE p.is_active = TRUE

            ORDER BY p.name
        """)

        return cursor.fetchall()

    finally:
        if cursor:
            cursor.close()

        if connection and connection.is_connected():
            connection.close()
