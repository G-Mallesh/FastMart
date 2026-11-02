
from backend.db import get_db_connection


def get_sales_analytics():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        # 1. Daily sales for the last 7 days
        cursor.execute("""
            SELECT
                DATE(created_at) AS sale_date,
                COUNT(*) AS order_count,
                COALESCE(SUM(total_amount), 0) AS sales
            FROM orders
            WHERE order_status != 'cancelled'
              AND created_at >= DATE_SUB(CURDATE(), INTERVAL 6 DAY)
            GROUP BY DATE(created_at)
            ORDER BY sale_date
        """)
        daily_sales = cursor.fetchall()

        # 2. Order summary
        cursor.execute("""
            SELECT
                COUNT(*) AS total_orders,
                COALESCE(SUM(
                    CASE
                        WHEN order_status != 'cancelled'
                        THEN total_amount
                        ELSE 0
                    END
                ), 0) AS total_sales,
                COALESCE(SUM(
                    CASE
                        WHEN order_status = 'delivered'
                        THEN 1
                        ELSE 0
                    END
                ), 0) AS delivered_orders,
                COALESCE(SUM(
                    CASE
                        WHEN order_status = 'cancelled'
                        THEN 1
                        ELSE 0
                    END
                ), 0) AS cancelled_orders
            FROM orders
        """)
        summary = cursor.fetchone()

        # 3. Top 5 best-selling products
        # line_total already contains quantity * unit_price
        cursor.execute("""
            SELECT
                p.id,
                p.name,
                COALESCE(SUM(oi.quantity), 0) AS units_sold,
                COALESCE(SUM(oi.line_total), 0) AS product_revenue
            FROM order_items oi
            JOIN products p ON p.id = oi.product_id
            JOIN orders o ON o.id = oi.order_id
            WHERE o.order_status != 'cancelled'
            GROUP BY p.id, p.name
            ORDER BY units_sold DESC, product_revenue DESC
            LIMIT 5
        """)
        best_sellers = cursor.fetchall()
        
        # 4. Delivery status statistics
        cursor.execute("""
            SELECT
                delivery_status,
                COUNT(*) AS delivery_count
            FROM deliveries
            GROUP BY delivery_status
            ORDER BY delivery_count DESC
        """)
        delivery_stats = cursor.fetchall()

       

        return {
            "daily_sales": daily_sales,
            "summary": summary,
            "best_sellers": best_sellers,
            "delivery_stats": delivery_stats,
        }

    finally:
        cursor.close()
        connection.close()
