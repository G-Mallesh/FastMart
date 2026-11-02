
from backend.db import get_db_connection


from decimal import Decimal


def validate_loyalty_redemption(
    connection, user_id, requested_points, subtotal, coupon_discount=Decimal("0.00")
):
    """
    Validate a redemption inside the order transaction.
    Returns (points, discount). Does not deduct points yet.
    """
    if requested_points is None:
        requested_points = 0

    if not isinstance(requested_points, int):
        raise ValueError("Invalid loyalty points amount.")

    if requested_points < 0 or requested_points % 100 != 0:
        raise ValueError("Redeem points in multiples of 100.")

    if requested_points == 0:
        return 0, Decimal("0.00")

    if not user_id:
        raise ValueError("Log in to redeem loyalty points.")

    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT points_balance
            FROM loyalty_accounts
            WHERE user_id = %s
            FOR UPDATE
        """, (user_id,))

        account = cursor.fetchone()

        if not account or account["points_balance"] < requested_points:
            raise ValueError("You do not have enough loyalty points.")

        discount = (
            Decimal(requested_points) / Decimal("100")
            * Decimal("10")
        )

        remaining_subtotal = (
            Decimal(str(subtotal)) - Decimal(str(coupon_discount))
        )

        if discount > remaining_subtotal:
            raise ValueError(
                "The requested points exceed the remaining order value."
            )

        return requested_points, discount

    finally:
        cursor.close()


def record_loyalty_redemption(
    connection, user_id, order_id, points, discount
):
    """Deduct points and record redemption in the current transaction."""
    if points <= 0:
        return

    cursor = connection.cursor()

    try:
        cursor.execute("""
            UPDATE loyalty_accounts
            SET points_balance = points_balance - %s
            WHERE user_id = %s
              AND points_balance >= %s
        """, (points, user_id, points))

        if cursor.rowcount != 1:
            raise ValueError(
                "Your points balance changed. Please try again."
            )

        cursor.execute("""
            INSERT INTO loyalty_transactions
                (user_id, order_id, transaction_type,
                 points, description)
            VALUES (%s, %s, 'redeem', %s, %s)
        """, (
            user_id,
            order_id,
            -points,
            f"Points redeemed for order #{order_id}; discount ₹{discount}",
        ))

    finally:
        cursor.close()

POINTS_PER_RUPEES = 10
POINTS_PER_REDEMPTION = 100
RUPEES_PER_REDEMPTION = 10


def get_loyalty_balance(user_id):
    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("""
            SELECT points_balance
            FROM loyalty_accounts
            WHERE user_id = %s
        """, (user_id,))

        row = cursor.fetchone()
        return int(row[0]) if row else 0
    finally:
        cursor.close()
        connection.close()


def award_points_for_delivered_order(order_id):
    """
    Award points once for an eligible delivered order.
    Returns the number of points awarded, or zero if
    the order is ineligible or already rewarded.
    """
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        connection.start_transaction()

        cursor.execute("""
            SELECT id, user_id, order_status, subtotal,
                   discount_amount
            FROM orders
            WHERE id = %s
            FOR UPDATE
        """, (order_id,))

        order = cursor.fetchone()

        if (
            not order
            or order["user_id"] is None
            or order["order_status"] != "delivered"
        ):
            connection.rollback()
            return 0

        # Award points based on the post-discount merchandise value.
        eligible_value = max(
            0,
            int(order["subtotal"] * 100)
            - int((order["discount_amount"] or 0) * 100)
        )

        points = eligible_value // (POINTS_PER_RUPEES * 100)

        if points <= 0:
            connection.rollback()
            return 0

        cursor.execute("""
            INSERT INTO loyalty_accounts (user_id, points_balance)
            VALUES (%s, 0)
            ON DUPLICATE KEY UPDATE user_id = VALUES(user_id)
        """, (order["user_id"],))

        cursor.execute("""
            SELECT points_balance
            FROM loyalty_accounts
            WHERE user_id = %s
            FOR UPDATE
        """, (order["user_id"],))

        cursor.fetchone()

        cursor.execute("""
            INSERT INTO loyalty_transactions
                (user_id, order_id, transaction_type,
                 points, description)
            VALUES (%s, %s, 'earn', %s, %s)
        """, (
            order["user_id"],
            order_id,
            points,
            f"Rewards for delivered order #{order_id}",
        ))

        cursor.execute("""
            UPDATE loyalty_accounts
            SET points_balance = points_balance + %s
            WHERE user_id = %s
        """, (points, order["user_id"]))

        connection.commit()
        return points

    except Exception as error:
        connection.rollback()

        # A duplicate earning transaction means this order
        # has already been rewarded.
        if getattr(error, "errno", None) == 1062:
            return 0
        raise

    finally:
        cursor.close()
        connection.close()


def get_loyalty_history(user_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT order_id, transaction_type, points,
                   description, created_at
            FROM loyalty_transactions
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT 100
        """, (user_id,))

        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()
