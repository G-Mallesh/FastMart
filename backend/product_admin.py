
from decimal import Decimal, InvalidOperation
from backend.db import get_db_connection


def get_categories():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id, name FROM categories ORDER BY name")
        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()


def save_product(
    name, category_id, description, price, stock_quantity,
    image_url, product_id=None
):
    name = name.strip()
    description = description.strip()
    image_url = image_url.strip()

    if not name or len(name) > 150:
        raise ValueError("Product name is required (maximum 150 characters).")

    if len(description) > 2000:
        raise ValueError("Description cannot exceed 2000 characters.")

    if len(image_url) > 1000:
        raise ValueError("Image URL is too long.")

    try:
        price = Decimal(str(price))
    except (InvalidOperation, ValueError):
        raise ValueError("Enter a valid product price.")

    if not price.is_finite() or price < 0 or price > Decimal("99999999.99"):
        raise ValueError("Price must be between ₹0 and ₹99,999,999.99.")

    if stock_quantity < 0 or stock_quantity > 1000000:
        raise ValueError("Stock must be between 0 and 1,000,000.")

    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        if category_id is not None:
            cursor.execute(
                "SELECT id FROM categories WHERE id = %s",
                (category_id,)
            )
            if not cursor.fetchone():
                raise ValueError("Select a valid category.")

        if product_id is None:
            cursor.execute("""
                INSERT INTO products
                    (category_id, name, description, price,
                     stock_quantity, image_url, is_active)
                VALUES (%s, %s, %s, %s, %s, %s, TRUE)
            """, (
                category_id, name, description, price,
                stock_quantity, image_url or None
            ))
        else:
            cursor.execute("""
                UPDATE products
                SET category_id = %s,
                    name = %s,
                    description = %s,
                    price = %s,
                    stock_quantity = %s,
                    image_url = %s
                WHERE id = %s
            """, (
                category_id, name, description, price,
                stock_quantity, image_url or None, product_id
            ))

            if cursor.rowcount == 0:
                cursor.execute(
                    "SELECT id FROM products WHERE id = %s",
                    (product_id,)
                )
                if not cursor.fetchone():
                    raise ValueError("Product not found.")

        connection.commit()

    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def set_product_active(product_id, is_active):
    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("""
            UPDATE products
            SET is_active = %s
            WHERE id = %s
        """, (is_active, product_id))

        if cursor.rowcount == 0:
            cursor.execute(
                "SELECT id FROM products WHERE id = %s",
                (product_id,)
            )
            if not cursor.fetchone():
                raise ValueError("Product not found.")

        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def get_product_for_admin(product_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT id, category_id, name, description, price,
                   stock_quantity, image_url, is_active
            FROM products
            WHERE id = %s
        """, (product_id,))
        return cursor.fetchone()
    finally:
        cursor.close()
        connection.close()
