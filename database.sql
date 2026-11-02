
CREATE DATABASE IF NOT EXISTS fastmart;
USE fastmart;

-- 1. Customers, workers and admins
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    phone VARCHAR(20),
    address TEXT,
    role ENUM('customer', 'worker', 'admin')
        NOT NULL DEFAULT 'customer',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Product categories
CREATE TABLE IF NOT EXISTS categories (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE
);

-- 3. Products and inventory
CREATE TABLE IF NOT EXISTS products (
    id INT AUTO_INCREMENT PRIMARY KEY,
    category_id INT,
    name VARCHAR(150) NOT NULL,
    description TEXT,
    price DECIMAL(10,2) NOT NULL,
    stock_quantity INT NOT NULL DEFAULT 0,
    image_url VARCHAR(500),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (category_id) REFERENCES categories(id),
    CHECK (price >= 0),
    CHECK (stock_quantity >= 0)
);

-- 4. Shopping carts
CREATE TABLE IF NOT EXISTS carts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
        ON DELETE CASCADE
);

-- 5. Items in shopping carts
CREATE TABLE IF NOT EXISTS cart_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    cart_id INT NOT NULL,
    product_id INT NOT NULL,
    quantity INT NOT NULL DEFAULT 1,
    UNIQUE (cart_id, product_id),
    FOREIGN KEY (cart_id) REFERENCES carts(id)
        ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id),
    CHECK (quantity > 0)
);

-- 6. Customer orders
CREATE TABLE IF NOT EXISTS orders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    delivery_address TEXT NOT NULL,
    subtotal DECIMAL(10,2) NOT NULL,
    delivery_fee DECIMAL(10,2) NOT NULL DEFAULT 0,
    total_amount DECIMAL(10,2) NOT NULL,
    order_status ENUM(
        'pending', 'confirmed', 'packed',
        'out_for_delivery', 'delivered', 'cancelled'
    ) DEFAULT 'pending',
    payment_status ENUM(
        'pending', 'paid', 'failed', 'refunded'
    ) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- 7. Products recorded in each order
CREATE TABLE IF NOT EXISTS order_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_id INT NOT NULL,
    product_id INT,
    product_name VARCHAR(150) NOT NULL,
    unit_price DECIMAL(10,2) NOT NULL,
    quantity INT NOT NULL,
    line_total DECIMAL(10,2) NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(id),
    FOREIGN KEY (product_id) REFERENCES products(id)
        ON DELETE SET NULL,
    CHECK (quantity > 0)
);

-- 8. Payment records
CREATE TABLE IF NOT EXISTS payments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_id INT NOT NULL,
    payment_method ENUM(
        'cash_on_delivery', 'razorpay'
    ) NOT NULL,
    transaction_id VARCHAR(255),
    amount DECIMAL(10,2) NOT NULL,
    status ENUM(
        'pending', 'paid', 'failed', 'refunded'
    ) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES orders(id)
);

-- 9. Delivery assignments and tracking
CREATE TABLE IF NOT EXISTS deliveries (
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_id INT NOT NULL UNIQUE,
    worker_id INT NULL,
    delivery_status ENUM(
        'waiting', 'assigned', 'picked_up',
        'delivered', 'cancelled'
    ) DEFAULT 'waiting',
    assigned_at TIMESTAMP NULL,
    delivered_at TIMESTAMP NULL,
    FOREIGN KEY (order_id) REFERENCES orders(id),
    FOREIGN KEY (worker_id) REFERENCES users(id)
        ON DELETE SET NULL
);

-- 10. Sample categories
INSERT IGNORE INTO categories (name) VALUES
('Fruits'),
('Vegetables'),
('Dairy'),
('Snacks'),
('Beverages'),
('Household');

-- 11. Sample products
INSERT INTO products
(category_id, name, description, price, stock_quantity, image_url)
SELECT id, 'Fresh Apples', 'Fresh red apples', 120.00, 50, NULL
FROM categories WHERE name = 'Fruits'
AND NOT EXISTS (
    SELECT 1 FROM products WHERE name = 'Fresh Apples'
);

INSERT INTO products
(category_id, name, description, price, stock_quantity, image_url)
SELECT id, 'Tomatoes', 'Fresh farm tomatoes', 40.00, 100, NULL
FROM categories WHERE name = 'Vegetables'
AND NOT EXISTS (
    SELECT 1 FROM products WHERE name = 'Tomatoes'
);

INSERT INTO products
(category_id, name, description, price, stock_quantity, image_url)
SELECT id, 'Milk 1L', 'One litre milk packet', 60.00, 40, NULL
FROM categories WHERE name = 'Dairy'
AND NOT EXISTS (
    SELECT 1 FROM products WHERE name = 'Milk 1L'
);

INSERT INTO products
(category_id, name, description, price, stock_quantity, image_url)
SELECT id, 'Potato Chips', 'Crunchy potato chips packet', 20.00, 75, NULL
FROM categories WHERE name = 'Snacks'
AND NOT EXISTS (
    SELECT 1 FROM products WHERE name = 'Potato Chips'
);

-- 12. Verify the database
SHOW TABLES;

SELECT id, name, price, stock_quantity
FROM products;
