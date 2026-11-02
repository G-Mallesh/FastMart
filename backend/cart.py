
from backend.db import get_db_connection


def get_product(product_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT id, name, price, stock_quantity, image_url
            FROM products
            WHERE id = %s AND is_active = TRUE
        """, (product_id,))

        return cursor.fetchone()
    finally:
        cursor.close()
        connection.close()


def get_cart_details(cart_data):
    items = []
    subtotal = 0.0
    total_items = 0

    for product_id, quantity in cart_data.items():
        product = get_product(int(product_id))

        if not product:
            continue

        quantity = int(quantity)
        price = float(product["price"])
        line_total = round(price * quantity, 2)

        items.append({
            "id": product["id"],
            "name": product["name"],
            "price": price,
            "quantity": quantity,
            "stock": product["stock_quantity"],
            "image_url": product["image_url"],
            "line_total": line_total,
        })

        subtotal += line_total
        total_items += quantity

    return {
        "items": items,
        "subtotal": round(subtotal, 2),
        "total_items": total_items,
    }


def add_to_cart(cart_data, product_id, quantity=1):
    product = get_product(product_id)

    if not product:
        return False, "Product not found."

    if quantity < 1:
        return False, "Quantity must be at least 1."

    current_quantity = int(cart_data.get(str(product_id), 0))
    new_quantity = current_quantity + quantity

    if new_quantity > product["stock_quantity"]:
        return False, (
            f"Only {product['stock_quantity']} units "
            f"of {product['name']} are available."
        )

    cart_data[str(product_id)] = new_quantity
    return True, f"{product['name']} added to your cart."


def update_cart_quantity(cart_data, product_id, quantity):
    if quantity <= 0:
        cart_data.pop(str(product_id), None)
        return True, "Product removed from cart."

    product = get_product(product_id)

    if not product:
        cart_data.pop(str(product_id), None)
        return False, "Product is no longer available."

    if quantity > product["stock_quantity"]:
        return False, (
            f"Only {product['stock_quantity']} units "
            f"of {product['name']} are available."
        )

    cart_data[str(product_id)] = quantity
    return True, "Cart quantity updated."
