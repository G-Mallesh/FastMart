
from decimal import Decimal, ROUND_HALF_UP
from backend.db import get_db_connection


from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP


def apply_coupon_in_transaction(connection, code, subtotal):
    """
    Validate and count a coupon within the order's database transaction.
    If the order fails and rolls back, the usage increment rolls back too.
    """
    code = (code or "").strip().upper()
    subtotal = Decimal(str(subtotal)).quantize(Decimal("0.01"))

    if not code:
        raise ValueError("Enter a coupon code.")

    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT id, code, discount_type, discount_value,
                   minimum_order, max_discount, usage_limit,
                   used_count, expires_at, is_active
            FROM coupons
            WHERE code = %s
            FOR UPDATE
        """, (code,))

        coupon = cursor.fetchone()

        if not coupon or not coupon["is_active"]:
            raise ValueError("This coupon is invalid or inactive.")

        if (
            coupon["usage_limit"] is not None
            and coupon["used_count"] >= coupon["usage_limit"]
        ):
            raise ValueError("This coupon has reached its usage limit.")

        if (
            coupon["expires_at"] is not None
            and coupon["expires_at"] <= datetime.now()
        ):
            raise ValueError("This coupon has expired.")

        minimum = Decimal(str(coupon["minimum_order"]))
        if subtotal < minimum:
            raise ValueError(
                f"Your order must be at least ₹{minimum:.2f} "
                "for this coupon."
            )

        value = Decimal(str(coupon["discount_value"]))

        if coupon["discount_type"] == "percentage":
            discount = subtotal * value / Decimal("100")
        else:
            discount = value

        if coupon["max_discount"] is not None:
            discount = min(
                discount,
                Decimal(str(coupon["max_discount"]))
            )

        discount = min(discount, subtotal).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        )

        # This update must use the same connection as the order.
        # A transaction rollback will undo it.
        cursor.execute("""
            UPDATE coupons
            SET used_count = used_count + 1
            WHERE id = %s
        """, (coupon["id"],))

        return {
            "code": coupon["code"],
            "discount": discount,
        }

    finally:
        cursor.close()

def get_all_coupons():
    """Return coupons for the admin dashboard."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT id, code, discount_type, discount_value,
                   minimum_order, max_discount, usage_limit,
                   used_count, expires_at, is_active, created_at
            FROM coupons
            ORDER BY created_at DESC
        """)
        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()


def save_coupon(
    code,
    discount_type,
    discount_value,
    minimum_order=0,
    max_discount=None,
    usage_limit=None,
    expires_at=None
):
    """Create a coupon after validating its settings."""
    from decimal import Decimal, InvalidOperation

    code = (code or "").strip().upper()
    discount_type = (discount_type or "").strip().lower()

    if not code or len(code) > 40:
        raise ValueError("Enter a coupon code of 1–40 characters.")

    if not code.replace("_", "").replace("-", "").isalnum():
        raise ValueError("Use only letters, numbers, hyphens, or underscores.")

    if discount_type not in ("percentage", "fixed"):
        raise ValueError("Choose percentage or fixed discount.")

    try:
        value = Decimal(str(discount_value))
        minimum = Decimal(str(minimum_order or 0))
        maximum = (
            Decimal(str(max_discount))
            if max_discount not in (None, "")
            else None
        )
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("Enter valid numeric discount amounts.")

    if not value.is_finite() or value <= 0:
        raise ValueError("Discount value must be greater than zero.")

    if discount_type == "percentage" and value > 100:
        raise ValueError("Percentage discount cannot exceed 100%.")

    if not minimum.is_finite() or minimum < 0:
        raise ValueError("Minimum order must be zero or greater.")

    if maximum is not None and (
        not maximum.is_finite() or maximum <= 0
    ):
        raise ValueError("Maximum discount must be greater than zero.")

    if discount_type == "fixed" and maximum is not None:
        raise ValueError("Maximum discount is only needed for percentage coupons.")

    try:
        limit = int(usage_limit) if usage_limit not in (None, "") else None
    except (TypeError, ValueError):
        raise ValueError("Usage limit must be a whole number.")

    if limit is not None and limit < 1:
        raise ValueError("Usage limit must be at least 1.")

    # The HTML datetime-local input sends YYYY-MM-DDTHH:MM.
    if expires_at:
        from datetime import datetime

        try:
            expires_at = datetime.strptime(
                expires_at.strip(), "%Y-%m-%dT%H:%M"
            )
        except (ValueError, AttributeError):
            raise ValueError("Enter a valid coupon expiration date and time.")

        if expires_at <= datetime.now():
            raise ValueError("Expiration must be in the future.")

    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("""
            INSERT INTO coupons (
                code, discount_type, discount_value,
                minimum_order, max_discount, usage_limit,
                expires_at, is_active
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE)
        """, (
            code,
            discount_type,
            value,
            minimum,
            maximum,
            limit,
            expires_at
        ))
        connection.commit()
    except Exception as error:
        connection.rollback()
        if getattr(error, "errno", None) == 1062:
            raise ValueError("That coupon code already exists.")
        raise
    finally:
        cursor.close()
        connection.close()


def toggle_coupon(coupon_id, is_active):
    """Activate or deactivate an existing coupon."""
    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("""
            UPDATE coupons
            SET is_active = %s
            WHERE id = %s
        """, (bool(is_active), coupon_id))

        if cursor.rowcount == 0:
            connection.rollback()
            return False

        connection.commit()
        return True
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()

def validate_coupon(code, subtotal):
    code = (code or "").strip().upper()
    subtotal = Decimal(str(subtotal)).quantize(Decimal("0.01"))

    if not code:
        raise ValueError("Enter a coupon code.")

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT code, discount_type, discount_value,
                   minimum_order, max_discount, usage_limit,
                   used_count, expires_at, is_active
            FROM coupons
            WHERE code = %s
            LIMIT 1
        """, (code,))

        coupon = cursor.fetchone()

        if not coupon or not coupon["is_active"]:
            raise ValueError("This coupon is invalid or inactive.")

        if (
            coupon["usage_limit"] is not None
            and coupon["used_count"] >= coupon["usage_limit"]
        ):
            raise ValueError("This coupon has reached its usage limit.")

        if (
            coupon["expires_at"] is not None
            and coupon["expires_at"].timestamp()
                <= __import__("time").time()
        ):
            raise ValueError("This coupon has expired.")

        if subtotal < Decimal(str(coupon["minimum_order"])):
            minimum = Decimal(str(coupon["minimum_order"]))
            raise ValueError(
                f"Your order must be at least ₹{minimum:.2f} for this coupon."
            )

        value = Decimal(str(coupon["discount_value"]))

        if coupon["discount_type"] == "percentage":
            discount = subtotal * value / Decimal("100")
        else:
            discount = value

        if coupon["max_discount"] is not None:
            discount = min(
                discount, Decimal(str(coupon["max_discount"]))
            )

        discount = min(discount, subtotal).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        return {
            "code": coupon["code"],
            "discount": discount,
            "subtotal": subtotal,
        }

    finally:
        cursor.close()
        connection.close()
