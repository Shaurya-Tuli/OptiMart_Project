"""
Generates synthetic sales history data for OptiMart (Demand Forecasting Extension Volume II - Phase 8).
Populates the `sales_history` table with 12 to 24 weeks of daily sales records per store/SKU,
incorporating day-of-week seasonality, promotion spikes, and stockout events.
"""
import os
import sys
import math
import random
import numpy as np
import pandas as pd
from datetime import date, timedelta
from sqlalchemy import text
from app.db import engine

# Ensure parent directory is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def generate_sales_history(weeks: int = 16, random_seed: int = 42):
    np.random.seed(random_seed)
    random.seed(random_seed)

    print(f"Generating synthetic sales history for the past {weeks} weeks...")

    with engine.begin() as conn:
        # Fetch active stores and active SKUs
        stores = conn.execute(text("SELECT id FROM stores")).fetchall()
        store_ids = [s[0] for s in stores]

        if not store_ids:
            print("No stores found in database. Please run scripts/seed.py first.")
            return

        batches = conn.execute(text("SELECT DISTINCT store_id, sku, category, original_selling_price FROM batches")).fetchall()
        if not batches:
            print("No batches found in database. Please run scripts/seed.py first.")
            return

        print("Clearing existing sales_history entries...")
        conn.execute(text("TRUNCATE TABLE sales_history CASCADE"))

        today = date.today()
        start_date = today - timedelta(weeks=weeks)
        total_days = (today - start_date).days

        # Base category demand parameters (mean daily sales)
        category_base_demand = {
            "Dairy": 25,
            "Bakery": 30,
            "Produce": 40,
            "Meat": 18,
            "Beverages": 35,
            "General": 20,
        }

        sales_records = []
        total_rows = 0

        for b in batches:
            store_id, sku, category, price = b[0], b[1], b[2], float(b[3])
            base_demand = category_base_demand.get(category, 20) + random.randint(-5, 5)
            base_demand = max(5, base_demand)

            for d_idx in range(total_days):
                current_date = start_date + timedelta(days=d_idx)
                day_of_week = current_date.weekday()  # 0=Mon, 6=Sun

                # Weekend seasonality factor (higher sales Fri/Sat/Sun)
                day_factor = 1.35 if day_of_week in [4, 5, 6] else 0.90

                # Periodic monthly promotion (e.g. 1 in 14 days)
                is_promo = (d_idx % 14 == 0) and random.random() < 0.8
                promo_factor = 1.5 if is_promo else 1.0
                price_at_time = round(price * 0.75, 2) if is_promo else price

                # Periodic stockout risk (e.g. 5% chance)
                is_stockout = random.random() < 0.05 if not is_promo else False

                if is_stockout:
                    units_sold = random.randint(0, 3)
                else:
                    # Poisson / Normal noise
                    expected_demand = base_demand * day_factor * promo_factor
                    noise = np.random.normal(0, max(2, expected_demand * 0.15))
                    units_sold = max(0, int(round(expected_demand + noise)))

                sales_records.append({
                    "store_id": store_id,
                    "sku": sku,
                    "date": current_date,
                    "units_sold": units_sold,
                    "price_at_time": price_at_time,
                    "promotion_flag": is_promo,
                    "stockout_flag": is_stockout,
                })

                if len(sales_records) >= 5000:
                    _insert_batch(conn, sales_records)
                    total_rows += len(sales_records)
                    sales_records = []

        if sales_records:
            _insert_batch(conn, sales_records)
            total_rows += len(sales_records)

        print(f"Successfully generated and inserted {total_rows} sales_history rows across {len(batches)} store/SKU combinations.")


def _insert_batch(conn, records):
    stmt = text(
        """
        INSERT INTO sales_history (store_id, sku, date, units_sold, price_at_time, promotion_flag, stockout_flag, created_at)
        VALUES (:store_id, :sku, :date, :units_sold, :price_at_time, :promotion_flag, :stockout_flag, NOW())
        ON CONFLICT (store_id, sku, date) DO UPDATE SET
            units_sold = EXCLUDED.units_sold,
            price_at_time = EXCLUDED.price_at_time,
            promotion_flag = EXCLUDED.promotion_flag,
            stockout_flag = EXCLUDED.stockout_flag
        """
    )
    conn.execute(stmt, records)


if __name__ == "__main__":
    generate_sales_history()
