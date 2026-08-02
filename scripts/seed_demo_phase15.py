"""
seed_demo_phase15.py — Phase 15 demo data seeder
==================================================
1. Inserts 6 demo batches (one per display category) for Store 1 with opening
   qty=30, dated 2026-07-27. Uses ON CONFLICT DO NOTHING — safe to re-run.
2. Extends sales_history from 2026-08-01 to today for every existing
   (store_id, sku) pair, using the same seasonality formula as
   generate_sales_history.py. Uses ON CONFLICT DO UPDATE — idempotent.

Constraints:
  - Does NOT modify any Phase 1-13 model/service code.
  - Does NOT wipe existing data.
  - Follows the same patterns as generate_sales_history.py.
"""
import os
import sys
import math
import random
from datetime import date, timedelta

import numpy as np
from sqlalchemy import text

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db import engine

# ---------------------------------------------------------------------------
# Mapping from display category → representative SKU at Store 1.
# These SKUs are confirmed to exist in sales_history (≥112 days of data).
# ---------------------------------------------------------------------------
DEMO_CATEGORY_SKUS = {
    "Dairy":          {"sku": "SKU-0004", "price": 115.0},
    "Bakery":         {"sku": "SKU-0018", "price":  71.5},
    "Fruits & Veggies": {"sku": "SKU-0089", "price":  60.0},
    "Meat & Seafood": {"sku": "SKU-0096", "price":  95.0},
    "Snacks":         {"sku": "SKU-0106", "price":  55.0},
    "Food Grains":    {"sku": "SKU-0127", "price":  45.0},
}

OPENING_QTY  = 30
OPENING_DATE = date(2026, 7, 27)
STORE_ID     = 1

# Demand parameters per category (matches generate_sales_history.py)
CATEGORY_BASE_DEMAND = {
    "Dairy":            25,
    "Bakery":           30,
    "Fruits & Veggies": 40,  # maps to Produce-like demand
    "Meat & Seafood":   18,
    "Snacks":           20,
    "Food Grains":      20,
    # Keep existing categories alive too
    "Produce":          40,
    "Beverages":        35,
    "General":          20,
    "Oil & Masala":     15,
    "Ready-to-Eat":     22,
}


def _generate_daily_sales(base_demand, d_idx, rng_np, rng_rand):
    """Reproduce the same formula used in generate_sales_history.py."""
    d_offset_from_known_start = d_idx  # arbitrary index, we just need reproducible noise
    current_date_weekday = (OPENING_DATE + timedelta(days=d_idx)).weekday()
    day_factor = 1.35 if current_date_weekday in [4, 5, 6] else 0.90
    is_promo = (d_idx % 14 == 0) and rng_rand.random() < 0.8
    promo_factor = 1.5 if is_promo else 1.0
    is_stockout = rng_rand.random() < 0.05 if not is_promo else False

    if is_stockout:
        units_sold = rng_rand.randint(0, 3)
    else:
        expected = base_demand * day_factor * promo_factor
        noise = rng_np.normal(0, max(2, expected * 0.15))
        units_sold = max(0, int(round(expected + noise)))

    price_at_time = DEMO_CATEGORY_SKUS.get("Bakery", {}).get("price", 100.0)  # placeholder
    return units_sold, is_promo, is_stockout


def run():
    np.random.seed(42)
    random.seed(42)
    rng_np = np.random.default_rng(42)
    rng_rand = random.Random(42)

    today = date.today()
    ext_start = date(2026, 8, 1)          # first day to extend
    ext_end   = today                      # inclusive

    if ext_end < ext_start:
        print("Sales history already up to date — nothing to extend.")
        ext_days = 0
    else:
        ext_days = (ext_end - ext_start).days + 1

    with engine.begin() as conn:

        # ------------------------------------------------------------------
        # 1. Ensure demo batches exist for Store 1 (ON CONFLICT DO NOTHING)
        # ------------------------------------------------------------------
        print("=== Step 1: Inserting demo batches (qty=30, opening 2026-07-27) ===")
        for cat, info in DEMO_CATEGORY_SKUS.items():
            sku = info["sku"]
            price = info["price"]
            discount_pct = 20.0
            curr_price = round(price * (1 - discount_pct / 100), 2)
            expiry = date(2026, 8, 27)

            conn.execute(text("""
                INSERT INTO batches (
                    store_id, sku, product_name, category, quantity,
                    cost_price, original_selling_price, current_price,
                    expiration_date, discount_percentage, status,
                    created_at, updated_at
                )
                VALUES (
                    :store_id, :sku, :product_name, :category, :qty,
                    :cost_price, :orig_price, :curr_price,
                    :expiry, :disc_pct, 'ACTIVE',
                    '2026-07-27 00:00:00+00', NOW()
                )
                ON CONFLICT DO NOTHING
            """), {
                "store_id":    STORE_ID,
                "sku":         sku,
                "product_name": f"Demo {cat} Product",
                "category":    cat,
                "qty":         OPENING_QTY,
                "cost_price":  round(price * 0.6, 2),
                "orig_price":  price,
                "curr_price":  curr_price,
                "expiry":      expiry,
                "disc_pct":    discount_pct,
            })
            print(f"  ✓ {cat} ({sku}) — opening qty={OPENING_QTY}")

        print()

        # ------------------------------------------------------------------
        # 2. Extend sales_history from 2026-08-01 → today
        # ------------------------------------------------------------------
        if ext_days == 0:
            print("=== Step 2: Nothing to extend (already up to date) ===")
            return

        print(f"=== Step 2: Extending sales_history {ext_start} → {ext_end} ({ext_days} days) ===")

        # Fetch all existing (store_id, sku, category, price) combos
        combos = conn.execute(text("""
            SELECT DISTINCT sh.store_id, sh.sku, b.category, AVG(sh.price_at_time) as avg_price
            FROM sales_history sh
            LEFT JOIN batches b ON sh.store_id = b.store_id AND sh.sku = b.sku
            GROUP BY sh.store_id, sh.sku, b.category
        """)).fetchall()

        print(f"  Found {len(combos)} (store, SKU) combos to extend.")

        records = []
        total = 0

        for combo in combos:
            c_store_id = combo[0]
            c_sku      = combo[1]
            c_category = combo[2] or "General"
            c_price    = float(combo[3] or 100.0)

            base_demand = CATEGORY_BASE_DEMAND.get(c_category, 20)
            # Small per-SKU jitter for variety (reproducible)
            sku_seed = hash(f"{c_store_id}_{c_sku}") % 10000
            sku_rng_np   = np.random.default_rng(sku_seed)
            sku_rng_rand = random.Random(sku_seed)
            base_demand  = max(5, base_demand + sku_rng_rand.randint(-5, 5))

            for d_idx in range(ext_days):
                current_date = ext_start + timedelta(days=d_idx)
                weekday = current_date.weekday()
                day_factor  = 1.35 if weekday in [4, 5, 6] else 0.90
                is_promo    = (d_idx % 14 == 0) and sku_rng_rand.random() < 0.8
                promo_factor = 1.5 if is_promo else 1.0
                price_at_time = round(c_price * 0.75, 2) if is_promo else c_price
                is_stockout = sku_rng_rand.random() < 0.05 if not is_promo else False

                if is_stockout:
                    units_sold = sku_rng_rand.randint(0, 3)
                else:
                    expected = base_demand * day_factor * promo_factor
                    noise = float(sku_rng_np.normal(0, max(2, expected * 0.15)))
                    units_sold = max(0, int(round(expected + noise)))

                records.append({
                    "store_id":       c_store_id,
                    "sku":            c_sku,
                    "date":           current_date,
                    "units_sold":     units_sold,
                    "price_at_time":  price_at_time,
                    "promotion_flag": is_promo,
                    "stockout_flag":  is_stockout,
                })

                if len(records) >= 5000:
                    _upsert(conn, records)
                    total += len(records)
                    records = []

        if records:
            _upsert(conn, records)
            total += len(records)

        print(f"  ✓ Inserted/updated {total} sales_history rows.")
        print()
        print("=== seed_demo_phase15.py complete ===")


def _upsert(conn, records):
    conn.execute(text("""
        INSERT INTO sales_history
            (store_id, sku, date, units_sold, price_at_time, promotion_flag, stockout_flag, created_at)
        VALUES
            (:store_id, :sku, :date, :units_sold, :price_at_time, :promotion_flag, :stockout_flag, NOW())
        ON CONFLICT (store_id, sku, date) DO UPDATE SET
            units_sold     = EXCLUDED.units_sold,
            price_at_time  = EXCLUDED.price_at_time,
            promotion_flag = EXCLUDED.promotion_flag,
            stockout_flag  = EXCLUDED.stockout_flag
    """), records)


if __name__ == "__main__":
    run()
