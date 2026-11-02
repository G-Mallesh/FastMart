
import os

from flask import (
    Flask, jsonify, render_template, session,
    request, redirect, url_for, flash
)
from dotenv import load_dotenv

from backend.db import test_db_connection
from backend.products import get_all_products
from backend.cart import (
    get_cart_details,
    add_to_cart,
    update_cart_quantity,
)
from backend.db import get_db_connection
from backend.orders import create_order

from backend.deliveries import (
    get_worker_deliveries,
    update_delivery,
)
from backend.auth import register_user, authenticate_user
from functools import wraps
from backend.orders import get_customer_orders, get_customer_order_details
from functools import wraps
from backend.admin import (
    get_admin_summary,
    get_admin_products,
    get_admin_orders,
    update_product_stock,
)
from backend.product_admin import (
    get_categories,
    save_product,
    set_product_active,
    get_product_for_admin,
)
from backend.admin import (
    get_available_workers,
    get_waiting_deliveries,
    assign_delivery,
)
import razorpay

from backend.orders import (
    create_online_order,
    save_razorpay_order_id,
    mark_online_payment_paid,
)
from backend.orders import cancel_failed_online_order
from backend.orders import get_order_tracking
from backend.admin import get_admin_report, mark_order_packed
from flask import render_template
import uuid
from PIL import Image, UnidentifiedImageError
from werkzeug.utils import secure_filename
from backend.products import get_all_products
from backend.reviews import (
    get_product_with_rating,
    get_product_reviews,
    add_product_review,
)
from backend.wishlist import (
    get_wishlist,
    add_to_wishlist as wishlist_add_product,
    remove_from_wishlist as wishlist_remove_product,
)
from backend.coupons import validate_coupon
from backend.coupons import (
    validate_coupon,
    get_all_coupons,
    save_coupon,
    toggle_coupon,
)

from decimal import Decimal, InvalidOperation
from backend.deliveries import (
    save_delivery_location,
    get_latest_delivery_location,
)
from backend.routing import get_driving_route
from backend.deliveries import get_latest_delivery_location
from backend.notifications import (
    create_notification,
    get_customer_notifications,
    mark_notification_read,
)
from backend.analytics import get_sales_analytics
from backend.recommendations import get_recommended_products
from decimal import Decimal, InvalidOperation
from flask import jsonify
from backend.products import search_products, autocomplete_products
from backend.cancellations import cancel_customer_order
from backend.support import (
    create_complaint,
    get_customer_complaints,
    get_all_complaints,
    update_complaint,
)
from backend.loyalty import (
    get_loyalty_balance,
    get_loyalty_history,
)
from backend.orders import get_customer_order_details
from backend.stock_alerts import (
    get_low_stock_products,
    update_stock_threshold,
)
from decimal import Decimal, InvalidOperation

from backend.restocking import (
    get_suppliers,
    get_restocking_data,
    add_supplier,
    create_restock_order,
    receive_restock_order,
)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, ".env"))



app = Flask(
    __name__,
    template_folder="../frontend/templates",
    static_folder="../frontend/static",
    static_url_path="/static",
)

app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
app.secret_key = os.getenv("SECRET_KEY")

if not app.secret_key or app.secret_key == "fast_mart":
    raise RuntimeError("Set a unique SECRET_KEY in your .env file.")


def current_cart():
    return dict(session.get("cart", {}))


from functools import wraps


def customer_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if (
            not session.get("user_id")
            or session.get("role") != "customer"
        ):
            flash("Please log in with your customer account.")
            return redirect(url_for("login"))

        return view(*args, **kwargs)

    return wrapped
@app.route("/coupon/apply", methods=["POST"])
def apply_coupon():
    cart_data = current_cart()

    if not cart_data:
        flash("Add products to your cart first.")
        return redirect(url_for("checkout"))

    cart = get_cart_details(cart_data)
    code = request.form.get("coupon_code", "").strip().upper()

    try:
        result = validate_coupon(code, cart["subtotal"])
        session["coupon_code"] = result["code"]
        flash(
            f"Coupon {result['code']} applied. "
            f"Discount: ₹{result['discount']:.2f}"
        )
    except ValueError as error:
        session.pop("coupon_code", None)
        flash(str(error))

    return redirect(url_for("checkout"))



@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")
    phone = request.form.get("phone", "").strip()
    address = request.form.get("address", "").strip()
    role = request.form.get("role", "customer")

    if password != confirm_password:
        flash("Passwords do not match.")
        return redirect(url_for("register"))

    try:
        register_user(name, email, password, phone, address, role)
        flash("Account created successfully. Please log in.")
        return redirect(url_for("login"))

    except ValueError as error:
        flash(str(error))
        return redirect(url_for("register"))

    except Exception:
        app.logger.exception("Registration failed")
        flash("Registration failed. Please try again.")
        return redirect(url_for("register"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")

    try:
        user = authenticate_user(email, password)

        if not user:
            flash("Invalid email or password.")
            return redirect(url_for("login"))

        # Clear any previous login session before setting a new one.
        session.clear()
        session["user_id"] = user["id"]
        session["name"] = user["name"]
        session["role"] = user["role"]

        flash("Welcome to FAST MART!")

        if user["role"] == "worker":
            return redirect(url_for("worker_dashboard"))
        if user["role"] == "admin":
           return redirect(url_for("admin_dashboard"))
        
        return redirect(url_for("home"))

    except Exception:
        app.logger.exception("Login failed")
        flash("Unable to log in right now. Please try again.")
        return redirect(url_for("login"))


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been logged out.")
    return redirect(url_for("home"))

@app.route("/my-orders/<int:order_id>")
@customer_required
def order_details(order_id):
    try:
        order = get_customer_order_details(
            order_id,
            int(session["user_id"])
        )

        if not order:
            return render_template("order_not_found.html"), 404

        return render_template(
            "order_details.html",
            order=order
        )

    except Exception:
        app.logger.exception("Could not load order details")
        flash("Unable to load order details.")
        return redirect(url_for("my_orders"))
@app.route("/my-orders/<int:order_id>/invoice")
@customer_required
def order_invoice(order_id):
    try:
        order_data = get_customer_order_details(
            order_id, int(session["user_id"])
        )

        if not order_data:
            return render_template("order_not_found.html"), 404

        # Support a helper that returns (order, items).
        if isinstance(order_data, tuple):
            order, items = order_data

        # Support a helper that returns {"order": ..., "items": ...}.
        elif (
            isinstance(order_data, dict)
            and "order" in order_data
            and "items" in order_data
        ):
            order = order_data["order"]
            items = order_data["items"]

        # Support a helper that returns the order dictionary
        # with its items stored inside it.
        else:
            order = order_data
            items = order.get("items", [])

        return render_template(
            "invoice.html",
            order=order,
            items=items
        )

    except Exception:
        app.logger.exception("Could not load invoice")
        flash("Unable to load invoice.")
        return redirect(url_for("my_orders"))


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/market")
def market():
    products = get_all_products()
    app.logger.info("Market loaded %s products", len(products))

    return render_template(
        "market.html",
        products=products
    )


@app.route("/api/health")
def health():
    connected, message = test_db_connection()
    return jsonify({
        "status": "ok" if connected else "error",
        "database": message
    }), 200 if connected else 503


@app.route("/api/products")
def products():
    try:
        product_list = get_all_products()

        for product in product_list:
            product["price"] = float(product["price"])

        return jsonify(product_list)
    except Exception:
        app.logger.exception("Could not retrieve products")
        return jsonify({"error": "Unable to retrieve products."}), 500


@app.route("/cart")
def view_cart():
    try:
        details = get_cart_details(current_cart())
        return render_template("cart.html", **details)
    except Exception:
        app.logger.exception("Could not load shopping cart")
        flash("Unable to load the cart. Check your database.")
        return render_template(
            "cart.html",
            items=[],
            subtotal=0,
            total_items=0,
        )


@app.route("/cart/add/<int:product_id>", methods=["POST"])
def cart_add(product_id):
    cart_data = current_cart()

    success, message = add_to_cart(cart_data, product_id)

    if success:
        session["cart"] = cart_data
        session.modified = True

    flash(message)
    return redirect(request.referrer or url_for("view_cart"))


@app.route("/cart/update/<int:product_id>", methods=["POST"])
def cart_update(product_id):
    try:
        quantity = int(request.form.get("quantity", "1"))
    except ValueError:
        flash("Please enter a valid quantity.")
        return redirect(url_for("view_cart"))

    cart_data = current_cart()
    success, message = update_cart_quantity(
        cart_data, product_id, quantity
    )

    if success:
        session["cart"] = cart_data
        session.modified = True

    flash(message)
    return redirect(url_for("view_cart"))


@app.route("/cart/remove/<int:product_id>", methods=["POST"])
def cart_remove(product_id):
    cart_data = current_cart()
    cart_data.pop(str(product_id), None)

    session["cart"] = cart_data
    session.modified = True

    flash("Product removed from your cart.")
    return redirect(url_for("view_cart"))

def worker_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id") or session.get("role") != "worker":
            flash("Please log in with a worker account.")
            return redirect(url_for("home"))
        return view(*args, **kwargs)
    return wrapped


@app.route("/worker")
@worker_required
def worker_dashboard():
    try:
        deliveries = get_worker_deliveries(
            int(session["user_id"])
        )
        return render_template(
            "worker.html",
            deliveries=deliveries
        )
    except Exception:
        app.logger.exception("Could not load worker dashboard")
        flash("Unable to load deliveries.")
        return redirect(url_for("home"))


@app.route("/worker/delivery/<int:delivery_id>/update", methods=["POST"])
@worker_required
def worker_update_delivery(delivery_id):
    action = request.form.get("action", "")

    try:
        update_delivery(
            delivery_id=delivery_id,
            worker_id=int(session["user_id"]),
            action=action,
        )
        flash("Delivery status updated successfully.")
    except ValueError as error:
        flash(str(error))
    except Exception:
        app.logger.exception("Delivery update failed")
        flash("Unable to update delivery. Please try again.")

    return redirect(url_for("worker_dashboard"))

@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    cart_data = current_cart()

    if not cart_data:
        flash("Your cart is empty. Add products first.")
        return redirect(url_for("home"))

    # Display checkout page
    if request.method == "GET":
        try:
            details = get_cart_details(cart_data)
            return render_template("checkout.html", **details)
        except Exception:
            app.logger.exception("Could not load checkout")
            flash("Could not load checkout. Please try again.")
            return redirect(url_for("view_cart"))

    # Read checkout form
    address = request.form.get("delivery_address", "").strip()
    payment_method = request.form.get("payment_method", "").strip()

    if len(address) < 10 or len(address) > 1000:
        flash("Enter a delivery address between 10 and 1000 characters.")
        return redirect(url_for("checkout"))

    # Read delivery coordinates
    latitude_raw = request.form.get("delivery_latitude", "").strip()
    longitude_raw = request.form.get("delivery_longitude", "").strip()

    delivery_latitude = None
    delivery_longitude = None

    # Both coordinates must be supplied together
    if bool(latitude_raw) != bool(longitude_raw):
        flash("Please select a valid delivery location.")
        return redirect(url_for("checkout"))

    # Validate coordinates when provided
    if latitude_raw and longitude_raw:
        try:
            delivery_latitude = float(latitude_raw)
            delivery_longitude = float(longitude_raw)

            if not (
                -90 <= delivery_latitude <= 90
                and -180 <= delivery_longitude <= 180
            ):
                raise ValueError("Coordinates out of range")

        except (ValueError, TypeError):
            flash(
                "Invalid delivery coordinates. "
                "Please select your location again."
            )
            return redirect(url_for("checkout"))

    # Create order
    try:
        result = create_order(
            cart_data=cart_data,
            delivery_address=address,
            payment_method=payment_method,
            user_id=session.get("user_id"),
            coupon_code=session.get("coupon_code"),
            delivery_latitude=delivery_latitude,
            delivery_longitude=delivery_longitude,
        )

        # Clear the cart and coupon after successful order creation
        session.pop("coupon_code", None)
        session["cart"] = {}
        session.modified = True

        return render_template("order_success.html", **result)

    except ValueError as error:
        flash(str(error))
        return redirect(url_for("checkout"))

    except Exception:
        app.logger.exception("Order creation failed")
        flash(
            "Order could not be placed. "
            "Please check your cart and try again."
        )
        return redirect(url_for("checkout"))
    



@app.route("/my-orders")
@customer_required
def my_orders():
    try:
        orders = get_customer_orders(int(session["user_id"]))
        return render_template("orders.html", orders=orders)
    except Exception:
        app.logger.exception("Could not load customer orders")
        flash("Unable to load your orders. Please try again.")
        return redirect(url_for("home"))




def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id") or session.get("role") != "admin":
            flash("Admin login is required.")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


@app.route("/admin")
@admin_required
def admin_dashboard():
    try:
        return render_template(
            "admin.html",
            summary=get_admin_summary(),
            products=get_admin_products(),
            orders=get_admin_orders(),
        )
    except Exception:
        app.logger.exception("Could not load admin dashboard")
        flash("Unable to load the admin dashboard.")
        return redirect(url_for("home"))
@app.route("/admin/products")
@admin_required
def admin_products_page():
    try:
        return render_template(
            "admin_products.html",
            products=get_admin_products(),
            categories=get_categories(),
        )
    except Exception:
        app.logger.exception("Could not load product management")
        flash("Unable to load product management.")
        return redirect(url_for("admin_dashboard"))


@app.route("/admin/product/new", methods=["GET", "POST"])
@admin_required
def admin_product_new():
    categories = get_categories()

    if request.method == "POST":
        try:
            category_raw = request.form.get("category_id", "").strip()
            category_id = int(category_raw) if category_raw else None

            stock_raw = request.form.get("stock_quantity", "").strip()

            if not stock_raw.isdigit():
                raise ValueError("Stock must be a whole number.")

            # Read the image URL entered in the form.
            image_url = request.form.get("image_url", "").strip()

            # If an image file was uploaded, save it.
            uploaded_image = request.files.get("image_file")

            if uploaded_image and uploaded_image.filename:
                image_url = save_uploaded_product_image(uploaded_image)

            # Save the product after preparing image_url.
            save_product(
                name=request.form.get("name", ""),
                category_id=category_id,
                description=request.form.get("description", ""),
                price=request.form.get("price", ""),
                stock_quantity=int(stock_raw),
                image_url=image_url,
            )

            flash("Product added successfully.")
            return redirect(url_for("admin_products_page"))

        except ValueError as error:
            flash(str(error))

        except Exception:
            app.logger.exception("Product creation failed")
            flash("Could not add the product.")

    return render_template(
        "product_form.html",
        product=None,
        categories=categories,
        page_title="Add Product",
    )
@app.route("/admin/product/<int:product_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_product_edit(product_id):
    product = get_product_for_admin(product_id)

    if not product:
        flash("Product not found.")
        return redirect(url_for("admin_products_page"))

    categories = get_categories()

    if request.method == "POST":
        try:
            category_raw = request.form.get("category_id", "").strip()
            category_id = int(category_raw) if category_raw else None

            stock_raw = request.form.get("stock_quantity", "").strip()

            if not stock_raw.isdigit():
                raise ValueError("Stock must be a whole number.")

            # Keep the existing image unless a replacement is provided.
            image_url = request.form.get("image_url", "").strip()

            uploaded_image = request.files.get("image_file")

            if uploaded_image and uploaded_image.filename:
                image_url = save_uploaded_product_image(uploaded_image)
            elif not image_url:
                # Reuse the image from the existing product.
                image_url = product["image_url"]

            save_product(
                product_id=product_id,
                name=request.form.get("name", ""),
                category_id=category_id,
                description=request.form.get("description", ""),
                price=request.form.get("price", ""),
                stock_quantity=int(stock_raw),
                image_url=image_url,
            )

            flash("Product updated successfully.")
            return redirect(url_for("admin_products_page"))

        except ValueError as error:
            flash(str(error))

        except Exception:
            app.logger.exception("Product update failed")
            flash("Could not update the product.")

        product = get_product_for_admin(product_id)

    return render_template(
        "product_form.html",
        product=product,
        categories=categories,
        page_title="Edit Product",
    )

@app.route("/admin/product/<int:product_id>/toggle", methods=["POST"])
@admin_required
def admin_product_toggle(product_id):
    raw_value = request.form.get("is_active", "")

    if raw_value not in ("0", "1"):
        flash("Invalid product status.")
        return redirect(url_for("admin_products_page"))

    try:
        set_product_active(product_id, raw_value == "1")
        flash("Product status updated.")
    except ValueError as error:
        flash(str(error))
    except Exception:
        app.logger.exception("Product status update failed")
        flash("Could not update product status.")

    return redirect(url_for("admin_products_page"))


@app.route("/admin/product/<int:product_id>/stock", methods=["POST"])
@admin_required
def admin_update_stock(product_id):
    try:
        raw_stock = request.form.get("stock_quantity", "").strip()

        if not raw_stock.isdigit():
            raise ValueError("Enter a valid whole-number stock quantity.")

        update_product_stock(product_id, int(raw_stock))
        flash("Product stock updated.")
    except ValueError as error:
        flash(str(error))
    except Exception:
        app.logger.exception("Stock update failed")
        flash("Could not update stock.")

    return redirect(url_for("admin_dashboard"))


@app.route("/admin/deliveries", methods=["GET", "POST"])
@admin_required
def admin_deliveries():
    if request.method == "POST":
        try:
            delivery_id = int(request.form.get("delivery_id", ""))
            worker_id = int(request.form.get("worker_id", ""))

            assign_delivery(delivery_id, worker_id)
            flash("Delivery assigned to worker successfully.")

        except ValueError as error:
            flash(str(error))
        except Exception:
            app.logger.exception("Delivery assignment failed")
            flash("Could not assign delivery.")

        return redirect(url_for("admin_deliveries"))

    try:
        return render_template(
            "admin_deliveries.html",
            deliveries=get_waiting_deliveries(),
            workers=get_available_workers(),
        )
    except Exception:
        app.logger.exception("Could not load delivery assignments")
        flash("Unable to load delivery assignments.")
        return redirect(url_for("admin_dashboard"))

@app.route("/payment/create", methods=["POST"])
def create_online_payment():
    if not session.get("user_id") or session.get("role") != "customer":
        flash("Please log in as a customer to pay online.")
        return redirect(url_for("login"))

    key_id = os.getenv("RAZORPAY_KEY_ID")
    key_secret = os.getenv("RAZORPAY_KEY_SECRET")

    if not key_id or not key_secret:
        flash("Razorpay test credentials are missing from .env.")
        return redirect(url_for("checkout"))

    address = request.form.get("delivery_address", "").strip()
    cart_data = current_cart()

    try:
        local_order = create_online_order(
            cart_data=cart_data,
            delivery_address=address,
            user_id=session["user_id"],
        )

        client = razorpay.Client(auth=(key_id, key_secret))
        gateway_order = client.order.create({
            "amount": local_order["amount_paise"],
            "currency": "INR",
            "receipt": f"fastmart_{local_order['order_id']}",
        })

        save_razorpay_order_id(
            local_order["order_id"],
            session["user_id"],
            gateway_order["id"],
        )

        return render_template(
            "payment.html",
            key_id=key_id,
            razorpay_order_id=gateway_order["id"],
            amount_paise=local_order["amount_paise"],
            order_id=local_order["order_id"],
            customer_name=session.get("name", ""),
        )

    except Exception as error:
        app.logger.exception("Online payment creation failed")
        flash(str(error) if isinstance(error, ValueError)
              else "Could not start online payment. Please try again.")
        return redirect(url_for("checkout"))

@app.route("/payment/verify", methods=["POST"])
def verify_online_payment():
    if not session.get("user_id") or session.get("role") != "customer":
        return jsonify({"success": False, "message": "Please log in again."}), 401

    data = request.get_json(silent=True) or {}
    razorpay_order_id = data.get("razorpay_order_id", "")
    razorpay_payment_id = data.get("razorpay_payment_id", "")
    razorpay_signature = data.get("razorpay_signature", "")

    if not all([razorpay_order_id, razorpay_payment_id, razorpay_signature]):
        return jsonify({"success": False, "message": "Missing payment details."}), 400

    key_id = os.getenv("RAZORPAY_KEY_ID")
    key_secret = os.getenv("RAZORPAY_KEY_SECRET")

    try:
        client = razorpay.Client(auth=(key_id, key_secret))

        # Verify the signature using the official SDK.
        client.utility.verify_payment_signature({
            "razorpay_order_id": razorpay_order_id,
            "razorpay_payment_id": razorpay_payment_id,
            "razorpay_signature": razorpay_signature,
        })

        order_id = mark_online_payment_paid(
            razorpay_order_id=razorpay_order_id,
            razorpay_payment_id=razorpay_payment_id,
            user_id=session["user_id"],
        )

        session["cart"] = {}

        return jsonify({
            "success": True,
            "redirect_url": url_for("my_orders"),
        })

    except Exception:
        app.logger.exception("Online payment verification failed")
        return jsonify({
            "success": False,
            "message": "Payment could not be verified. Check your order status before retrying.",
        }), 400

@app.route("/payment/cancel/<int:order_id>", methods=["POST"])
def cancel_online_payment(order_id):
    if not session.get("user_id") or session.get("role") != "customer":
        return jsonify({
            "success": False,
            "message": "Please log in again."
        }), 401

    key_id = os.getenv("RAZORPAY_KEY_ID")
    key_secret = os.getenv("RAZORPAY_KEY_SECRET")

    if not key_id or not key_secret:
        return jsonify({
            "success": False,
            "message": "Payment gateway configuration is missing."
        }), 500

    try:
        # Confirm the gateway's current payment attempts first.
        client = razorpay.Client(auth=(key_id, key_secret))

        connection = None
        cursor = None
        try:
            from backend.db import get_db_connection
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)

            cursor.execute(
                """
                SELECT p.razorpay_order_id
                FROM payments p
                JOIN orders o ON o.id = p.order_id
                WHERE o.id = %s AND o.user_id = %s
                  AND p.payment_method = 'razorpay'
                """,
                (order_id, session["user_id"]),
            )
            row = cursor.fetchone()
        finally:
            if cursor:
                cursor.close()
            if connection and connection.is_connected():
                connection.close()

        if not row or not row["razorpay_order_id"]:
            raise ValueError("Gateway order not found.")

        gateway_order_id = row["razorpay_order_id"]
        response = client.order.payments(gateway_order_id)
        attempts = response.get("items", [])

        # Never restore stock if any attempt could still succeed
        # or has already been paid.
        if not attempts or any(
            payment.get("status") != "failed"
            for payment in attempts
        ):
            return jsonify({
                "success": False,
                "message": (
                    "Payment is not confirmed as failed. "
                    "Check the order status before retrying."
                )
            }), 409

        cancel_failed_online_order(order_id, session["user_id"])

        return jsonify({
            "success": True,
            "message": "Failed order cancelled and stock restored."
        })

    except ValueError as error:
        return jsonify({
            "success": False,
            "message": str(error)
        }), 400
    except Exception:
        app.logger.exception("Online order cancellation failed")
        return jsonify({
            "success": False,
            "message": "Could not verify payment status. Please try again."
        }), 502

@app.route("/my-orders/<int:order_id>/tracking")
def track_order(order_id):
    if not session.get("user_id") or session.get("role") != "customer":
        flash("Please log in to track your orders.")
        return redirect(url_for("login"))

    order = get_order_tracking(order_id, session["user_id"])

    if not order:
        return render_template("order_not_found.html"), 404

    return render_template("tracking.html", order=order)


@app.route("/admin/reports")
def admin_reports():
    if not session.get("user_id") or session.get("role") != "admin":
        flash("Admin login required.")
        return redirect(url_for("login"))

    report = get_admin_report()
    return render_template("admin_reports.html", report=report)


def admin_coupon_access():
    return session.get("user_id") and session.get("role") == "admin"


@app.route("/admin/coupons")
def admin_coupons():
    if not admin_coupon_access():
        flash("Admin login is required.")
        return redirect(url_for("login"))

    coupons = get_all_coupons()
    return render_template("admin_coupons.html", coupons=coupons)


@app.route("/admin/coupon/new", methods=["POST"])
def admin_coupon_create():
    if not admin_coupon_access():
        flash("Admin login is required.")
        return redirect(url_for("login"))

    try:
        save_coupon(
            code=request.form.get("code", ""),
            discount_type=request.form.get("discount_type", ""),
            discount_value=request.form.get("discount_value", ""),
            minimum_order=request.form.get("minimum_order", "0"),
            max_discount=request.form.get("max_discount", ""),
            usage_limit=request.form.get("usage_limit", ""),
            expires_at=request.form.get("expires_at", ""),
        )
        flash("Coupon created successfully.")
    except ValueError as error:
        flash(str(error))
    except Exception:
        app.logger.exception("Could not create coupon")
        flash("Could not create the coupon. Check the server log.")

    return redirect(url_for("admin_coupons"))


@app.route("/admin/coupon/<int:coupon_id>/toggle", methods=["POST"])
def admin_coupon_toggle(coupon_id):
    if not admin_coupon_access():
        flash("Admin login is required.")
        return redirect(url_for("login"))

    active_value = request.form.get("is_active", "")
    if active_value not in ("0", "1"):
        flash("Invalid coupon status.")
        return redirect(url_for("admin_coupons"))

    try:
        updated = toggle_coupon(coupon_id, active_value == "1")
        flash("Coupon status updated." if updated else "Coupon not found.")
    except Exception:
        app.logger.exception("Could not update coupon status")
        flash("Could not update coupon status.")

    return redirect(url_for("admin_coupons"))

@app.route("/admin/order/<int:order_id>/pack", methods=["POST"])
def admin_pack_order(order_id):
    if not session.get("user_id") or session.get("role") != "admin":
        flash("Admin login required.")
        return redirect(url_for("login"))

    try:
        mark_order_packed(order_id)
        flash(f"Order #{order_id} marked as packed.")
    except ValueError as error:
        flash(str(error))
    except Exception:
        app.logger.exception("Admin could not update order status")
        flash("Unable to update the order. Please try again.")

    return redirect(url_for("admin_reports"))

def save_uploaded_product_image(image_file):
    """Validate and save an uploaded product image."""
    if not image_file or not image_file.filename:
        return None

    original_name = secure_filename(image_file.filename)
    if not original_name or "." not in original_name:
        raise ValueError("Please select a valid image file.")

    extension = original_name.rsplit(".", 1)[1].lower()

    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError("Use JPG, JPEG, PNG, or WebP images only.")

    try:
        image_file.stream.seek(0)
        with Image.open(image_file.stream) as image:
            image.verify()
    except (UnidentifiedImageError, OSError, ValueError):
        raise ValueError("The uploaded file is not a valid image.")

    image_file.stream.seek(0)

    upload_folder = os.path.join(
        app.static_folder, "uploads", "products"
    )
    os.makedirs(upload_folder, exist_ok=True)

    filename = f"{uuid.uuid4().hex}.{extension}"
    destination = os.path.join(upload_folder, filename)

    image_file.save(destination)

    # This relative path works with url_for('static', filename=...).
    return f"uploads/products/{filename}"

@app.route("/product/<int:product_id>")
def product_detail(product_id):
    product = get_product_with_rating(product_id)

    if not product:
        return render_template("order_not_found.html"), 404

    reviews = get_product_reviews(product_id)

    return render_template(
        "product_detail.html",
        product=product,
        reviews=reviews,
    )
    

@app.route("/product/<int:product_id>/review", methods=["POST"])
def submit_product_review(product_id):
    if (
        not session.get("user_id")
        or session.get("role") != "customer"
    ):
        flash("Please log in as a customer to leave a review.")
        return redirect(url_for("login"))

    try:
        rating = int(request.form.get("rating", "0"))
        comment = request.form.get("comment", "")

        add_product_review(
            product_id=product_id,
            user_id=session["user_id"],
            rating=rating,
            comment=comment,
        )

        flash("Thank you! Your review has been published.")

    except ValueError as error:
        flash(str(error))
    except Exception:
        app.logger.exception("Unable to save product review")
        flash("Could not save your review. Please try again.")

    return redirect(url_for("product_detail", product_id=product_id))

def wishlist_customer_required():
    return (
        session.get("user_id")
        and session.get("role") == "customer"
    )


@app.route("/wishlist")
def wishlist_page():
    if not wishlist_customer_required():
        flash("Please log in as a customer to view your wishlist.")
        return redirect(url_for("login"))

    products = get_wishlist(session["user_id"])
    return render_template("wishlist.html", products=products)


@app.route("/wishlist/add/<int:product_id>", methods=["POST"])
def wishlist_add_route(product_id):
    if not wishlist_customer_required():
        flash("Please log in as a customer first.")
        return redirect(url_for("login"))

    try:
        wishlist_add_product(session["user_id"], product_id)
        flash("Product saved to your wishlist.")
    except ValueError as error:
        flash(str(error))
    except Exception:
        app.logger.exception("Could not save wishlist product")
        flash("Could not save this product. Please try again.")

    return redirect(request.referrer or url_for("market"))


@app.route("/wishlist/remove/<int:product_id>", methods=["POST"])
def wishlist_remove_route(product_id):
    if not wishlist_customer_required():
        flash("Please log in as a customer first.")
        return redirect(url_for("login"))

    try:
        wishlist_remove_product(session["user_id"], product_id)
        flash("Product removed from your wishlist.")
    except Exception:
        app.logger.exception("Could not remove wishlist product")
        flash("Could not remove this product. Please try again.")

    return redirect(url_for("wishlist_page"))


@app.route("/wishlist/<int:product_id>/add-to-cart", methods=["POST"])
def wishlist_add_to_cart(product_id):
    if not wishlist_customer_required():
        flash("Please log in as a customer first.")
        return redirect(url_for("login"))

    cart_data = current_cart()
    success, message = add_to_cart(cart_data, product_id, 1)
    flash(message)

    if success:
        session["cart"] = cart_data
        session.modified = True

    return redirect(url_for("wishlist_page"))




@app.route("/coupon/remove", methods=["POST"])
def remove_coupon():
    session.pop("coupon_code", None)
    flash("Coupon removed.")
    return redirect(url_for("checkout"))

@app.route("/worker/delivery/<int:delivery_id>/location", methods=["POST"])
def worker_update_location(delivery_id):
    if not session.get("user_id") or session.get("role") != "worker":
        return jsonify({"error": "Worker login required."}), 403

    data = request.get_json(silent=True) or {}

    try:
        latitude = Decimal(str(data.get("latitude", "")))
        longitude = Decimal(str(data.get("longitude", "")))

        if not latitude.is_finite() or not longitude.is_finite():
            raise ValueError("Invalid coordinates.")

        if not (Decimal("-90") <= latitude <= Decimal("90")):
            raise ValueError("Latitude is out of range.")

        if not (Decimal("-180") <= longitude <= Decimal("180")):
            raise ValueError("Longitude is out of range.")

        save_delivery_location(
            delivery_id,
            session["user_id"],
            latitude,
            longitude,
        )

        return jsonify({"message": "Location updated."}), 200

    except (InvalidOperation, TypeError, ValueError) as error:
        return jsonify({"error": str(error)}), 400
    except Exception:
        app.logger.exception("Unable to update delivery location")
        return jsonify({"error": "Unable to save location."}), 500


@app.route("/my-orders/<int:order_id>/location", methods=["GET"])
def customer_delivery_location(order_id):
    if not session.get("user_id") or session.get("role") != "customer":
        return jsonify({"error": "Customer login required."}), 403

    try:
        location = get_latest_delivery_location(
            order_id,
            session["user_id"],
        )

        if not location:
            return jsonify({
                "message": "No delivery location has been shared yet."
            }), 404

        return jsonify({
            "latitude": float(location["latitude"]),
            "longitude": float(location["longitude"]),
            "recorded_at": location["recorded_at"].isoformat()
                if location["recorded_at"] else None,
            "delivery_status": location["delivery_status"],
        })

    except Exception:
        app.logger.exception("Unable to retrieve delivery location")
        return jsonify({"error": "Unable to retrieve location."}), 500

def get_order_destination(order_id):
    """Return the delivery address for an order."""
    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT delivery_address
            FROM orders
            WHERE order_id = %s
            """,
            (order_id,)
        )

        order = cursor.fetchone()

        if not order:
            return None

        return order.get("delivery_address")

    except Exception:
        app.logger.exception(
            "Could not retrieve destination for order %s",
            order_id
        )
        return None

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route("/my-orders/<int:order_id>/route")
def customer_delivery_route(order_id):
    if not session.get("user_id") or session.get("role") != "customer":
        return jsonify({"error": "Customer login required."}), 403

    try:
        destination = get_order_destination(
            order_id, session["user_id"]
        )

        if (
            not destination
            or destination["delivery_latitude"] is None
            or destination["delivery_longitude"] is None
        ):
            return jsonify({"error": "Delivery destination is unavailable."}), 404

        worker = get_latest_delivery_location(
            order_id, session["user_id"]
        )

        if not worker:
            return jsonify({"error": "Worker location is not available yet."}), 404

        route = get_driving_route(
            worker["latitude"],
            worker["longitude"],
            destination["delivery_latitude"],
            destination["delivery_longitude"],
        )

        return jsonify({
            "distance_meters": route["distance_meters"],
            "duration_seconds": route["duration_seconds"],
            "route_points": route["route_points"],
        })

    except Exception:
        app.logger.exception("Route calculation failed")
        return jsonify({"error": "Unable to calculate the delivery route."}), 502


@app.route("/my-notifications")
def my_notifications():
    if not session.get("user_id") or session.get("role") != "customer":
        flash("Please log in as a customer.")
        return redirect(url_for("login"))

    notifications = get_customer_notifications(session["user_id"])

    return render_template(
        "notifications.html",
        notifications=notifications,
    )


@app.route("/my-notifications/<int:notification_id>/read", methods=["POST"])
def notification_read(notification_id):
    if not session.get("user_id") or session.get("role") != "customer":
        flash("Please log in as a customer.")
        return redirect(url_for("login"))

    mark_notification_read(notification_id, session["user_id"])
    return redirect(url_for("my_notifications"))

@app.route("/admin/analytics")
def admin_analytics():
    if not session.get("user_id") or session.get("role") != "admin":
        flash("Admin login required.")
        return redirect(url_for("login"))

    analytics = get_sales_analytics()

    return render_template(
        "admin_analytics.html",
        analytics=analytics,
    )

@app.route("/recommendations")
def recommendations():
    if not session.get("user_id") or session.get("role") != "customer":
        flash("Log in as a customer to view recommendations.")
        return redirect(url_for("login"))

    products = get_recommended_products(session["user_id"])

    return render_template(
        "recommendations.html",
        products=products,
    )


@app.route("/api/search-suggestions")
def search_suggestions():
    keyword = request.args.get("q", "").strip()

    if len(keyword) < 2:
        return jsonify([])

    products = autocomplete_products(keyword)

    # Return only the fields needed by the browser.
    return jsonify([
        {
            "id": p["id"],
            "name": p["name"],
            "price": float(p["price"]),
        }
        for p in products
    ])


@app.route("/search")
def product_search():
    keyword = request.args.get("q", "").strip()
    category_id = request.args.get("category_id", "").strip()
    min_price = request.args.get("min_price", "").strip()
    max_price = request.args.get("max_price", "").strip()

    try:
        category_id = int(category_id) if category_id else None
        if category_id is not None and category_id < 1:
            raise ValueError
    except ValueError:
        flash("Invalid category.")
        return redirect(url_for("market"))

    try:
        min_value = Decimal(min_price) if min_price else None
        max_value = Decimal(max_price) if max_price else None

        for value in (min_value, max_value):
            if value is not None and (
                not value.is_finite() or value < 0 or value > Decimal("99999999")
            ):
                raise ValueError

        if (min_value is not None and max_value is not None
                and min_value > max_value):
            raise ValueError

    except (InvalidOperation, ValueError):
        flash("Enter a valid price range.")
        return redirect(url_for("market"))

    products = search_products(
        keyword=keyword,
        category_id=category_id,
        min_price=min_value,
        max_price=max_value,
    )

    # Use the category-loading function already present in your project.
    from backend.product_admin import get_categories
    categories = get_categories()

    return render_template(
        "market.html",
        products=products,
        categories=categories,
        search_query=keyword,
        selected_category=category_id,
        min_price=min_price,
        max_price=max_price,
    )

@app.route(
    "/my-orders/<int:order_id>/cancel",
    methods=["POST"]
)
def cancel_order(order_id):
    if (
        not session.get("user_id")
        or session.get("role") != "customer"
    ):
        flash("Please log in as a customer.")
        return redirect(url_for("login"))

    try:
        success, message = cancel_customer_order(
            order_id,
            session["user_id"],
        )
        flash(message)
    except Exception:
        app.logger.exception("Order cancellation failed")
        flash("Cancellation failed. Please try again.")

    return redirect(
        url_for("order_details", order_id=order_id)
    )

@app.route("/support", methods=["GET", "POST"])
def customer_support():
    if (
        not session.get("user_id")
        or session.get("role") != "customer"
    ):
        flash("Please log in as a customer.")
        return redirect(url_for("login"))

    if request.method == "POST":
        success, message = create_complaint(
            user_id=session["user_id"],
            order_id=request.form.get("order_id") or None,
            subject=request.form.get("subject", ""),
            category=request.form.get("category", "other"),
            description=request.form.get("description", ""),
        )
        flash(message)

        if success:
            return redirect(url_for("customer_support"))

    complaints = get_customer_complaints(session["user_id"])

    return render_template(
        "support.html",
        complaints=complaints,
    )


@app.route("/admin/complaints")
def admin_complaints():
    if (
        not session.get("user_id")
        or session.get("role") != "admin"
    ):
        flash("Admin login required.")
        return redirect(url_for("login"))

    complaints = get_all_complaints()

    return render_template(
        "admin_complaints.html",
        complaints=complaints,
    )


@app.route(
    "/admin/complaint/<int:complaint_id>/update",
    methods=["POST"]
)
def admin_update_complaint(complaint_id):
    if (
        not session.get("user_id")
        or session.get("role") != "admin"
    ):
        flash("Admin login required.")
        return redirect(url_for("login"))

    success, message = update_complaint(
        complaint_id=complaint_id,
        status=request.form.get("status", ""),
        response=request.form.get("admin_response", ""),
    )
    flash(message)

    return redirect(url_for("admin_complaints"))

@app.route("/rewards")
def customer_rewards():
    if (
        not session.get("user_id")
        or session.get("role") != "customer"
):
        flash("Please log in as a customer.")
        return redirect(url_for("login"))

    user_id = session["user_id"]

    return render_template(
        "rewards.html",
        points_balance=get_loyalty_balance(user_id),
        transactions=get_loyalty_history(user_id),
    )

@app.route("/admin/low-stock")
def admin_low_stock():
    if (
        not session.get("user_id")
        or session.get("role") != "admin"
    ):
        flash("Admin login required.")
        return redirect(url_for("login"))

    products = get_low_stock_products()

    return render_template(
        "admin_low_stock.html",
        products=products,
    )


@app.route("/admin/product/<int:product_id>/stock-threshold",
           methods=["POST"])
def admin_update_stock_threshold(product_id):
    if (
        not session.get("user_id")
        or session.get("role") != "admin"
    ):
        flash("Admin login required.")
        return redirect(url_for("login"))

    try:
        threshold = int(request.form.get("threshold", ""))

        if threshold < 0:
            raise ValueError("Threshold cannot be negative.")

        update_stock_threshold(product_id, threshold)
        flash("Low-stock threshold updated.")

    except ValueError as error:
        flash(str(error) or "Enter a valid threshold.")

    return redirect(url_for("admin_low_stock"))


@app.route("/admin/restocking")
def admin_restocking():
    if (
        not session.get("user_id")
        or session.get("role") != "admin"
    ):
        flash("Admin login required.")
        return redirect(url_for("login"))

    products, orders = get_restocking_data()

    return render_template(
        "admin_restocking.html",
        suppliers=get_suppliers(),
        products=products,
        orders=orders,
    )


@app.route("/admin/supplier/add", methods=["POST"])
def admin_add_supplier():
    if (
        not session.get("user_id")
        or session.get("role") != "admin"
    ):
        flash("Admin login required.")
        return redirect(url_for("login"))

    try:
        add_supplier(
            request.form.get("supplier_name", ""),
            request.form.get("phone", ""),
            request.form.get("email", ""),
            request.form.get("address", ""),
        )
        flash("Supplier added successfully.")
    except ValueError as error:
        flash(str(error))

    return redirect(url_for("admin_restocking"))


@app.route("/admin/restocking/create", methods=["POST"])
def admin_create_restock():
    if (
        not session.get("user_id")
        or session.get("role") != "admin"
    ):
        flash("Admin login required.")
        return redirect(url_for("login"))

    try:
        supplier_id = int(request.form["supplier_id"])
        product_id = int(request.form["product_id"])
        quantity = int(request.form["quantity"])
        unit_cost = Decimal(request.form["unit_cost"])

        if not unit_cost.is_finite():
            raise ValueError("Enter a valid unit cost.")

        if unit_cost.as_tuple().exponent < -2:
            raise ValueError("Unit cost can have at most two decimals.")

        if unit_cost < 0 or unit_cost > Decimal("99999999.99"):
            raise ValueError("Unit cost is outside the allowed range.")

        create_restock_order(
            supplier_id=supplier_id,
            product_id=product_id,
            quantity=quantity,
            unit_cost=unit_cost,
            reference_number=request.form.get("reference_number", ""),
            admin_id=session["user_id"],
        )
        flash("Restocking order created. Stock has not changed yet.")

    except (ValueError, InvalidOperation, KeyError):
        flash("Check the supplier, product, quantity and unit cost.")

    return redirect(url_for("admin_restocking"))


@app.route(
    "/admin/restocking/<int:restock_id>/receive",
    methods=["POST"]
)
def admin_receive_restock(restock_id):
    if (
        not session.get("user_id")
        or session.get("role") != "admin"
    ):
        flash("Admin login required.")
        return redirect(url_for("login"))

    try:
        receive_restock_order(restock_id)
        flash("Stock received and inventory updated.")
    except ValueError as error:
        flash(str(error))

    return redirect(url_for("admin_restocking"))

if __name__ == "__main__":
    app.run(debug=True)
