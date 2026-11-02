
from decimal import Decimal

from backend.db import get_db_connection
from backend.coupons import validate_coupon
from backend.coupons import apply_coupon_in_transaction
from backend.loyalty import (
    validate_loyalty_redemption,
    record_loyalty_redemption,
)

DELIVERY_FEE = Decimal("40.00")
FREE_DELIVERY_MINIMUM = Decimal("500.00")


def get_order_tracking(order_id, user_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT
                o.id AS order_id,
                o.order_status,
                o.payment_status,
                o.subtotal,
                o.discount_amount,
                o.coupon_code,
                o.delivery_fee,
                o.total_amount,
                o.delivery_address,
                o.created_at,
                d.delivery_status,
                d.assigned_at,
                d.delivered_at,
                u.name AS worker_name,
                u.phone AS worker_phone
            FROM orders o
            LEFT JOIN deliveries d ON d.order_id = o.id
            LEFT JOIN users u ON u.id = d.worker_id
            WHERE o.id = %s AND o.user_id = %s
            LIMIT 1
            """,
            (order_id, user_id),
        )

        order = cursor.fetchone()

        if not order:
            return None

        cursor.execute(
            """
            SELECT product_name, unit_price, quantity, line_total
            FROM order_items
            WHERE order_id = %s
            ORDER BY id
            """,
            (order_id,),
        )

        order["items"] = cursor.fetchall()
        return order

    finally:
        cursor.close()
        connection.close()


def cancel_failed_online_order(order_id, user_id):
    connection = get_db_connection()
    cursor = None

    try:
        connection.start_transaction()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                o.id,
                o.order_status,
                o.payment_status,
                p.status AS payment_row_status
            FROM orders o
            JOIN payments p ON p.order_id = o.id
            WHERE o.id = %s
              AND o.user_id = %s
              AND p.payment_method = 'razorpay'
            FOR UPDATE
            """,
            (order_id, user_id),
        )

        order = cursor.fetchone()

        if not order:
            raise ValueError("Online order not found.")

        if (
            order["order_status"] != "pending"
            or order["payment_status"] != "pending"
            or order["payment_row_status"] != "pending"
        ):
            raise ValueError(
                "This order cannot be cancelled as a pending payment."
            )

        cursor.execute(
            """
            SELECT product_id, quantity
            FROM order_items
            WHERE order_id = %s AND product_id IS NOT NULL
            """,
            (order_id,),
        )

        items = cursor.fetchall()

        for item in items:
            cursor.execute(
                """
                UPDATE products
                SET stock_quantity = stock_quantity + %s
                WHERE id = %s
                """,
                (item["quantity"], item["product_id"]),
            )

            if cursor.rowcount != 1:
                raise ValueError("Could not restore product stock.")

        cursor.execute(
            """
            UPDATE payments
            SET status = 'failed'
            WHERE order_id = %s AND status = 'pending'
            """,
            (order_id,),
        )

        cursor.execute(
            """
            UPDATE orders
            SET order_status = 'cancelled',
                payment_status = 'failed'
            WHERE id = %s
              AND order_status = 'pending'
              AND payment_status = 'pending'
            """,
            (order_id,),
        )

        if cursor.rowcount != 1:
            raise ValueError("Order status changed. Please check again.")

        connection.commit()
        return True

    except Exception:
        connection.rollback()
        raise

    finally:
        if cursor:
            cursor.close()
        connection.close()


def create_online_order(
    cart_data,
    delivery_address,
    user_id,
    coupon_code=None,
):
    """Create a pending Razorpay order with a server-validated coupon."""

    if not user_id:
        raise ValueError("Please log in before using online payment.")

    if not cart_data:
        raise ValueError("Your shopping cart is empty.")

    if not delivery_address or len(delivery_address.strip()) < 10:
        raise ValueError("Please enter a complete delivery address.")

    connection = get_db_connection()
    cursor = None

    try:
        connection.start_transaction()
        cursor = connection.cursor(dictionary=True)

        product_ids = sorted(int(pid) for pid in cart_data.keys())
        placeholders = ",".join(["%s"] * len(product_ids))

        cursor.execute(
            f"""
            SELECT id, name, price, stock_quantity
            FROM products
            WHERE id IN ({placeholders})
              AND is_active = TRUE
            ORDER BY id
            FOR UPDATE
            """,
            tuple(product_ids),
        )

        products = {p["id"]: p for p in cursor.fetchall()}

        if len(products) != len(product_ids):
            raise ValueError(
                "A product is unavailable. Refresh your cart."
            )

        items = []
        subtotal = Decimal("0.00")

        for product_id in product_ids:
            quantity = int(cart_data[str(product_id)])
            product = products[product_id]

            if quantity < 1:
                raise ValueError("Invalid product quantity.")

            if quantity > product["stock_quantity"]:
                raise ValueError(
                    f"Only {product['stock_quantity']} units of "
                    f"{product['name']} are available."
                )

            price = Decimal(str(product["price"]))
            line_total = (price * quantity).quantize(
                Decimal("0.01")
            )
            subtotal += line_total

            items.append(
                {
                    "id": product_id,
                    "name": product["name"],
                    "price": price,
                    "quantity": quantity,
                    "line_total": line_total,
                }
            )

        subtotal = subtotal.quantize(Decimal("0.01"))

        # Revalidate the coupon using the server-calculated subtotal.
        discount_amount = Decimal("0.00")
        applied_coupon = None

        if coupon_code:
            coupon_result = validate_coupon(
                coupon_code,
                subtotal,
            )

            discount_amount = Decimal(
                str(coupon_result["discount"])
            ).quantize(Decimal("0.01"))

            applied_coupon = coupon_result["code"]

            if discount_amount < Decimal("0.00"):
                raise ValueError("Invalid coupon discount.")

            if discount_amount > subtotal:
                raise ValueError("Coupon discount exceeds the subtotal.")

        delivery_fee = (
            Decimal("0.00")
            if subtotal >= FREE_DELIVERY_MINIMUM
            else DELIVERY_FEE
        )

        total = (
            subtotal - discount_amount + delivery_fee
        ).quantize(Decimal("0.01"))

        if total < Decimal("0.00"):
            raise ValueError("Invalid order total.")

        cursor.execute(
            """
            INSERT INTO orders (
                user_id,
                delivery_address,
                subtotal,
                delivery_fee,
                discount_amount,
                coupon_code,
                total_amount,
                order_status,
                payment_status
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s,
                'pending', 'pending'
            )
            """,
            (
                user_id,
                delivery_address.strip(),
                subtotal,
                delivery_fee,
                discount_amount,
                applied_coupon,
                total,
            ),
        )

        order_id = cursor.lastrowid

        for item in items:
            cursor.execute(
                """
                INSERT INTO order_items (
                    order_id,
                    product_id,
                    product_name,
                    unit_price,
                    quantity,
                    line_total
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    order_id,
                    item["id"],
                    item["name"],
                    item["price"],
                    item["quantity"],
                    item["line_total"],
                ),
            )

            cursor.execute(
                """
                UPDATE products
                SET stock_quantity = stock_quantity - %s
                WHERE id = %s
                  AND stock_quantity >= %s
                """,
                (
                    item["quantity"],
                    item["id"],
                    item["quantity"],
                ),
            )

            if cursor.rowcount != 1:
                raise ValueError(
                    f"Stock changed for {item['name']}. Please retry."
                )

        cursor.execute(
            """
            INSERT INTO payments (
                order_id,
                payment_method,
                amount,
                status
            )
            VALUES (%s, 'razorpay', %s, 'pending')
            """,
            (order_id, total),
        )

        # Keep the order pending until Razorpay payment is verified.
        connection.commit()

        return {
            "order_id": order_id,
            "subtotal": subtotal,
            "discount_amount": discount_amount,
            "coupon_code": applied_coupon,
            "delivery_fee": delivery_fee,
            "total": total,
            "amount_paise": int(total * 100),
        }

    except Exception:
        connection.rollback()
        raise

    finally:
        if cursor:
            cursor.close()
        connection.close()


def save_razorpay_order_id(order_id, user_id, razorpay_order_id):
    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            UPDATE payments p
            JOIN orders o ON o.id = p.order_id
            SET p.razorpay_order_id = %s
            WHERE o.id = %s
              AND o.user_id = %s
              AND p.payment_method = 'razorpay'
              AND p.status = 'pending'
              AND p.razorpay_order_id IS NULL
            """,
            (razorpay_order_id, order_id, user_id),
        )

        if cursor.rowcount != 1:
            raise ValueError(
                "Could not link the online payment to this order."
            )

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()


def mark_online_payment_paid(
    razorpay_order_id,
    razorpay_payment_id,
    user_id,
):
    connection = get_db_connection()
    cursor = None

    try:
        connection.start_transaction()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                p.order_id,
                p.status
            FROM payments p
            JOIN orders o ON o.id = p.order_id
            WHERE p.razorpay_order_id = %s
              AND o.user_id = %s
              AND p.payment_method = 'razorpay'
            FOR UPDATE
            """,
            (razorpay_order_id, user_id),
        )

        payment = cursor.fetchone()

        if not payment:
            raise ValueError("Online payment order not found.")

        if payment["status"] == "paid":
            connection.commit()
            return payment["order_id"]

        if payment["status"] != "pending":
            raise ValueError("This payment is no longer pending.")

        cursor.execute(
            """
            UPDATE payments
            SET transaction_id = %s,
                status = 'paid'
            WHERE razorpay_order_id = %s
              AND status = 'pending'
            """,
            (razorpay_payment_id, razorpay_order_id),
        )

        if cursor.rowcount != 1:
            raise ValueError("Payment status changed. Please retry.")

        cursor.execute(
            """
            UPDATE orders
            SET payment_status = 'paid',
                order_status = 'confirmed'
            WHERE id = %s
              AND user_id = %s
              AND payment_status = 'pending'
            """,
            (payment["order_id"], user_id),
        )

        if cursor.rowcount != 1:
            raise ValueError("Could not confirm the paid order.")

        cursor.execute(
            """
            INSERT INTO deliveries (order_id, delivery_status)
            VALUES (%s, 'waiting')
            """,
            (payment["order_id"],),
        )

        connection.commit()
        return payment["order_id"]

    except Exception:
        connection.rollback()
        raise

    finally:
        if cursor:
            cursor.close()
        connection.close()


def get_customer_orders(user_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT
                o.id AS order_id,
                o.subtotal,
                o.discount_amount,
                o.coupon_code,
                o.delivery_fee,
                o.total_amount,
                o.order_status,
                o.payment_status,
                o.created_at,
                d.delivery_status
            FROM orders AS o
            LEFT JOIN deliveries AS d ON d.order_id = o.id
            WHERE o.user_id = %s
            ORDER BY o.created_at DESC, o.id DESC
            """,
            (user_id,),
        )

        return cursor.fetchall()

    finally:
        cursor.close()
        connection.close()


def get_customer_order_details(order_id, user_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT
                o.id AS order_id,
                o.delivery_address,
                o.subtotal,
                o.discount_amount,
                o.coupon_code,
                o.delivery_fee,
                o.total_amount,
                o.order_status,
                o.payment_status,
                o.created_at,
                d.delivery_status,
                d.assigned_at,
                d.delivered_at,
                u.name AS worker_name,
                u.phone AS worker_phone
            FROM orders AS o
            LEFT JOIN deliveries AS d ON d.order_id = o.id
            LEFT JOIN users AS u ON u.id = d.worker_id
            WHERE o.id = %s AND o.user_id = %s
            LIMIT 1
            """,
            (order_id, user_id),
        )

        order = cursor.fetchone()

        if not order:
            return None

        cursor.execute(
            """
            SELECT product_name, unit_price, quantity, line_total
            FROM order_items
            WHERE order_id = %s
            ORDER BY id
            """,
            (order_id,),
        )

        order["items"] = cursor.fetchall()
        return order

    finally:
        cursor.close()
        connection.close()


def create_order(
    cart_data,
    delivery_address,
    payment_method,
    user_id=None,
    coupon_code=None,
     loyalty_points=0,
):
    """Create a Cash on Delivery order with transactional coupon handling."""

    if not cart_data:
        raise ValueError("Your shopping cart is empty.")

    if not delivery_address or len(delivery_address.strip()) < 10:
        raise ValueError("Please enter a complete delivery address.")

    if payment_method != "cash_on_delivery":
        raise ValueError(
            "Online payment is not enabled in this function. "
            "Please select Cash on Delivery."
        )

    connection = get_db_connection()
    cursor = None

    try:
        connection.start_transaction()
        cursor = connection.cursor(dictionary=True)

        # Lock product rows to prevent overselling.
        product_ids = sorted(int(pid) for pid in cart_data.keys())

        if not product_ids:
            raise ValueError("Your shopping cart is empty.")

        placeholders = ",".join(["%s"] * len(product_ids))

        cursor.execute(
            f"""
            SELECT id, name, price, stock_quantity
            FROM products
            WHERE id IN ({placeholders})
              AND is_active = TRUE
            ORDER BY id
            FOR UPDATE
            """,
            tuple(product_ids),
        )

        products = {
            row["id"]: row for row in cursor.fetchall()
        }

        if len(products) != len(product_ids):
            raise ValueError(
                "One or more products are unavailable. Refresh your cart."
            )

        order_items = []
        subtotal = Decimal("0.00")

        # Validate quantities and calculate the server-side subtotal.
        for product_id in product_ids:
            quantity = int(cart_data[str(product_id)])

            if quantity < 1:
                raise ValueError("Invalid product quantity.")

            product = products[product_id]

            if quantity > product["stock_quantity"]:
                raise ValueError(
                    f"Only {product['stock_quantity']} units of "
                    f"{product['name']} are available."
                )

            price = Decimal(str(product["price"])).quantize(
                Decimal("0.01")
            )
            line_total = (price * quantity).quantize(
                Decimal("0.01")
            )
            subtotal += line_total

            order_items.append(
                {
                    "id": product_id,
                    "name": product["name"],
                    "price": price,
                    "quantity": quantity,
                    "line_total": line_total,
                }
            )

        subtotal = subtotal.quantize(Decimal("0.01"))

        # Determine delivery fee.
        delivery_fee = (
            Decimal("0.00")
            if subtotal >= FREE_DELIVERY_MINIMUM
            else DELIVERY_FEE
        )

        # Apply and record the coupon inside this transaction.
        discount_amount = Decimal("0.00")
        applied_coupon = None

        if coupon_code:
            coupon_result = apply_coupon_in_transaction(
                connection,
                coupon_code,
                subtotal,
            )

            discount_amount = Decimal(
                str(coupon_result["discount"])
            ).quantize(Decimal("0.01"))

            applied_coupon = coupon_result["code"]

            if discount_amount < Decimal("0.00"):
                raise ValueError("Invalid coupon discount.")

            if discount_amount > subtotal:
                raise ValueError(
                    "Coupon discount exceeds the subtotal."
                )

        # Calculate the final amount.
        total = (
            subtotal - discount_amount + delivery_fee
        ).quantize(Decimal("0.01"))

        if total < Decimal("0.00"):
            raise ValueError("Invalid order total.")

        # Save the order and applied coupon.
        cursor.execute(
            """
            INSERT INTO orders (
                user_id,
                delivery_address,
                subtotal,
                delivery_fee,
                discount_amount,
                coupon_code,
                total_amount,
                order_status,
                payment_status
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s,
                'confirmed', 'pending'
            )
            """,
            (
                user_id,
                delivery_address.strip(),
                subtotal,
                delivery_fee,
                discount_amount,
                applied_coupon,
                total,
            ),
        )

        order_id = cursor.lastrowid

        # Insert order items and reduce inventory.
        for item in order_items:
            cursor.execute(
                """
                INSERT INTO order_items (
                    order_id,
                    product_id,
                    product_name,
                    unit_price,
                    quantity,
                    line_total
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    order_id,
                    item["id"],
                    item["name"],
                    item["price"],
                    item["quantity"],
                    item["line_total"],
                ),
            )

            cursor.execute(
                """
                UPDATE products
                SET stock_quantity = stock_quantity - %s
                WHERE id = %s
                  AND stock_quantity >= %s
                """,
                (
                    item["quantity"],
                    item["id"],
                    item["quantity"],
                ),
            )

            if cursor.rowcount != 1:
                raise ValueError(
                    f"Stock changed for {item['name']}. Please retry."
                )

        # Save payment information.
        cursor.execute(
            """
            INSERT INTO payments (
                order_id,
                payment_method,
                amount,
                status
            )
            VALUES (%s, %s, %s, 'pending')
            """,
            (order_id, payment_method, total),
        )

        # Create the delivery record.
        cursor.execute(
            """
            INSERT INTO deliveries (
                order_id,
                delivery_status
            )
            VALUES (%s, 'waiting')
            """,
            (order_id,),
        )

        # Commit only after all order operations succeed.
        connection.commit()

        return {
            "order_id": order_id,
            "subtotal": subtotal,
            "discount_amount": discount_amount,
            "coupon_code": applied_coupon,
            "delivery_fee": delivery_fee,
            "total": total,
        }

    except Exception:
        connection.rollback()
        raise

    finally:
        if cursor:
            cursor.close()
        connection.close()
