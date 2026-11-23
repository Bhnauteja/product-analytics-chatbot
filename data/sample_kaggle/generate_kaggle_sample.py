"""
Kaggle Superstore E-Commerce Sample Data Generator.
Generates a realistic Kaggle-style Superstore CSV dataset with standard e-commerce fields:
Order_ID, Order_Date, Ship_Date, Customer_ID, Customer_Name, Segment,
Country, City, State, Region, Category, Sub_Category, Sales, Quantity, Discount, Profit
"""

import os
import random
from datetime import datetime, timedelta
import pandas as pd

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
os.makedirs(OUTPUT_DIR, exist_ok=True)
CSV_PATH = os.path.join(OUTPUT_DIR, "superstore_kaggle_sample.csv")

SEGMENTS = ["Consumer", "Corporate", "Home Office"]
REGIONS = {
    "West": ["California", "Washington", "Oregon", "Nevada", "Arizona"],
    "East": ["New York", "Pennsylvania", "Ohio", "Massachusetts", "New Jersey"],
    "Central": ["Illinois", "Texas", "Michigan", "Indiana", "Wisconsin"],
    "South": ["Florida", "North Carolina", "Virginia", "Georgia", "Tennessee"]
}

CATEGORIES = {
    "Technology": ["Phones", "Accessories", "Machines", "Copiers"],
    "Furniture": ["Chairs", "Tables", "Bookcases", "Furnishings"],
    "Office Supplies": ["Binders", "Paper", "Storage", "Art", "Appliances", "Envelopes"]
}

CUSTOMER_NAMES = [
    "Claire Gute", "Brosina Hoffman", "Darrin Van Huff", "Sean O'Donnell",
    "Zuschuss Donatelli", "Eric Hoffmann", "Ruben Ausman", "Kunst Miller",
    "Andrew Allen", "Irene Maddox", "Harold Pawlan", "Pete Kriz",
    "Sandra Flanagan", "Hunter Lopez", "Subhash Patel", "Ken Black"
]

def generate_kaggle_superstore(num_records: int = 1500):
    start_date = datetime(2025, 1, 1)
    records = []

    for i in range(1, num_records + 1):
        order_date = start_date + timedelta(days=random.randint(0, 450))
        ship_date = order_date + timedelta(days=random.randint(1, 5))
        cust_name = random.choice(CUSTOMER_NAMES)
        cust_id = f"CG-{hash(cust_name) % 9000 + 1000}"
        segment = random.choice(SEGMENTS)
        
        region = random.choice(list(REGIONS.keys()))
        state = random.choice(REGIONS[region])
        city = f"{state} City"
        
        category = random.choice(list(CATEGORIES.keys()))
        sub_category = random.choice(CATEGORIES[category])
        
        quantity = random.randint(1, 10)
        base_unit_price = random.uniform(15.0, 500.0)
        discount = random.choice([0.0, 0.1, 0.2, 0.3, 0.5])
        sales = round(quantity * base_unit_price * (1 - discount), 2)
        profit_margin = random.uniform(-0.15, 0.45) if discount > 0.2 else random.uniform(0.10, 0.40)
        profit = round(sales * profit_margin, 2)

        records.append({
            "order_id": f"CA-2025-{100000 + i}",
            "order_date": order_date.strftime("%Y-%m-%d"),
            "ship_date": ship_date.strftime("%Y-%m-%d"),
            "customer_id": cust_id,
            "customer_name": cust_name,
            "segment": segment,
            "country": "United States",
            "city": city,
            "state": state,
            "region": region,
            "category": category,
            "sub_category": sub_category,
            "sales": sales,
            "quantity": quantity,
            "discount": discount,
            "profit": profit
        })

    df = pd.DataFrame(records)
    df.to_csv(CSV_PATH, index=False)
    print(f"Generated {len(df)} Kaggle Superstore rows at: {CSV_PATH}")

if __name__ == "__main__":
    generate_kaggle_superstore()
