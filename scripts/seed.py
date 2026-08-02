"""
Populates stores, batches, standing orders, claims, and standing order matches
for demo presentation with rich quantities, impact metrics, and category coverage.
"""
import os
import sys
import random
import pandas as pd
from datetime import datetime, timedelta, timezone
from sqlalchemy import text
from app.db import engine

# Ensure parent directory is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def run():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    full_path = os.path.join(base_dir, "output", "full_dataset")
    demo_path = os.path.join(base_dir, "output", "seed_demo_subset")

    if not os.path.exists(full_path):
        full_path = "/app/output/full_dataset"
    if not os.path.exists(demo_path):
        demo_path = "/app/output/seed_demo_subset"

    if os.path.exists(full_path) and os.path.exists(os.path.join(full_path, "stores.csv")):
        base_path = full_path
    else:
        base_path = demo_path

    print(f"Loading seed data from: {base_path}")

    stores_df = pd.read_csv(os.path.join(base_path, "stores.csv"))
    products_df = pd.read_csv(os.path.join(base_path, "products.csv"))
    batches_df = pd.read_csv(os.path.join(base_path, "batches.csv"))
    batches_df = batches_df.merge(products_df, on="sku_id", how="inner")
    ngo_df = pd.read_csv(os.path.join(base_path, "ngo_standing_orders.csv"))

    with engine.begin() as conn:
        print("Clearing existing batches, standing orders, claims, matches, and stores...")
        conn.execute(text("TRUNCATE TABLE claims CASCADE"))
        conn.execute(text("TRUNCATE TABLE standing_order_matches CASCADE"))
        conn.execute(text("TRUNCATE TABLE batches CASCADE"))
        conn.execute(text("TRUNCATE TABLE standing_orders CASCADE"))
        conn.execute(text("TRUNCATE TABLE stores CASCADE"))

        # 1. Stores
        store_map = {}
        for _, row in stores_df.iterrows():
            result = conn.execute(
                text(
                    """
                    INSERT INTO stores (name, address, location_lat, location_lng, created_at, updated_at)
                    VALUES (:name, :address, :lat, :lng, NOW(), NOW())
                    RETURNING id
                    """
                ),
                {
                    "name": row["store_name"],
                    "address": f"{row['city']}, {row['state']}, India",
                    "lat": float(row["latitude"]),
                    "lng": float(row["longitude"]),
                },
            )
            db_id = result.scalar()
            store_map[row["store_id"]] = db_id
            print(f"Created store: {row['store_name']} ({row['city']}) -> DB ID: {db_id}")

        # 2. NGO Standing Orders
        ngo_ids = []
        for _, row in ngo_df.iterrows():
            cats = str(row["category_priority"]).split("|")
            cat_filter = cats[0] if cats else "ALL"
            res = conn.execute(
                text(
                    """
                    INSERT INTO standing_orders 
                        (ngo_name, contact_email, contact_phone, category_filter, 
                         min_quantity, priority_window_hours, is_active, created_at, updated_at)
                    VALUES 
                        (:ngo_name, :contact_email, :contact_phone, :category_filter, 
                         :min_quantity, :priority_window_hours, :is_active, NOW(), NOW())
                    RETURNING id
                    """
                ),
                {
                    "ngo_name": row["ngo_name"],
                    "contact_email": f"contact@{str(row['ngo_name']).lower().replace(' ', '').replace('&','')}.org",
                    "contact_phone": "+919876543210",
                    "category_filter": cat_filter,
                    "min_quantity": int(row["min_quantity_kg"]),
                    "priority_window_hours": int(row["priority_time_window_hours"]),
                    "is_active": True if row["verified_status"] == "verified" else False,
                },
            )
            ngo_ids.append(res.scalar())
        print(f"Created {len(ngo_ids)} standing orders.")

        # 3. Batches
        now = datetime.now(timezone.utc)
        batch_ids = []
        
        # Take up to 120 representative batches across categories
        sample_batches = batches_df.sample(n=min(120, len(batches_df)), random_state=42)
        
        for idx, row in sample_batches.iterrows():
            csv_store_id = row["store_id"]
            if csv_store_id not in store_map:
                db_store_id = random.choice(list(store_map.values()))
            else:
                db_store_id = store_map[csv_store_id]

            days_offset = random.randint(1, 6)
            new_expiry = now + timedelta(days=days_offset)
            category = row["category"]
            qty = max(10, int(row["quantity_received"]))
            orig_price = float(row["current_price_inr"])
            discount_pct = random.choice([20.0, 30.0, 40.0, 50.0])
            curr_price = round(orig_price * (1.0 - discount_pct / 100.0), 2)
            cost_price = round(orig_price * 0.4, 2)

            res = conn.execute(
                text(
                    """
                    INSERT INTO batches
                        (store_id, sku, product_name, category, quantity,
                         cost_price, original_selling_price, current_price, discount_percentage,
                         expiration_date, status, created_at, updated_at)
                    VALUES
                        (:store_id, :sku, :product_name, :category, :qty,
                         :cost, :orig_price, :curr_price, :discount_pct,
                         :expiry, 'ACTIVE', NOW(), NOW())
                    RETURNING id
                    """
                ),
                {
                    "store_id": db_store_id,
                    "sku": row["sku_id"],
                    "product_name": row["product_name"],
                    "category": category,
                    "qty": qty,
                    "cost": cost_price,
                    "orig_price": orig_price,
                    "curr_price": curr_price,
                    "discount_pct": discount_pct,
                    "expiry": new_expiry.date(),
                },
            )
            batch_ids.append(res.scalar())

        print(f"Created {len(batch_ids)} active batches across categories.")

        # 4. Create Claims (Rescued & Completed items)
        statuses = ["FULFILLED", "PAID", "PAID", "PAID", "RESERVED", "EXPIRED"]
        claims_count = 0
        rescued_items_count = 0

        for i in range(50):
            b_id = random.choice(batch_ids)
            st = random.choice(statuses)
            qty = random.randint(4, 15)
            token = f"CLM-DEMO-{i+1:04d}"
            
            conn.execute(
                text(
                    """
                    INSERT INTO claims
                        (batch_id, claim_token, reserver_phone, reserver_email,
                         reserved_quantity, fulfillment_type, status, is_subsidized, created_at, updated_at)
                    VALUES
                        (:batch_id, :token, '+919876543210', 'consumer@optimart.app',
                         :qty, 'pickup', :status, FALSE, NOW(), NOW())
                    """
                ),
                {
                    "batch_id": b_id,
                    "token": token,
                    "qty": qty,
                    "status": st,
                },
            )
            claims_count += 1
            if st in ["PAID", "FULFILLED"]:
                rescued_items_count += qty

        print(f"Created {claims_count} claims ({rescued_items_count} items rescued).")

        # 5. Standing Order Matches
        matches_count = 0
        for i in range(12):
            b_id = random.choice(batch_ids)
            s_id = random.choice(ngo_ids)
            qty = random.randint(15, 35)
            conn.execute(
                text(
                    """
                    INSERT INTO standing_order_matches
                        (standing_order_id, batch_id, allocated_quantity, status, is_subsidized, allocated_at)
                    VALUES
                        (:s_id, :b_id, :qty, 'ALLOCATED', TRUE, NOW())
                    """
                ),
                {
                    "s_id": s_id,
                    "b_id": b_id,
                    "qty": qty,
                },
            )
            matches_count += 1

        print(f"Created {matches_count} standing order matches.")


if __name__ == "__main__":
    run()
