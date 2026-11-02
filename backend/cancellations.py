
from backend.db import get_db_connection


def cancel_customer_order(order_id, user_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        connection.start_transaction()

        # Lock the customer's order while checking its status.
        cursor.execute("""
            SELECT id, order_status, payment_status
            FROM orders
            WHERE id = %s AND user_id = %s
            FOR UPDATE
        """, (order_id, user_id))

        order = cursor.fetchone()

        if not order:
            connection.rollback()
            return False, "Order not found."

        if order["order_status"] != "confirmed":
            connection.rollback()
            return False, (
                "Only confirmed orders can be cancelled online."
            )

        # Lock the order items before restoring stock.
        cursor.execute("""
            SELECT product_id, quantity
            FROM order_items
            WHERE order_id = %s
            FOR UPDATE
        """, (order_id,))

        items = cursor.fetchall()

        if not items:
            connection.rollback()
            return False, "No order items were found."

        for item in items:
            cursor.execute("""
                UPDATE products
                SET stock_quantity = stock_quantity + %s
                WHERE id = %s
            """, (item["quantity"], item["product_id"]))

            if cursor.rowcount != 1:
                raise RuntimeError(
                    "A product was missing while restoring stock."
                )

        # The order status and stock changes commit together.
        cursor.execute("""
            UPDATE orders
            SET order_status = 'cancelled'
            WHERE id = %s AND user_id = %s
              AND order_status = 'confirmed'
        """, (order_id, user_id))

        if cursor.rowcount != 1:
            raise RuntimeError(
                "The order status changed unexpectedly."
            )

        connection.commit()
        return True, "Order cancelled successfully. Stock restored."

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()
