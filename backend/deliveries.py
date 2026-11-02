
from backend.db import get_db_connection

from backend.db import get_db_connection

from backend.loyalty import award_points_for_delivered_order
def get_order_destination(order_id, customer_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT delivery_latitude, delivery_longitude
            FROM orders
            WHERE id = %s AND user_id = %s
            LIMIT 1
        """, (order_id, customer_id))

        return cursor.fetchone()
    finally:
        cursor.close()
        connection.close()

def save_delivery_location(delivery_id, worker_id, latitude, longitude):
    """Save a location only if this worker owns the active delivery."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT id, status
            FROM deliveries
            WHERE id = %s AND worker_id = %s
            FOR UPDATE
        """, (delivery_id, worker_id))

        delivery = cursor.fetchone()

        if not delivery:
            raise ValueError("This delivery is not assigned to you.")

        if delivery["status"] not in ("assigned", "picked_up"):
            raise ValueError("Location sharing is not available for this delivery.")

        cursor.execute("""
            INSERT INTO delivery_locations
                (delivery_id, worker_id, latitude, longitude)
            VALUES (%s, %s, %s, %s)
        """, (delivery_id, worker_id, latitude, longitude))

        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def get_latest_delivery_location(order_id, customer_id):
    """Return the latest location only to the customer who owns the order."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT
                dl.latitude,
                dl.longitude,
                dl.recorded_at,
                d.status AS delivery_status
            FROM orders o
            JOIN deliveries d ON d.order_id = o.id
            JOIN delivery_locations dl ON dl.delivery_id = d.id
            WHERE o.id = %s
              AND o.user_id = %s
            ORDER BY dl.recorded_at DESC, dl.id DESC
            LIMIT 1
        """, (order_id, customer_id))

        return cursor.fetchone()
    finally:
        cursor.close()
        connection.close()


def get_worker_deliveries(worker_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT
                d.id AS delivery_id,
                d.delivery_status,
                d.assigned_at,
                d.delivered_at,
                o.id AS order_id,
                o.delivery_latitude,
                o.delivery_longitude,
                o.delivery_address,
                o.total_amount,
                o.payment_status,
                o.order_status,
            FROM deliveries AS d
            JOIN orders AS o ON o.id = d.order_id
            WHERE d.worker_id = %s
               OR d.delivery_status = 'waiting'
            ORDER BY
                CASE
                    WHEN d.delivery_status = 'waiting' THEN 0
                    ELSE 1
                END,
                d.id DESC
        """, (worker_id,))

        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()


def update_delivery(delivery_id, worker_id, action):
    connection = get_db_connection()
    cursor = None

    try:
        connection.start_transaction()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                d.id,
                d.worker_id,
                d.delivery_status,
                d.order_id
            FROM deliveries AS d
            JOIN orders AS o ON o.id = d.order_id
            WHERE d.id = %s
            FOR UPDATE
        """, (delivery_id,))

        delivery = cursor.fetchone()

        if not delivery:
            raise ValueError("Delivery not found.")

        status = delivery["delivery_status"]
        assigned_worker = delivery["worker_id"]
        order_id = delivery["order_id"]

        if action == "accept":
            if status != "waiting" or assigned_worker is not None:
                raise ValueError("This delivery is no longer available.")

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
                raise ValueError("Another worker accepted this delivery.")

        else:
            if assigned_worker != worker_id:
                raise ValueError("This delivery is not assigned to you.")

            if action == "pickup":
                if status != "assigned":
                    raise ValueError("Only assigned deliveries can be picked up.")

                cursor.execute("""
                    UPDATE deliveries
                    SET delivery_status = 'picked_up'
                    WHERE id = %s AND worker_id = %s
                """, (delivery_id, worker_id))

                cursor.execute("""
                    UPDATE orders
                    SET order_status = 'out_for_delivery'
                    WHERE id = %s
                """, (order_id,))

            elif action == "deliver":
                if status != "picked_up":
                    raise ValueError("Pick up the order before marking it delivered.")

                cursor.execute("""
                    UPDATE deliveries
                    SET delivery_status = 'delivered',
                        delivered_at = CURRENT_TIMESTAMP
                    WHERE id = %s AND worker_id = %s
                """, (delivery_id, worker_id))

                cursor.execute("""
                    UPDATE orders
                    SET order_status = 'delivered'
                    WHERE id = %s
                """, (order_id,)),
                award_points_for_delivered_order(order_id)

            else:
                raise ValueError("Invalid delivery action.")

        connection.commit()
        return True

    except Exception:
        connection.rollback()
        raise

    finally:
        if cursor:
            cursor.close()
        connection.close()
