"""
ReturnShield Live Traffic Pool Generator
==========================================
Generates data/live_traffic_pool.csv with UI metadata but NO label column.
Records are used by the Locust load generator.

Usage:
    python ml/generate_synthetic_data.py [--size 1000] [--seed 42]
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import numpy as np
import pandas as pd
import uuid
from pathlib import Path
from shared.feature_schema import FEATURE_NAMES, PRODUCT_CATEGORY_MAP, RETURN_REASON_MAP

PRODUCT_NAMES = {
    1: ["Samsung Galaxy S24", "OnePlus 12", "Bluetooth Earbuds", "Laptop Dell XPS", "Smart Watch"],
    2: ["Cotton Kurti Set", "Slim Fit Jeans", "Ethnic Wear Saree", "Formal Shirt", "Sports T-Shirt"],
    3: ["Nike Running Shoes", "Adidas Sneakers", "Bata Formal Shoes", "Puma Sports Shoes", "Casual Loafers"],
    4: ["Air Purifier Philips", "Steel Almirah", "Wooden Bookshelf", "Kitchen Mixer", "Ceiling Fan"],
    5: ["Data Structures Book", "Indian History Vol 2", "UPSC Guide 2024", "Python Cookbook", "Business Analytics"],
}

CITIES = [
    "Mumbai", "Delhi", "Bengaluru", "Hyderabad", "Chennai",
    "Kolkata", "Pune", "Ahmedabad", "Jaipur", "Lucknow",
    "Surat", "Kochi", "Chandigarh", "Bhopal", "Nagpur",
]

FIRST_NAMES = ["Rahul", "Priya", "Amit", "Sunita", "Vikram", "Neha", "Suresh", "Kavita", "Arjun", "Deepa",
               "Ravi", "Meena", "Rohit", "Anita", "Sanjay", "Pooja", "Kiran", "Asha", "Manoj", "Rekha"]
LAST_NAMES = ["Sharma", "Patel", "Singh", "Kumar", "Verma", "Gupta", "Joshi", "Nair", "Reddy", "Rao",
              "Mehta", "Shah", "Malhotra", "Agarwal", "Tiwari", "Pandey", "Banerjee", "Das", "Iyer", "Pillai"]


def generate_pool(size: int = 1000, seed: int = 42) -> pd.DataFrame:
    rng = np.random.RandomState(seed)

    # Feature generation - realistic ranges from training data analysis
    account_age_days     = rng.randint(1, 1500, size)
    total_past_orders    = rng.randint(1, 80, size)
    historical_return_ratio = np.clip(rng.beta(2, 6, size), 0.02, 0.95).round(3)
    past_inr_claims      = rng.choice([0, 0, 0, 0, 1, 1, 2, 3, 5], size)
    item_price           = np.round(rng.uniform(299, 85000, size), 2)
    product_category_code = rng.randint(1, 6, size)  # 1-5
    return_reason_code   = rng.randint(1, 6, size)    # 1-5
    hours_since_delivery = np.round(rng.uniform(1, 240, size), 1)

    # weight_discrepancy_grams: ~20% null, rest low values (scan not always available)
    weight_disc = np.round(rng.uniform(0, 80, size), 1)
    null_mask = rng.random(size) < 0.20
    weight_disc_final = weight_disc.astype(object)
    weight_disc_final[null_mask] = None

    # shared_identity_links: mostly 0, some 1-3 (Redis computes at inference)
    shared_identity_links = rng.choice([0, 0, 0, 0, 0, 1, 1, 2, 3], size)
    is_cod_order    = rng.randint(0, 2, size)
    purchased_in_sale = rng.randint(0, 2, size)

    # UI metadata (never passed to model)
    request_ids = [f"REF-{rng.randint(10000, 99999)}" for _ in range(size)]
    customer_names = [
        f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"
        for _ in range(size)
    ]
    product_names = [
        rng.choice(PRODUCT_NAMES[cat])
        for cat in product_category_code
    ]
    cities = rng.choice(CITIES, size).tolist()

    df = pd.DataFrame({
        "request_id": request_ids,
        "customer_name": customer_names,
        "product_name": product_names,
        "city": cities,
        "account_age_days": account_age_days,
        "total_past_orders": total_past_orders,
        "historical_return_ratio": historical_return_ratio,
        "past_inr_claims": past_inr_claims,
        "item_price": item_price,
        "product_category_code": product_category_code,
        "return_reason_code": return_reason_code,
        "hours_since_delivery": hours_since_delivery,
        "weight_discrepancy_grams": weight_disc_final,
        "shared_identity_links": shared_identity_links,
        "is_cod_order": is_cod_order,
        "purchased_in_sale": purchased_in_sale,
    })
    # No label column - this is the live pool
    return df


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--size", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", default="data/live_traffic_pool.csv")
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Generating live traffic pool: size={args.size}, seed={args.seed}")
    df = generate_pool(args.size, args.seed)
    df.to_csv(output_path, index=False)
    print(f"Saved {len(df)} records to {output_path}")
    print(f"Columns: {list(df.columns)}")
    print(f"Note: No label column. shared_identity_links will be overridden by Redis at inference.")


if __name__ == "__main__":
    main()
