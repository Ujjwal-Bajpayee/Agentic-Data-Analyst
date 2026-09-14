import sys
import argparse
from pathlib import Path
from datetime import datetime, timedelta
import random
from sqlalchemy import text, create_engine, URL

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.db.connection import build_engine


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS categories (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS products (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    category_id INT,
    price DECIMAL(10,2) NOT NULL,
    stock_quantity INT DEFAULT 100,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS customers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(150) NOT NULL,
    segment VARCHAR(50) DEFAULT 'Standard',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS orders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    customer_id INT,
    status VARCHAR(50) DEFAULT 'completed',
    discount_amount DECIMAL(10,2) DEFAULT 0.00,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS order_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_id INT NOT NULL,
    product_id INT NOT NULL,
    quantity INT NOT NULL,
    unit_price DECIMAL(10,2) NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS payments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_id INT NOT NULL,
    payment_method VARCHAR(50) NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
) ENGINE=InnoDB;
"""


def seed_database(engine) -> dict:
    with engine.begin() as conn:
        for stmt in SCHEMA_SQL.strip().split(";"):
            cleaned = stmt.strip()
            if cleaned:
                conn.execute(text(cleaned))

        conn.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
        conn.execute(text("TRUNCATE TABLE payments;"))
        conn.execute(text("TRUNCATE TABLE order_items;"))
        conn.execute(text("TRUNCATE TABLE orders;"))
        conn.execute(text("TRUNCATE TABLE products;"))
        conn.execute(text("TRUNCATE TABLE categories;"))
        conn.execute(text("TRUNCATE TABLE customers;"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))

        categories = ["Electronics", "Home & Kitchen", "Apparel", "Books", "Sports & Fitness"]
        for cat in categories:
            conn.execute(text("INSERT INTO categories (name) VALUES (:name)"), {"name": cat})

        products_data = [
            ("Pro Laptop 15-inch", 1, 1299.99, 50),
            ("Wireless Noise-Canceling Headphones", 1, 249.99, 120),
            ("Ultra-Wide Monitor 34-inch", 1, 599.99, 45),
            ("Mechanical Keyboard RGB", 1, 119.99, 150),
            ("Ergonomic Mouse", 1, 79.99, 200),
            ("Smartphone Flagship 256GB", 1, 899.99, 80),
            ("Smart Watch Series 5", 1, 329.99, 110),
            ("Espresso Machine Pro", 2, 499.99, 35),
            ("Cast Iron Skillet Set", 2, 89.99, 90),
            ("Robot Vacuum Cleaner", 2, 349.99, 60),
            ("Air Fryer XL 6-Quart", 2, 129.99, 85),
            ("Blender 1200W High-Speed", 2, 109.99, 70),
            ("Ceramic Knife Set", 2, 49.99, 130),
            ("Performance Running Shoes", 3, 139.99, 140),
            ("Waterproof Trail Jacket", 3, 179.99, 65),
            ("Classic Cotton Crewneck", 3, 34.99, 300),
            ("Slim-Fit Denim Jeans", 3, 69.99, 180),
            ("Merino Wool Sweater", 3, 89.99, 95),
            ("Data Engineering with Python", 4, 49.99, 150),
            ("Designing Data-Intensive Applications", 4, 54.99, 210),
            ("Cloud Architecture Blueprint", 4, 44.99, 120),
            ("Machine Learning Operations Handbook", 4, 59.99, 90),
            ("Business Analytics in Practice", 4, 39.99, 160),
            ("Adjustable Dumbbell Set 50lbs", 5, 299.99, 40),
            ("Yoga Mat Non-Slip 6mm", 5, 29.99, 250),
            ("Resistance Bands 5-Pack", 5, 19.99, 350),
            ("Cycling Indoor Smart Trainer", 5, 699.99, 25),
            ("Hydration Backpack 2L", 5, 45.99, 110),
        ]

        for p_name, cat_id, price, stock in products_data:
            conn.execute(
                text("INSERT INTO products (name, category_id, price, stock_quantity) VALUES (:name, :cat_id, :price, :stock)"),
                {"name": p_name, "cat_id": cat_id, "price": price, "stock": stock},
            )

        customer_names = [
            ("Apex Logistics", "Enterprise"),
            ("Beacon Health", "Enterprise"),
            ("Crestview Financial", "Enterprise"),
            ("Delta Retail Group", "Enterprise"),
            ("Echo Media Lab", "Mid-Market"),
            ("Frontier Systems", "Mid-Market"),
            ("Genesis Energy", "Mid-Market"),
            ("Horizon Tech", "Mid-Market"),
            ("Insight Analytics", "Mid-Market"),
            ("Jupiter Networks", "Mid-Market"),
            ("Krypton Design", "SMB"),
            ("Lighthouse Capital", "SMB"),
            ("Matrix Software", "SMB"),
            ("Nexus Biotech", "SMB"),
            ("Omni Consumer Goods", "SMB"),
            ("Pulse Digital", "SMB"),
            ("Quantum Labs", "SMB"),
            ("Radiant Solutions", "SMB"),
            ("Summit Partners", "SMB"),
            ("Titan Manufacturing", "SMB"),
            ("Unified Commerce", "Standard"),
            ("Vortex Labs", "Standard"),
            ("Waveform Audio", "Standard"),
            ("Xenon Global", "Standard"),
            ("Yield Metrics", "Standard"),
            ("Zenith Dynamics", "Standard"),
            ("Alpha Core", "Standard"),
            ("Beta Ventures", "Standard"),
            ("Gamma Industries", "Standard"),
            ("Delta Force Corp", "Standard"),
        ]

        now = datetime.now()
        for idx, (c_name, segment) in enumerate(customer_names):
            days_ago = random.randint(30, 365)
            created_dt = now - timedelta(days=days_ago)
            email = f"contact@{c_name.lower().replace(' ', '')}.com"
            conn.execute(
                text("INSERT INTO customers (name, email, segment, created_at) VALUES (:name, :email, :segment, :created_at)"),
                {"name": c_name, "email": email, "segment": segment, "created_at": created_dt},
            )

        statuses = ["completed", "completed", "completed", "completed", "pending", "refunded"]
        payment_methods = ["Credit Card", "Wire Transfer", "ACH", "PayPal", "Corporate Card"]

        order_count = 140
        for o_idx in range(1, order_count + 1):
            cust_id = random.randint(1, len(customer_names) - 3)
            status = random.choice(statuses)
            days_ago = random.randint(1, 180)
            order_dt = now - timedelta(days=days_ago, hours=random.randint(1, 23), minutes=random.randint(0, 59))
            updated_dt = order_dt + timedelta(days=random.randint(1, 4))
            discount = random.choice([0.00, 0.00, 15.00, 25.00, 50.00])

            conn.execute(
                text("INSERT INTO orders (customer_id, status, discount_amount, created_at, updated_at) VALUES (:cid, :status, :disc, :cat, :uat)"),
                {"cid": cust_id, "status": status, "disc": discount, "cat": order_dt, "uat": updated_dt},
            )

            order_id = o_idx
            num_items = random.randint(1, 4)
            chosen_products = random.sample(products_data, num_items)
            order_total = 0.0

            for p_name, _, p_price, _ in chosen_products:
                prod_id = products_data.index((p_name, _, p_price, _)) + 1
                qty = random.randint(1, 3)
                conn.execute(
                    text("INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES (:oid, :pid, :qty, :uprice)"),
                    {"oid": order_id, "pid": prod_id, "qty": qty, "uprice": p_price},
                )
                order_total += qty * p_price

            pmethod = random.choice(payment_methods)
            conn.execute(
                text("INSERT INTO payments (order_id, payment_method, amount, created_at) VALUES (:oid, :pm, :amt, :cat)"),
                {"oid": order_id, "pm": pmethod, "amt": max(0.0, order_total - discount), "cat": order_dt},
            )

    return {
        "categories": len(categories),
        "products": len(products_data),
        "customers": len(customer_names),
        "orders": order_count,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed demo database for Agentic Data Analyst")
    parser.add_argument("--host", default="localhost", help="MySQL host")
    parser.add_argument("--port", type=int, default=3306, help="MySQL port")
    parser.add_argument("--user", default="root", help="MySQL user")
    parser.add_argument("--password", default="", help="MySQL password")
    parser.add_argument("--database", required=True, help="MySQL database")
    args = parser.parse_args()

    db_url = URL.create(
        drivername="mysql+pymysql",
        username=args.user,
        password=args.password,
        host=args.host,
        port=args.port,
        database=args.database,
        query={"charset": "utf8mb4"},
    )
    engine = create_engine(db_url)
    stats = seed_database(engine)
    print(f"Database seeded successfully: {stats}")
