"""
Synthetic Data Generator for Product Analytics Chatbot.
Generates realistic e-commerce / SaaS analytics dataset:
- users
- events (funnels: visit -> add_to_cart -> checkout_start -> purchase)
- orders
- products
- sessions

Saves directly into data/analytics.duckdb
"""

import os
import random
import uuid
from datetime import datetime, timedelta
import duckdb

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(DATA_DIR, "analytics.duckdb")

COUNTRIES = ["United States", "India", "United Kingdom", "Germany", "Canada", "Australia", "France", "Japan"]
COUNTRY_WEIGHTS = [0.35, 0.25, 0.12, 0.08, 0.07, 0.05, 0.05, 0.03]

DEVICES = ["Desktop", "Mobile iOS", "Mobile Android", "Tablet"]
DEVICE_WEIGHTS = [0.45, 0.30, 0.20, 0.05]

PLANS = ["Free", "Starter", "Pro", "Enterprise"]
PLAN_WEIGHTS = [0.60, 0.25, 0.12, 0.03]

CHANNELS = ["Organic Search", "Direct", "Paid Search", "Social Media", "Referral", "Email"]
CHANNEL_WEIGHTS = [0.30, 0.25, 0.20, 0.12, 0.08, 0.05]

PRODUCTS = [
    ("prod_001", "Enterprise Analytics Suite", "Software", 299.00),
    ("prod_002", "Team Collaboration Hub", "Software", 99.00),
    ("prod_003", "Data Pipeline Connector", "Integration", 149.00),
    ("prod_004", "Security & Compliance Shield", "Security", 199.00),
    ("prod_005", "Automated Reporting Pro", "Reporting", 49.00),
    ("prod_006", "Real-Time Alerting Bot", "DevOps", 79.00),
    ("prod_007", "Customer Insight Tracker", "Analytics", 129.00),
    ("prod_008", "AI Workflow Assistant", "AI", 199.00),
    ("prod_009", "Custom Dashboard Template", "Addon", 29.00),
    ("prod_010", "Priority Support SLA", "Services", 399.00)
]

def generate_dataset(num_users: int = 15000, days_history: int = 120):
    print(f"Generating synthetic dataset: {num_users} users over {days_history} days...")
    
    # End date: today
    now = datetime.now()
    start_date = now - timedelta(days=days_history)
    
    users = []
    events = []
    orders = []
    sessions = []
    
    user_ids = [f"usr_{uuid.uuid4().hex[:10]}" for _ in range(num_users)]
    
    # 1. Generate Users
    for uid in user_ids:
        signup_offset_days = random.randint(0, days_history - 1)
        signup_date = (start_date + timedelta(days=signup_offset_days)).date()
        country = random.choices(COUNTRIES, weights=COUNTRY_WEIGHTS)[0]
        device = random.choices(DEVICES, weights=DEVICE_WEIGHTS)[0]
        plan = random.choices(PLANS, weights=PLAN_WEIGHTS)[0]
        channel = random.choices(CHANNELS, weights=CHANNEL_WEIGHTS)[0]
        
        users.append({
            "user_id": uid,
            "signup_date": signup_date,
            "country": country,
            "device": device,
            "plan": plan,
            "acquisition_channel": channel
        })
    
    # 2. Generate Events, Sessions, and Orders with realistic funnels
    # Funnel steps: visit (100%) -> add_to_cart (35%) -> checkout_start (15%) -> purchase (8%)
    event_counter = 1
    session_counter = 1
    order_counter = 1
    
    for u in users:
        uid = u["user_id"]
        signup_dt = datetime.combine(u["signup_date"], datetime.min.time()) + timedelta(seconds=random.randint(0, 86399))
        
        # User activity frequency based on plan
        activity_multiplier = 1.0 if u["plan"] == "Free" else (2.0 if u["plan"] == "Starter" else 3.5)
        num_sessions = max(1, int(random.expovariate(1.0 / (3 * activity_multiplier))))
        
        current_sess_time = signup_dt
        for s in range(num_sessions):
            gap_days = random.randint(0, max(1, (now - current_sess_time).days if now > current_sess_time else 1))
            sess_time = current_sess_time + timedelta(days=gap_days, hours=random.randint(0, 12), minutes=random.randint(0, 59))
            if sess_time > now:
                break
            
            duration = random.randint(20, 1800)
            sess_id = f"sess_{session_counter:07d}"
            session_counter += 1
            
            sessions.append({
                "session_id": sess_id,
                "user_id": uid,
                "start_time": sess_time,
                "duration_seconds": duration,
                "device": u["device"]
            })
            
            # Step 1: visit
            events.append({
                "event_id": f"evt_{event_counter:08d}",
                "user_id": uid,
                "event_type": "visit",
                "event_timestamp": sess_time,
                "feature_name": "homepage",
                "platform": "web" if "Desktop" in u["device"] else ("ios" if "iOS" in u["device"] else "android")
            })
            event_counter += 1
            
            # Step 2: add_to_cart (35% probability)
            if random.random() < 0.35:
                cart_time = sess_time + timedelta(seconds=random.randint(30, 300))
                prod = random.choice(PRODUCTS)
                events.append({
                    "event_id": f"evt_{event_counter:08d}",
                    "user_id": uid,
                    "event_type": "add_to_cart",
                    "event_timestamp": cart_time,
                    "feature_name": prod[1],
                    "platform": "web" if "Desktop" in u["device"] else ("ios" if "iOS" in u["device"] else "android")
                })
                event_counter += 1
                
                # Step 3: checkout_start (45% of cart users)
                if random.random() < 0.45:
                    checkout_time = cart_time + timedelta(seconds=random.randint(20, 200))
                    events.append({
                        "event_id": f"evt_{event_counter:08d}",
                        "user_id": uid,
                        "event_type": "checkout_start",
                        "event_timestamp": checkout_time,
                        "feature_name": "checkout_page",
                        "platform": "web" if "Desktop" in u["device"] else ("ios" if "iOS" in u["device"] else "android")
                    })
                    event_counter += 1
                    
                    # Step 4: purchase (60% of checkout_start users)
                    if random.random() < 0.60:
                        purchase_time = checkout_time + timedelta(seconds=random.randint(15, 120))
                        events.append({
                            "event_id": f"evt_{event_counter:08d}",
                            "user_id": uid,
                            "event_type": "purchase",
                            "event_timestamp": purchase_time,
                            "feature_name": "order_confirmation",
                            "platform": "web" if "Desktop" in u["device"] else ("ios" if "iOS" in u["device"] else "android")
                        })
                        event_counter += 1
                        
                        # Generate Order
                        order_id = f"ord_{order_counter:07d}"
                        order_counter += 1
                        status = "completed" if random.random() < 0.94 else random.choice(["cancelled", "refunded"])
                        orders.append({
                            "order_id": order_id,
                            "user_id": uid,
                            "order_date": purchase_time,
                            "amount": prod[3],
                            "product_id": prod[0],
                            "status": status
                        })
            
            current_sess_time = sess_time
            
    print(f"Generated {len(users)} users, {len(events)} events, {len(orders)} orders, {len(sessions)} sessions.")
    
    # Save to DuckDB
    if os.path.exists(DB_PATH):
        try:
            os.remove(DB_PATH)
        except Exception:
            pass
            
    con = duckdb.connect(DB_PATH)
    
    # Create products table
    con.execute("""
        CREATE TABLE products (
            product_id VARCHAR PRIMARY KEY,
            name VARCHAR,
            category VARCHAR,
            price DOUBLE
        );
    """)
    con.executemany("INSERT INTO products VALUES (?, ?, ?, ?)", PRODUCTS)
    
    # Create users table
    con.execute("""
        CREATE TABLE users (
            user_id VARCHAR PRIMARY KEY,
            signup_date DATE,
            country VARCHAR,
            device VARCHAR,
            plan VARCHAR,
            acquisition_channel VARCHAR
        );
    """)
    con.executemany("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)", [
        (u["user_id"], u["signup_date"], u["country"], u["device"], u["plan"], u["acquisition_channel"])
        for u in users
    ])
    
    # Create events table
    con.execute("""
        CREATE TABLE events (
            event_id VARCHAR PRIMARY KEY,
            user_id VARCHAR,
            event_type VARCHAR,
            event_timestamp TIMESTAMP,
            feature_name VARCHAR,
            platform VARCHAR
        );
    """)
    con.executemany("INSERT INTO events VALUES (?, ?, ?, ?, ?, ?)", [
        (e["event_id"], e["user_id"], e["event_type"], e["event_timestamp"], e["feature_name"], e["platform"])
        for e in events
    ])
    
    # Create orders table
    con.execute("""
        CREATE TABLE orders (
            order_id VARCHAR PRIMARY KEY,
            user_id VARCHAR,
            order_date TIMESTAMP,
            amount DOUBLE,
            product_id VARCHAR,
            status VARCHAR
        );
    """)
    con.executemany("INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?)", [
        (o["order_id"], o["user_id"], o["order_date"], o["amount"], o["product_id"], o["status"])
        for o in orders
    ])
    
    # Create sessions table
    con.execute("""
        CREATE TABLE sessions (
            session_id VARCHAR PRIMARY KEY,
            user_id VARCHAR,
            start_time TIMESTAMP,
            duration_seconds INTEGER,
            device VARCHAR
        );
    """)
    con.executemany("INSERT INTO sessions VALUES (?, ?, ?, ?, ?)", [
        (s["session_id"], s["user_id"], s["start_time"], s["duration_seconds"], s["device"])
        for s in sessions
    ])
    
    # Verify counts
    print("\nDatabase created successfully at:", DB_PATH)
    for tbl in ["users", "events", "orders", "products", "sessions"]:
        count = con.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        print(f" - Table '{tbl}': {count:,} rows")
        
    con.close()

if __name__ == "__main__":
    generate_dataset()
