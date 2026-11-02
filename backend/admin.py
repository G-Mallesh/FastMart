
from backend.db import get_db_connection


def get_admin_report():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT
                COUNT(*) AS total_orders,
                COALESCE(SUM(
                    CASE
                        WHEN order_status = 'delivered'
                         AND payment_status = 'paid'
                        THEN total_amount ELSE 0
                    END
                ), 0) AS paid_revenue,
                SUM(CASE WHEN order_status = 'pending'
                         THEN 1 ELSE 0 END) AS pending_orders,
                SUM(CASE WHEN order_status = 'packed'
                         THEN 1 ELSE 0 END) AS packed_orders,
                SUM(CASE WHEN order_status = 'out_for_delivery'
                         THEN 1 ELSE 0 END) AS out_for_delivery_orders,
                SUM(CASE WHEN order_status = 'delivered'
                         THEN 1 ELSE 0 END) AS delivered_orders
            FROM orders
        """)
        summary = cursor.fetchone()

        cursor.execute("""
            SELECT id, name, stock_quantity, price
            FROM products
            WHERE is_active = TRUE AND stock_quantity < 10
            ORDER BY stock_quantity ASC, name ASC
        """)
        low_stock_products = cursor.fetchall()

        cursor.execute("""
            SELECT o.id AS order_id, u.name AS customer_name,
                   o.total_amount, o.order_status, o.payment_status,
                   o.created_at
            FROM orders o
            LEFT JOIN users u ON u.id = o.user_id
            ORDER BY o.created_at DESC, o.id DESC
            LIMIT 20
        """)
        recent_orders = cursor.fetchall()

        return {
            "summary": summary,
            "low_stock_products": low_stock_products,
            "recent_orders": recent_orders,
        }

    finally:
        cursor.close()
        connection.close()


def mark_order_packed(order_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        connection.start_transaction()

        cursor.execute("""
            SELECT o.id, o.order_status, o.payment_status,
                   p.payment_method
            FROM orders o
            LEFT JOIN payments p ON p.order_id = o.id
            WHERE o.id = %s
            FOR UPDATE
        """, (order_id,))
        order = cursor.fetchone()

        if not order:
            raise ValueError("Order not found.")

        if order["order_status"] != "confirmed":
            raise ValueError("Only confirmed orders can be packed.")

        # COD orders may still be unpaid. Online orders must be paid.
        if (
            order["payment_method"] == "razorpay"
            and order["payment_status"] != "paid"
        ):
            raise ValueError("Online payment must be verified before packing.")

        cursor.execute("""
            UPDATE orders
            SET order_status = 'packed'
            WHERE id = %s AND order_status = 'confirmed'
        """, (order_id,))

        if cursor.rowcount != 1:
            raise ValueError("Order status changed. Refresh and try again.")

        connection.commit()

    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()

def get_available_workers():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT id, name, email
            FROM users
            WHERE role = 'worker'
            ORDER BY name
        """)
        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()


def get_waiting_deliveries():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT
                d.id AS delivery_id,
                d.order_id,
                o.delivery_address,
                o.total_amount,
                o.order_status
            FROM deliveries d
            JOIN orders o ON o.id = d.order_id
            WHERE d.delivery_status = 'waiting'
              AND d.worker_id IS NULL
            ORDER BY d.id
        """)
        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()


def assign_delivery(delivery_id, worker_id):
    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        connection.start_transaction()

        cursor.execute("""
            SELECT id
            FROM users
            WHERE id = %s AND role = 'worker'
            FOR UPDATE
        """, (worker_id,))

        if not cursor.fetchone():
            raise ValueError("Select a valid delivery worker.")

        cursor.execute("""
            UPDATE deliveries
            SET worker_id = %s,
                delivery_status = 'assigned',
                assigned_at = CURRENT_TIMESTAMP
            WHERE id = %s
              AND worker_id IS NULL
              AND delivery_status = 'waiting'
        """, (worker_id, delivery_id))

        if cursor.rowcount != 1:
            raise ValueError(
                "Delivery is no longer waiting or has already been assigned."
            )

        connection.commit()

    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()

def get_admin_summary():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("SELECT COUNT(*) AS total FROM users WHERE role='customer'")
        customers = cursor.fetchone()["total"]

        cursor.execute("SELECT COUNT(*) AS total FROM users WHERE role='worker'")
        workers = cursor.fetchone()["total"]

        cursor.execute("SELECT COUNT(*) AS total FROM products WHERE is_active=TRUE")
        products = cursor.fetchone()["total"]

        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM orders
            WHERE order_status NOT IN ('delivered', 'cancelled')
        """)
        active_orders = cursor.fetchone()["total"]

        cursor.execute("""
            SELECT COALESCE(SUM(total_amount), 0) AS total
            FROM orders
            WHERE order_status = 'delivered'
              AND payment_status = 'paid'
        """)
        revenue = cursor.fetchone()["total"]

        return {
            "customers": customers,
            "workers": workers,
            "products": products,
            "active_orders": active_orders,
            "revenue": float(revenue),
        }
    finally:
        cursor.close()
        connection.close()


def get_admin_products():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT p.id, p.name, p.price, p.stock_quantity,
                   p.is_active, c.name AS category
            FROM products p
            LEFT JOIN categories c ON c.id = p.category_id
            ORDER BY p.id DESC
        """)
        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()


def update_product_stock(product_id, stock_quantity):
    if stock_quantity < 0 or stock_quantity > 1000000:
        raise ValueError("Stock must be between 0 and 1,000,000.")

    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("""
            UPDATE products
            SET stock_quantity = %s
            WHERE id = %s
        """, (stock_quantity, product_id))

        if cursor.rowcount == 0:
            cursor.execute("SELECT id FROM products WHERE id = %s", (product_id,))
            if not cursor.fetchone():
                raise ValueError("Product not found.")

        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def get_admin_orders():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT
                o.id AS order_id,
                o.delivery_address,
                o.total_amount,
                o.order_status,
                o.payment_status,
                o.created_at,
                u.name AS customer_name,
                d.delivery_status,
                w.name AS worker_name
            FROM orders o
            LEFT JOIN users u ON u.id = o.user_id
            LEFT JOIN deliveries d ON d.order_id = o.id
            LEFT JOIN users w ON w.id = d.worker_id
            ORDER BY o.id DESC
            LIMIT 200
        """)
        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()
