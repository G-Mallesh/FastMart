
from backend.db import get_db_connection


def get_suppliers():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT id, supplier_name, phone, email, address
            FROM suppliers
            WHERE is_active = TRUE
            ORDER BY supplier_name
        """)
        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()


def get_restocking_data():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT id, name, stock_quantity
            FROM products
            WHERE is_active = TRUE
            ORDER BY name
        """)
        products = cursor.fetchall()

        cursor.execute("""
            SELECT
                r.id, r.quantity, r.unit_cost,
                r.reference_number, r.status,
                r.created_at, r.received_at,
                s.supplier_name,
                p.name AS product_name
            FROM restock_orders r
            JOIN suppliers s ON s.id = r.supplier_id
            JOIN products p ON p.id = r.product_id
            ORDER BY r.id DESC
            LIMIT 100
        """)
        orders = cursor.fetchall()

        return products, orders
    finally:
        cursor.close()
        connection.close()


def add_supplier(name, phone="", email="", address=""):
    name = name.strip()
    if not name:
        raise ValueError("Supplier name is required.")

    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("""
            INSERT INTO suppliers
                (supplier_name, phone, email, address)
            VALUES (%s, %s, %s, %s)
        """, (
            name,
            phone.strip() or None,
            email.strip() or None,
            address.strip() or None,
        ))
        connection.commit()
        return cursor.lastrowid
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def create_restock_order(
    supplier_id, product_id, quantity, unit_cost,
    reference_number, admin_id
):
    if quantity <= 0:
        raise ValueError("Quantity must be greater than zero.")
    if unit_cost < 0:
        raise ValueError("Unit cost cannot be negative.")

    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        connection.start_transaction()

        cursor.execute(
            "SELECT id FROM suppliers "
            "WHERE id = %s AND is_active = TRUE FOR UPDATE",
            (supplier_id,)
        )
        if not cursor.fetchone():
            raise ValueError("Select an active supplier.")

        cursor.execute(
            "SELECT id FROM products "
            "WHERE id = %s AND is_active = TRUE FOR UPDATE",
            (product_id,)
        )
        if not cursor.fetchone():
            raise ValueError("Select an active product.")

        cursor.execute("""
            INSERT INTO restock_orders (
                supplier_id, product_id, quantity, unit_cost,
                reference_number, created_by
            )
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            supplier_id, product_id, quantity, unit_cost,
            reference_number.strip() or None, admin_id
        ))

        restock_id = cursor.lastrowid
        connection.commit()
        return restock_id

    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def receive_restock_order(restock_id):
    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        connection.start_transaction()

        cursor.execute("""
            SELECT product_id, quantity, status
            FROM restock_orders
            WHERE id = %s
            FOR UPDATE
        """, (restock_id,))

        restock = cursor.fetchone()

        if not restock:
            raise ValueError("Restocking order not found.")

        product_id, quantity, status = restock

        if status != "ordered":
            raise ValueError(
                "Only an ordered restocking record can be received."
            )

        cursor.execute("""
            UPDATE products
            SET stock_quantity = stock_quantity + %s
            WHERE id = %s
        """, (quantity, product_id))

        if cursor.rowcount != 1:
            raise ValueError("Product stock could not be updated.")

        cursor.execute("""
            UPDATE restock_orders
            SET status = 'received', received_at = CURRENT_TIMESTAMP
            WHERE id = %s AND status = 'ordered'
        """, (restock_id,))

        if cursor.rowcount != 1:
            raise ValueError("Restocking status could not be updated.")

        connection.commit()

    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()
