#!/usr/bin/env python3
"""
generate_synthetic_data.py
==========================
OptiMart Synthetic Dataset Generator — Indian Market Edition

Generates a complete, reproducible synthetic dataset for training and demoing
the OptiMart AI food-waste rescue platform, grounded in Indian grocery market
realities (INR pricing, Indian cities, Indian festivals, etc.).

Category / price-range reference:
  - Supermart Grocery Sales (Kaggle, mohamedharris): Oil & Masala, Beverages,
    Food Grains, Fruits & Veggies, Bakery, Snacks — Tamil Nadu regional spread
  - DMart Products (Kaggle, chinmayshanbhag): Indian grocery catalog with MRP

Run:
    pip install pandas numpy faker
    python generate_synthetic_data.py

All outputs land in:
    output/full_dataset/       — full training corpus
    output/seed_demo_subset/   — 1-store, ~20 SKU, 2-week slice for live demo

Author: OptiMart Team
Seed: 42 (fixed throughout for reproducibility)
"""

import os
import sys
import math
import random
from datetime import date, datetime, timedelta
from typing import Dict, List, Tuple

# Force UTF-8 output on Windows where the default console is cp1252
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import numpy as np
import pandas as pd
from faker import Faker

# ─────────────────────────────────────────────────────────────────────────────
# GLOBAL CONFIGURATION  ← tune these constants to resize the dataset
# ─────────────────────────────────────────────────────────────────────────────
SEED               = 42
NUM_STORES         = 6      # How many store branches
NUM_SKUS           = 150    # Unique SKU / product lines
MONTHS_OF_HISTORY  = 6      # Historical window for batches + sales
NUM_USERS          = 500    # Registered app users
NUM_NGOS           = 8      # NGO / shelter partners
BATCHES_PER_SKU_PER_STORE = 3  # Average batch arrivals per SKU/store over history window

# Demo subset config
DEMO_STORE_IDX     = 0      # Index into STORES list used for the demo
DEMO_NUM_SKUS      = 20
DEMO_DAYS          = 14

# ─────────────────────────────────────────────────────────────────────────────
# DATE RANGE HELPERS
# ─────────────────────────────────────────────────────────────────────────────
SIM_END_DATE   = date(2025, 3, 31)   # End of simulated history
SIM_START_DATE = SIM_END_DATE - timedelta(days=30 * MONTHS_OF_HISTORY)

# ─────────────────────────────────────────────────────────────────────────────
# INITIALISE RANDOM SEEDS
# ─────────────────────────────────────────────────────────────────────────────
random.seed(SEED)
np.random.seed(SEED)
fake = Faker("en_IN")
Faker.seed(SEED)

# ─────────────────────────────────────────────────────────────────────────────
# OUTPUT DIRECTORIES
# ─────────────────────────────────────────────────────────────────────────────
OUT_FULL  = "output/full_dataset"
OUT_DEMO  = "output/seed_demo_subset"
os.makedirs(OUT_FULL, exist_ok=True)
os.makedirs(OUT_DEMO, exist_ok=True)

# ─────────────────────────────────────────────────────────────────────────────
# REFERENCE TABLES  (hardcoded from domain knowledge of Indian grocery retail)
# ─────────────────────────────────────────────────────────────────────────────

# Real Indian cities with correct lat/lng and state/region mapping
CITY_METADATA = [
    # city, state, region, lat, lng
    ("Chennai",   "Tamil Nadu",     "South India", 13.0827, 80.2707),
    ("Bengaluru", "Karnataka",      "South India", 12.9716, 77.5946),
    ("Hyderabad", "Telangana",      "South India", 17.3850, 78.4867),
    ("Mumbai",    "Maharashtra",    "West India",  19.0760, 72.8777),
    ("Pune",      "Maharashtra",    "West India",  18.5204, 73.8567),
    ("Delhi",     "Delhi",          "North India", 28.7041, 77.1025),
]

STORE_TYPES = ["supermarket", "hypermarket", "local grocery"]

# Category reference: (category, sub_category, unit_cost_range_inr,
#                      retail_price_range_inr, shelf_life_days_range,
#                      elasticity_coeff, b2b_eligible)
#
# Elasticity coefficient: higher = more price-sensitive demand response.
# Based on typical FMCG elasticity estimates for India (-0.8 to -2.5).
# We use the ABSOLUTE value here; sign is negative in the demand model.
#
# Price ranges grounded in Indian retail:
#   Milk ~₹30-60/L, Bread ~₹40-60, Rice ~₹60-120/kg, Apples ~₹80-200/kg
#   Chips ~₹10-50, Cooking oil ~₹120-180/L, Dal ~₹80-160/kg
CATEGORY_SPEC: List[Dict] = [
    {
        "category": "Dairy",
        "sub_categories": ["Milk", "Curd", "Paneer", "Butter", "Ghee", "Cheese"],
        "cost_range": (20, 90),
        "retail_range": (30, 130),
        "shelf_life_range": (5, 10),
        "elasticity": 1.4,
        "b2b": False,
        "weight_unit": "litre / 500g",
    },
    {
        "category": "Bakery",
        "sub_categories": ["White Bread", "Whole Wheat Bread", "Buns & Rolls",
                           "Cakes", "Biscuits & Cookies", "Rusks"],
        "cost_range": (25, 80),
        "retail_range": (40, 120),
        "shelf_life_range": (2, 5),
        "elasticity": 1.6,
        "b2b": False,
        "weight_unit": "loaf / pack",
    },
    {
        "category": "Fruits & Veggies",
        "sub_categories": ["Apples", "Bananas", "Tomatoes", "Onions",
                           "Potatoes", "Leafy Greens", "Capsicum", "Mangoes"],
        "cost_range": (15, 120),
        "retail_range": (25, 200),
        "shelf_life_range": (3, 7),
        "elasticity": 1.8,
        "b2b": False,
        "weight_unit": "kg",
    },
    {
        "category": "Food Grains",
        "sub_categories": ["Basmati Rice", "Brown Rice", "Toor Dal",
                           "Chana Dal", "Moong Dal", "Atta", "Maida", "Poha"],
        "cost_range": (50, 130),
        "retail_range": (70, 180),
        "shelf_life_range": (180, 365),
        "elasticity": 0.8,
        "b2b": True,
        "weight_unit": "kg",
    },
    {
        "category": "Beverages",
        "sub_categories": ["Packaged Water", "Fruit Juice", "Soft Drinks",
                           "Tea Powder", "Coffee Powder", "Energy Drinks",
                           "Coconut Water", "Lassi"],
        "cost_range": (15, 100),
        "retail_range": (20, 150),
        "shelf_life_range": (30, 180),
        "elasticity": 1.2,
        "b2b": False,
        "weight_unit": "bottle / litre",
    },
    {
        "category": "Snacks",
        "sub_categories": ["Potato Chips", "Namkeen", "Popcorn", "Papad",
                           "Murukku", "Bhujia", "Roasted Nuts", "Chocolate Bar"],
        "cost_range": (10, 60),
        "retail_range": (15, 90),
        "shelf_life_range": (60, 180),
        "elasticity": 1.3,
        "b2b": False,
        "weight_unit": "pack / 100g",
    },
    {
        "category": "Oil & Masala",
        "sub_categories": ["Sunflower Oil", "Mustard Oil", "Coconut Oil",
                           "Turmeric Powder", "Red Chilli Powder", "Coriander Powder",
                           "Garam Masala", "Jeera"],
        "cost_range": (60, 160),
        "retail_range": (90, 220),
        "shelf_life_range": (180, 540),
        "elasticity": 0.7,
        "b2b": True,
        "weight_unit": "litre / kg",
    },
    {
        "category": "Meat & Seafood",
        "sub_categories": ["Chicken Breast", "Chicken Legs", "Eggs",
                           "Fresh Fish", "Prawns", "Mutton"],
        "cost_range": (60, 400),
        "retail_range": (90, 600),
        "shelf_life_range": (1, 3),
        "elasticity": 2.0,
        "b2b": False,
        "weight_unit": "kg / dozen",
    },
    {
        "category": "Ready-to-Eat",
        "sub_categories": ["Instant Noodles", "Ready Curry Paste", "Frozen Paratha",
                           "Ready Dal Makhani", "Idli Mix", "Dhokla Mix"],
        "cost_range": (30, 120),
        "retail_range": (45, 180),
        "shelf_life_range": (10, 90),
        "elasticity": 1.5,
        "b2b": False,
        "weight_unit": "pack",
    },
]

# CO2e factors per category (kg CO2e avoided per kg food rescued)
# Source: USDA ERS and FAO 2011 "Global Food Losses and Food Waste" estimates.
# These are global scientific constants, not India-specific.
CO2E_FACTORS = {
    "Dairy":          3.8,
    "Bakery":         1.5,
    "Fruits & Veggies": 0.9,
    "Food Grains":    1.3,
    "Beverages":      0.5,
    "Snacks":         2.0,
    "Oil & Masala":   2.5,
    "Meat & Seafood": 8.5,
    "Ready-to-Eat":   2.2,
}

# Indian festivals / holidays (MM-DD format, approximate fixed dates)
# We'll check these against the simulated date range
INDIAN_FESTIVALS = [
    ("01-14", "Makar Sankranti / Pongal"),
    ("01-26", "Republic Day"),
    ("02-26", "Maha Shivratri"),       # approximate
    ("03-08", "Holi"),                  # approximate
    ("04-14", "Tamil New Year / Dr. Ambedkar Jayanti"),
    ("04-22", "Eid ul-Fitr"),           # approximate
    ("06-29", "Eid ul-Adha"),           # approximate
    ("08-15", "Independence Day"),
    ("08-26", "Janmashtami"),           # approximate
    ("10-02", "Gandhi Jayanti"),
    ("10-22", "Diwali"),                # approximate
    ("11-01", "Kannada Rajyotsava"),
    ("11-15", "Guru Nanak Jayanti"),
    ("12-25", "Christmas"),
]

def _is_festival(d: date) -> Tuple[bool, str]:
    """Return (True, festival_name) if date is a major Indian festival."""
    md = d.strftime("%m-%d")
    for fmd, fname in INDIAN_FESTIVALS:
        if fmd == md:
            return True, fname
    return False, ""


# ─────────────────────────────────────────────────────────────────────────────
# HELPER UTILITIES
# ─────────────────────────────────────────────────────────────────────────────

def rng_float(lo: float, hi: float) -> float:
    return round(random.uniform(lo, hi), 2)

def rng_int(lo: int, hi: int) -> int:
    return random.randint(lo, hi)

def date_range(start: date, end: date) -> List[date]:
    delta = (end - start).days
    return [start + timedelta(days=i) for i in range(delta + 1)]

def round_inr(v: float) -> float:
    """Round to nearest sensible INR denomination (0.50 steps)."""
    return round(v * 2) / 2

def fictional_store_name() -> str:
    """Generate fictional Indian supermarket / kirana chain names."""
    prefixes = [
        "Fresh", "Green", "Daily", "Smart", "Namma", "Aapka",
        "Quick", "Pure", "Aahar", "Sewa", "Bazaar", "Sabji",
    ]
    suffixes = [
        "Mart", "Bazaar", "Basket", "Corner", "Hub", "Point",
        "Store", "Kirana", "Express", "Palace", "Garden",
    ]
    return f"{random.choice(prefixes)}{random.choice(suffixes)}"

def fictional_ngo_name() -> str:
    """Generate plausible Indian NGO / shelter names — NOT real organizations."""
    words1 = ["Akshaya", "Anna", "Seva", "Prerna", "Shakti", "Asha",
              "Sahara", "Daya", "Prabha", "Sneha", "Arogya", "Shanti"]
    words2 = ["Daan", "Sewa", "Nidhi", "Mandal", "Foundation",
              "Trust", "Samiti", "Sangha", "Seva", "Samaj"]
    words3 = ["Foundation", "Trust", "Charitable Society",
              "NGO", "Welfare Society", "Community Centre", ""]
    return f"{random.choice(words1)} {random.choice(words2)} {random.choice(words3)}".strip()


# ─────────────────────────────────────────────────────────────────────────────
# TABLE 1: STORES
# ─────────────────────────────────────────────────────────────────────────────

def generate_stores(n: int = NUM_STORES) -> pd.DataFrame:
    """
    Generates store branches across Indian cities.
    Each store gets a unique fictional name, real city lat/lng, and a type.
    """
    rows = []
    used_cities = random.choices(CITY_METADATA, k=n)
    for i, (city, state, region, lat, lng) in enumerate(used_cities, start=1):
        # Add small jitter so stores in the same city are distinct locations
        lat_j = lat + np.random.normal(0, 0.03)
        lng_j = lng + np.random.normal(0, 0.03)
        rows.append({
            "store_id":   f"STR-{i:03d}",
            "store_name": fictional_store_name(),
            "city":       city,
            "state":      state,
            "region":     region,
            "latitude":   round(lat_j, 5),
            "longitude":  round(lng_j, 5),
            "store_type": random.choice(STORE_TYPES),
        })
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
# TABLE 2: PRODUCTS / SKU CATALOG
# ─────────────────────────────────────────────────────────────────────────────

def generate_products(n: int = NUM_SKUS) -> pd.DataFrame:
    """
    Creates a catalog of SKUs drawn from the category spec.
    Shelf-life and elasticity are category-specific; prices are in INR.
    """
    rows = []
    skus_per_cat = n // len(CATEGORY_SPEC)
    sku_counter = 1
    for cat_spec in CATEGORY_SPEC:
        cat      = cat_spec["category"]
        subcats  = cat_spec["sub_categories"]
        clo, chi = cat_spec["cost_range"]
        rlo, rhi = cat_spec["retail_range"]
        slo, shi = cat_spec["shelf_life_range"]
        b2b      = cat_spec["b2b"]
        for _ in range(skus_per_cat):
            sub = random.choice(subcats)
            cost   = round_inr(rng_float(clo, chi))
            retail = round_inr(max(cost * 1.1, rng_float(rlo, rhi)))  # retail > cost
            shelf  = rng_int(slo, shi)
            rows.append({
                "sku_id":                f"SKU-{sku_counter:04d}",
                "product_name":          f"{sub} ({cat_spec['weight_unit']})",
                "category":              cat,
                "sub_category":          sub,
                "unit_cost_inr":         cost,
                "standard_retail_price_inr": retail,
                "typical_shelf_life_days":   shelf,
                "b2b_eligible":          b2b,
            })
            sku_counter += 1
    # Fill up to exact n if division was uneven
    while len(rows) < n:
        cat_spec = random.choice(CATEGORY_SPEC)
        sub      = random.choice(cat_spec["sub_categories"])
        clo, chi = cat_spec["cost_range"]
        rlo, rhi = cat_spec["retail_range"]
        slo, shi = cat_spec["shelf_life_range"]
        cost   = round_inr(rng_float(clo, chi))
        retail = round_inr(max(cost * 1.1, rng_float(rlo, rhi)))
        shelf  = rng_int(slo, shi)
        rows.append({
            "sku_id":                f"SKU-{sku_counter:04d}",
            "product_name":          f"{sub} ({cat_spec['weight_unit']})",
            "category":              cat_spec["category"],
            "sub_category":          sub,
            "unit_cost_inr":         cost,
            "standard_retail_price_inr": retail,
            "typical_shelf_life_days":   shelf,
            "b2b_eligible":          cat_spec["b2b"],
        })
        sku_counter += 1
    return pd.DataFrame(rows[:n])


# ─────────────────────────────────────────────────────────────────────────────
# TABLE 3: INVENTORY BATCHES
# ─────────────────────────────────────────────────────────────────────────────

def generate_batches(stores: pd.DataFrame,
                     products: pd.DataFrame,
                     n_per_sku_per_store: int = BATCHES_PER_SKU_PER_STORE
                     ) -> pd.DataFrame:
    """
    For each (store, SKU) pair, generates multiple batch arrivals over the
    historical window.  current_price starts at retail and may be pre-marked-down
    if batch arrives with < 40% shelf life remaining.

    Batch quantities are sized per store_type:
      hypermarket: 30-150 units, supermarket: 15-80, local grocery: 5-30
    """
    qty_ranges = {
        "hypermarket":   (30, 150),
        "supermarket":   (15, 80),
        "local grocery": (5,  30),
    }
    shelf_sections = ["Aisle-A", "Aisle-B", "Refrigerated", "Frozen",
                      "Produce Rack", "Checkout Display", "Bulk Bins"]
    rows = []
    batch_counter = 1
    history_days = (SIM_END_DATE - SIM_START_DATE).days

    for _, store in stores.iterrows():
        qlo, qhi = qty_ranges[store["store_type"]]
        for _, sku in products.iterrows():
            shelf_life = sku["typical_shelf_life_days"]
            for _ in range(n_per_sku_per_store):
                received = SIM_START_DATE + timedelta(
                    days=rng_int(0, history_days - 1))
                expiry   = received + timedelta(days=shelf_life)
                qty_recv = rng_int(qlo, qhi)
                remaining_life_pct = random.random()  # 0..1 of shelf life used up
                # Some batches arrive with partial shelf life (returns, slow stock)
                if remaining_life_pct < 0.15:
                    # Near-expiry arrival — pre-discounted by 20-40%
                    price = round_inr(
                        sku["standard_retail_price_inr"] * rng_float(0.60, 0.80))
                else:
                    price = sku["standard_retail_price_inr"]
                rows.append({
                    "batch_id":         f"BAT-{batch_counter:06d}",
                    "store_id":         store["store_id"],
                    "sku_id":           sku["sku_id"],
                    "quantity_received": qty_recv,
                    "quantity_on_hand":  qty_recv,     # will be updated by sales sim
                    "received_date":    received.isoformat(),
                    "expiry_date":      expiry.isoformat(),
                    "current_price_inr": price,
                    "shelf_section":    random.choice(shelf_sections),
                })
                batch_counter += 1
    df = pd.DataFrame(rows)
    df = df.sort_values("received_date").reset_index(drop=True)
    return df


# ─────────────────────────────────────────────────────────────────────────────
# TABLE 5: WEATHER (generated BEFORE sales so sales can reference weather)
# ─────────────────────────────────────────────────────────────────────────────

def generate_weather(stores: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Generates historical daily weather per city (not per-store, since a city
    has one weather pattern) and a 48-hour forecast stub.

    Weather model:
      - Base temperature by region (South hotter; North colder in winter)
      - Monsoon season (Jun-Sep) increases precipitation probability
      - Condition derived from precipitation probability threshold
    """
    city_weather: Dict[str, Dict[str, List]] = {}  # city -> {date: row}
    all_dates = date_range(SIM_START_DATE, SIM_END_DATE)

    for _, store in stores.iterrows():
        city   = store["city"]
        region = store["region"]
        if city in city_weather:
            continue  # already generated for this city
        city_weather[city] = {}

        # Base temperature by region (°C, annual average)
        base_temp = {
            "South India": 29.0,
            "West India":  28.0,
            "North India": 25.0,
        }.get(region, 27.0)

        for d in all_dates:
            month = d.month
            # Seasonal temperature swing
            if region == "North India":
                # Cold winters, hot summers
                temp_offset = 10 * math.sin((month - 4) * math.pi / 6)
            else:
                # Mild swing in South/West
                temp_offset = 3 * math.sin((month - 4) * math.pi / 6)

            temp = round(base_temp + temp_offset + np.random.normal(0, 1.5), 1)

            # Monsoon: Jun-Sep has high rain probability; sporadic otherwise
            if 6 <= month <= 9:
                precip_prob = rng_int(40, 85)
            elif month in (10, 11, 3, 4):
                precip_prob = rng_int(5, 30)
            else:
                precip_prob = rng_int(0, 15)

            # Condition classification
            if precip_prob >= 60:
                cond = "rainy"
            elif precip_prob >= 30:
                cond = "cloudy"
            elif temp >= 38:
                cond = "heatwave"
            else:
                cond = "sunny"

            city_weather[city][d.isoformat()] = {
                "city":                       city,
                "date":                       d.isoformat(),
                "avg_temperature_c":          temp,
                "precipitation_probability_pct": precip_prob,
                "condition":                  cond,
            }

    # Flatten to rows, join store_id
    hist_rows = []
    for _, store in stores.iterrows():
        city = store["city"]
        for dkey, wrow in city_weather[city].items():
            hist_rows.append({"store_id": store["store_id"], **wrow})
    weather_hist = pd.DataFrame(hist_rows)

    # 48-hour forecast (rolling from SIM_END_DATE)
    forecast_rows = []
    for _, store in stores.iterrows():
        city = store["city"]
        region = store["region"]
        base_temp = {"South India": 29.0, "West India": 28.0, "North India": 25.0}.get(region, 27.0)
        for h in range(48):
            fc_dt = datetime(SIM_END_DATE.year, SIM_END_DATE.month, SIM_END_DATE.day) + timedelta(hours=h+1)
            temp = round(base_temp + np.random.normal(0, 2), 1)
            precip = rng_int(0, 40)
            cond = "rainy" if precip >= 35 else ("cloudy" if precip >= 20 else "sunny")
            forecast_rows.append({
                "store_id":                   store["store_id"],
                "city":                       city,
                "forecast_datetime":          fc_dt.isoformat(),
                "hour_ahead":                 h + 1,
                "predicted_temp_c":           temp,
                "precipitation_probability_pct": precip,
                "predicted_condition":        cond,
            })
    weather_fc = pd.DataFrame(forecast_rows)

    return weather_hist, weather_fc, city_weather


# ─────────────────────────────────────────────────────────────────────────────
# TABLE 6: FOOT TRAFFIC
# ─────────────────────────────────────────────────────────────────────────────

def generate_foot_traffic(stores: pd.DataFrame) -> pd.DataFrame:
    """
    Simulates intraday transaction counts per store per day.

    Intraday shape (transactions per hour, index 0=midnight):
      - Low: 0-9h (store closed or low traffic)
      - Morning bump: 9-11h
      - Lunch peak: 12-14h
      - Afternoon lull: 15-17h
      - Evening peak: 18-21h (highest)
      - Close: 22h onwards (near-zero)

    Multipliers:
      - Weekend: +25%
      - Festival/holiday: +60%
      - Rainy condition: -20% (perishables traffic drops)
    """
    # Baseline hourly weights (24 hours)
    HOURLY_WEIGHTS = [
        0.0, 0.0, 0.0, 0.0, 0.0, 0.0,  # 0-5h  (closed)
        0.5, 1.0, 1.5,                  # 6-8h  (opening)
        2.0, 2.5, 2.5,                  # 9-11h (morning)
        3.5, 3.0, 2.8,                  # 12-14h (lunch)
        2.5, 2.5, 2.5,                  # 15-17h (afternoon)
        4.0, 4.5, 4.0, 3.0,             # 18-21h (evening peak)
        1.0, 0.5,                        # 22-23h (closing)
    ]
    BASE_DAILY_TXNS = {
        "hypermarket":   800,
        "supermarket":   350,
        "local grocery": 120,
    }
    rows = []
    all_dates = date_range(SIM_START_DATE, SIM_END_DATE)
    for _, store in stores.iterrows():
        base_txns = BASE_DAILY_TXNS[store["store_type"]]
        for d in all_dates:
            is_weekend = d.weekday() >= 5
            is_fest, fest_name = _is_festival(d)
            day_mult = (1.25 if is_weekend else 1.0) * (1.6 if is_fest else 1.0)
            total_day = int(base_txns * day_mult * rng_float(0.85, 1.15))
            weight_sum = sum(HOURLY_WEIGHTS)
            for h, w in enumerate(HOURLY_WEIGHTS):
                expected_h = total_day * (w / weight_sum)
                actual_h = max(0, int(np.random.poisson(max(1e-6, expected_h))))
                rows.append({
                    "store_id":         store["store_id"],
                    "date":             d.isoformat(),
                    "hour_of_day":      h,
                    "transaction_count": actual_h,
                    "is_weekend":       is_weekend,
                    "local_event":      fest_name if is_fest else "",
                })
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
# TABLE 4: HISTORICAL SALES / DEMAND  (the core ML training table)
# ─────────────────────────────────────────────────────────────────────────────

def compute_demand(
    base_qty:      int,
    price_ratio:   float,       # current_price / standard_retail_price
    elasticity:    float,       # category-specific absolute elasticity
    time_to_exp_h: float,       # hours remaining to expiry at time of sale
    shelf_life_h:  float,       # total shelf life in hours
    condition:     str,         # weather condition
    day_of_week:   int,         # 0=Monday … 6=Sunday
    discount_pct:  float,       # discount depth 0-1
) -> int:
    """
    Demand model:
    ─────────────
    1. PRICE ELASTICITY: units_base * price_ratio^(-elasticity)
       A price_ratio < 1 (discount) boosts demand. Elasticity is category-specific.

    2. URGENCY MULTIPLIER: sigmoid curve peaking as time_to_expiry_hours → 0.
       Once discount threshold > 25% is crossed, the urgency effect kicks in harder.
       Formula: 1 + urgency_weight * sigmoid(-12 * (tte_pct - 0.15))
       where tte_pct = time_to_expiry / shelf_life

    3. WEATHER DAMPENER: rainy/heatwave reduces perishable impulse purchases.
       Rain → -15% on dairy, produce, bakery. Heatwave → -10% on dairy.

    4. DAY-OF-WEEK MULTIPLIER: weekend spike (Sat=+20%, Sun=+15%)

    5. GAUSSIAN NOISE: ±15% random noise to avoid perfectly clean signal.
    """
    # 1. Price elasticity (power law)
    price_ratio = max(price_ratio, 0.01)  # avoid zero-division
    elastic_factor = price_ratio ** (-elasticity)

    # 2. Urgency effect (sigmoid)
    tte_pct = time_to_exp_h / max(shelf_life_h, 1)
    urgency_raw = 1 / (1 + math.exp(12 * (tte_pct - 0.15)))
    # Scale urgency by how deep the discount is (deeper discount = larger urgency pop)
    urgency_weight = 0.8 if discount_pct >= 0.25 else 0.3
    urgency_mult = 1.0 + urgency_weight * urgency_raw

    # 3. Weather dampener (affects categories differently — simplified to single float)
    weather_dampen = {
        "sunny":    1.00,
        "cloudy":   0.95,
        "rainy":    0.82,
        "heatwave": 0.88,
    }.get(condition, 1.0)

    # 4. Day-of-week multiplier
    dow_mult = {0: 1.0, 1: 1.0, 2: 1.0, 3: 1.0, 4: 1.05, 5: 1.20, 6: 1.15}[day_of_week]

    # Combine all factors
    demand_raw = (base_qty * elastic_factor * urgency_mult *
                  weather_dampen * dow_mult)

    # 5. Gaussian noise ±15%
    noise = np.random.normal(1.0, 0.15)
    demand = max(0, int(round(demand_raw * noise)))
    return demand


def generate_sales_history(batches: pd.DataFrame,
                           products: pd.DataFrame,
                           weather_hist: pd.DataFrame,
                           city_weather: Dict,
                           stores: pd.DataFrame) -> pd.DataFrame:
    """
    For each batch, simulates a day-by-day sell-down trajectory.

    Outcomes per batch (assigned at end of its active window):
      - sold_out:          on_hand reached 0 before expiry
      - partially_sold:    some stock remains but batch has expired
      - expired_unsold:    very little sold before expiry
      - donated:           batch in its last 12h, still ≥ 10% stock, routed to NGO

    Each sale event is recorded at a random hour during store opening hours (9-22).
    """
    # Build product lookup for fast access
    prod_lu = products.set_index("sku_id").to_dict("index")

    # Build weather lookup: city -> date_str -> condition
    city_wx = {}
    for city, dates in city_weather.items():
        city_wx[city] = {d: v["condition"] for d, v in dates.items()}

    # Build store lookup
    store_lu = stores.set_index("store_id").to_dict("index")

    rows = []
    record_counter = 1
    cat_spec_lu = {s["category"]: s for s in CATEGORY_SPEC}

    for _, batch in batches.iterrows():
        sku_id   = batch["sku_id"]
        store_id = batch["store_id"]
        prod     = prod_lu[sku_id]
        cat      = prod["category"]
        spec     = cat_spec_lu[cat]
        elasticity = spec["elasticity"]
        shelf_life_days = prod["typical_shelf_life_days"]
        shelf_life_h    = shelf_life_days * 24.0
        retail_price    = prod["standard_retail_price_inr"]
        current_price   = batch["current_price_inr"]
        store_city      = store_lu[store_id]["city"]

        received = date.fromisoformat(batch["received_date"])
        expiry   = date.fromisoformat(batch["expiry_date"])
        qty_on_hand = batch["quantity_received"]
        if qty_on_hand <= 0:
            continue

        # Base units-per-day without any discounting (Poisson rate estimate)
        # Assume a batch sells through in ~70% of shelf life at full price
        daily_base = max(1, qty_on_hand / max(1, shelf_life_days * 0.7))

        active_dates = date_range(received, min(expiry, SIM_END_DATE))
        batch_outcome = "expired_unsold"  # default

        for d in active_dates:
            if qty_on_hand <= 0:
                batch_outcome = "sold_out"
                break
            tte_h = ((expiry - d).days * 24)
            # Dynamic markdown: increase discount as expiry approaches
            # 3 days out → 10% off, 2 days → 20%, 1 day → 35%, same-day → 50%
            days_to_exp = (expiry - d).days
            if days_to_exp <= 0:
                discount_pct = 0.50
            elif days_to_exp == 1:
                discount_pct = 0.35
            elif days_to_exp == 2:
                discount_pct = 0.20
            elif days_to_exp <= 5 and shelf_life_days <= 7:
                discount_pct = 0.10
            else:
                discount_pct = 0.0
            # For initial batch pre-discount:
            initial_discount = 1 - (current_price / retail_price)
            discount_pct = max(discount_pct, initial_discount)
            sale_price = round_inr(retail_price * (1 - discount_pct))

            condition = city_wx.get(store_city, {}).get(d.isoformat(), "sunny")
            dow = d.weekday()
            is_weekend = dow >= 5
            is_holiday, _ = _is_festival(d)
            price_ratio = sale_price / retail_price

            # Donation routing: last 12 hours + ≥ 10% stock remaining
            if days_to_exp <= 0 and qty_on_hand >= batch["quantity_received"] * 0.10:
                batch_outcome = "donated"
                # Record a donation row and stop
                rows.append({
                    "record_id":              f"SL-{record_counter:08d}",
                    "batch_id":               batch["batch_id"],
                    "store_id":               store_id,
                    "sku_id":                 sku_id,
                    "date":                   d.isoformat(),
                    "hour_of_day":            10,
                    "units_sold":             qty_on_hand,
                    "price_at_sale_inr":      0,
                    "discount_depth_pct":     100.0,
                    "time_to_expiry_hours_at_sale": 0,
                    "day_of_week":            dow,
                    "is_weekend":             is_weekend,
                    "is_holiday":             is_holiday,
                    "outcome":                "donated",
                })
                record_counter += 1
                qty_on_hand = 0
                break

            demand = compute_demand(
                base_qty=daily_base,
                price_ratio=price_ratio,
                elasticity=elasticity,
                time_to_exp_h=tte_h,
                shelf_life_h=shelf_life_h,
                condition=condition,
                day_of_week=dow,
                discount_pct=discount_pct,
            )
            units = min(demand, qty_on_hand)
            if units <= 0:
                continue
            qty_on_hand -= units
            sale_hour = rng_int(9, 21)
            rows.append({
                "record_id":              f"SL-{record_counter:08d}",
                "batch_id":               batch["batch_id"],
                "store_id":               store_id,
                "sku_id":                 sku_id,
                "date":                   d.isoformat(),
                "hour_of_day":            sale_hour,
                "units_sold":             units,
                "price_at_sale_inr":      sale_price,
                "discount_depth_pct":     round(discount_pct * 100, 1),
                "time_to_expiry_hours_at_sale": max(0, tte_h),
                "day_of_week":            dow,
                "is_weekend":             is_weekend,
                "is_holiday":             is_holiday,
                "outcome":                "sold_out" if qty_on_hand == 0 else "partially_sold",
            })
            record_counter += 1

        # Final outcome determination
        if qty_on_hand > 0 and batch_outcome not in ("sold_out", "donated"):
            remaining_pct = qty_on_hand / batch["quantity_received"]
            batch_outcome = "expired_unsold" if remaining_pct > 0.30 else "partially_sold"
            # Mark last row with final outcome if it exists
        # Update batch outcome on last row for this batch
        # (rows are in order so the last row for this batch is rows[-1])
        if rows and rows[-1]["batch_id"] == batch["batch_id"]:
            rows[-1]["outcome"] = batch_outcome

    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
# TABLE 7: CUSTOMERS / USERS
# ─────────────────────────────────────────────────────────────────────────────

def generate_users(stores: pd.DataFrame, n: int = NUM_USERS) -> pd.DataFrame:
    """
    Privacy-conscious user table — no real PII.
    Geolocation is city-level with ±0.15° jitter (approx 10-15 km radius).
    Phone numbers follow Indian format: +91-XXXXXXXXXX (10 digits, start 6-9).
    """
    categories = [s["category"] for s in CATEGORY_SPEC]
    channels   = ["SMS", "WhatsApp", "reply-YES"]
    rows = []
    store_cities = list(zip(stores["city"], stores["latitude"], stores["longitude"]))

    for i in range(1, n + 1):
        city, base_lat, base_lng = random.choice(store_cities)
        coarse_lat = round(base_lat + np.random.uniform(-0.15, 0.15), 3)
        coarse_lng = round(base_lng + np.random.uniform(-0.15, 0.15), 3)
        # Indian mobile: starts with 6, 7, 8, or 9
        ph_start = random.choice([6, 7, 8, 9])
        ph_rest  = "".join([str(rng_int(0, 9)) for _ in range(9)])
        phone    = f"+91{ph_start}{ph_rest}"
        # Opt-in categories (1-4 categories)
        n_cats   = rng_int(1, 4)
        opted_in = random.sample(categories, n_cats)
        reliability  = round(rng_float(0.50, 1.0), 3)
        rows.append({
            "user_id":                    f"USR-{i:05d}",
            "city":                       city,
            "coarse_lat":                 coarse_lat,
            "coarse_lng":                 coarse_lng,
            "phone":                      phone,
            "category_opt_ins":           "|".join(opted_in),
            "preferred_channel":          random.choice(channels),
            "reliability_score":          reliability,
            "price_sensitivity_threshold_pct": rng_int(10, 60),
            "response_latency_minutes_avg":    rng_int(2, 45),
        })
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
# TABLE 8: CLAIMS / USER ACTIVITY
# ─────────────────────────────────────────────────────────────────────────────

def generate_claims(users: pd.DataFrame,
                    batches: pd.DataFrame,
                    sales: pd.DataFrame) -> pd.DataFrame:
    """
    Generates claim events for a subset of sale rows.
    ~30% of sale events result in a trackable claim (user responded to notification).
    Claim completion probability = user reliability_score * random noise.

    claim_id, user_id, batch_id, store_id, claimed_at, channel_used,
    discount_at_claim, fulfillment_type, completed, completed_at
    """
    user_lu = users.set_index("user_id").to_dict("index")
    user_ids = list(users["user_id"])
    channels = ["SMS", "WhatsApp", "reply-YES"]
    fulfillment = ["pickup", "delivery"]

    # Sample ~30% of sales rows to become claim events
    claimed_sales = sales.sample(frac=0.30, random_state=SEED)
    rows = []
    for i, (_, sale) in enumerate(claimed_sales.iterrows(), start=1):
        uid = random.choice(user_ids)
        usr = user_lu[uid]
        claimed_dt = datetime.fromisoformat(sale["date"]) + timedelta(
            hours=sale["hour_of_day"],
            minutes=rng_int(0, usr["response_latency_minutes_avg"]))
        complete = random.random() < usr["reliability_score"]
        completed_at = None
        if complete:
            completed_at = (claimed_dt + timedelta(
                minutes=rng_int(15, 120))).isoformat()
        rows.append({
            "claim_id":          f"CLM-{i:07d}",
            "user_id":           uid,
            "batch_id":          sale["batch_id"],
            "store_id":          sale["store_id"],
            "claimed_at":        claimed_dt.isoformat(),
            "channel_used":      random.choice(channels),
            "discount_at_claim_pct": sale["discount_depth_pct"],
            "fulfillment_type":  random.choice(fulfillment),
            "completed":         complete,
            "completed_at":      completed_at,
        })
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
# TABLE 9: NGO STANDING ORDERS
# ─────────────────────────────────────────────────────────────────────────────

def generate_ngo_standing_orders(stores: pd.DataFrame,
                                  n: int = NUM_NGOS) -> pd.DataFrame:
    """
    NGO/shelter standing orders for priority allocation of near-expiry batches.
    Names are fictional plausible Indian NGO names.
    """
    categories = [s["category"] for s in CATEGORY_SPEC]
    delivery   = ["pickup", "delivery", "pickup"]  # pickup more common
    rows = []
    cities = list(stores["city"].unique())

    for i in range(1, n + 1):
        n_cats     = rng_int(1, 3)
        cat_prio   = "|".join(random.sample(categories, n_cats))
        city       = random.choice(cities)
        ngo_name   = fictional_ngo_name()
        verified   = random.random() > 0.2  # 80% verified
        rows.append({
            "ngo_id":                    f"NGO-{i:03d}",
            "ngo_name":                  ngo_name,
            "city":                      city,
            "verified_status":           "verified" if verified else "pending",
            "category_priority":         cat_prio,
            "min_quantity_kg":           rng_int(5, 50),
            "priority_time_window_hours": rng_int(6, 48),
            "delivery_or_pickup":        random.choice(delivery),
        })
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
# TABLE 10A: CATEGORY SHELF-LIFE CURVES (reference / cold-start lookup)
# ─────────────────────────────────────────────────────────────────────────────

def generate_shelf_life_curves() -> pd.DataFrame:
    rows = []
    for spec in CATEGORY_SPEC:
        lo, hi = spec["shelf_life_range"]
        rows.append({
            "category":                     spec["category"],
            "avg_shelf_life_days":          round((lo + hi) / 2, 1),
            "min_shelf_life_days":          lo,
            "max_shelf_life_days":          hi,
            "elasticity_coefficient":       spec["elasticity"],
            "b2b_eligible":                 spec["b2b"],
        })
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
# TABLE 10B: CO2E CONVERSION FACTORS (published reference constants)
# ─────────────────────────────────────────────────────────────────────────────

def generate_co2e_factors() -> pd.DataFrame:
    rows = []
    for cat, factor in CO2E_FACTORS.items():
        rows.append({
            "category":                  cat,
            "kg_co2e_avoided_per_kg_food": factor,
            "source":                    "FAO (2011) Global Food Losses + USDA ERS estimates",
            "notes":                     "Global scientific constants; currency/pricing layer is India-specific (INR)",
        })
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
# DEMO SUBSET SLICER
# ─────────────────────────────────────────────────────────────────────────────

def make_demo_subset(stores, products, batches, sales, weather_hist,
                     foot_traffic, users, claims, ngo) -> Dict[str, pd.DataFrame]:
    """
    Carves out a 1-store × ~20-SKU × 2-week slice for live demo seeding.
    """
    demo_store_id = stores.iloc[DEMO_STORE_IDX]["store_id"]
    demo_end      = SIM_END_DATE
    demo_start    = demo_end - timedelta(days=DEMO_DAYS)
    demo_skus     = products.sample(n=DEMO_NUM_SKUS, random_state=SEED)["sku_id"].tolist()

    d_stores = stores[stores["store_id"] == demo_store_id].copy()
    d_products = products[products["sku_id"].isin(demo_skus)].copy()
    d_batches = batches[
        (batches["store_id"] == demo_store_id) &
        (batches["sku_id"].isin(demo_skus)) &
        (batches["received_date"] >= demo_start.isoformat())
    ].copy()
    batch_ids = d_batches["batch_id"].tolist()
    d_sales = sales[
        (sales["store_id"] == demo_store_id) &
        (sales["date"] >= demo_start.isoformat()) &
        (sales["date"] <= demo_end.isoformat()) &
        (sales["batch_id"].isin(batch_ids))
    ].copy()
    d_weather = weather_hist[
        (weather_hist["store_id"] == demo_store_id) &
        (weather_hist["date"] >= demo_start.isoformat()) &
        (weather_hist["date"] <= demo_end.isoformat())
    ].copy()
    d_traffic = foot_traffic[
        (foot_traffic["store_id"] == demo_store_id) &
        (foot_traffic["date"] >= demo_start.isoformat()) &
        (foot_traffic["date"] <= demo_end.isoformat())
    ].copy()
    d_claims = claims[claims["store_id"] == demo_store_id].copy()

    return {
        "stores.csv":        d_stores,
        "products.csv":      d_products,
        "batches.csv":       d_batches,
        "sales_history.csv": d_sales,
        "weather_history.csv": d_weather,
        "foot_traffic.csv":  d_traffic,
        "claims.csv":        d_claims,
        "ngo_standing_orders.csv": ngo,
    }


# ─────────────────────────────────────────────────────────────────────────────
# DATA DICTIONARY
# ─────────────────────────────────────────────────────────────────────────────

DATA_DICTIONARY = """# OptiMart Synthetic Dataset — Data Dictionary

> **Currency**: All monetary values are in Indian Rupees (INR / ₹).  
> **Dates**: ISO 8601 format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS).  
> **Seed**: Fixed at `42` — fully reproducible.  
> **Reference sources**: CO2e factors from FAO 2011 + USDA ERS (global scientific constants). Pricing calibrated to Indian grocery retail.

---

## stores.csv
| Column | Type | Description |
|--------|------|-------------|
| store_id | string | Unique store identifier (STR-001 … STR-NNN) |
| store_name | string | Fictional Indian grocery brand name |
| city | string | Indian city (Chennai / Bengaluru / Hyderabad / Mumbai / Pune / Delhi) |
| state | string | Indian state (Tamil Nadu / Karnataka / Telangana / Maharashtra / Delhi) |
| region | string | Broad region (South India / West India / North India) |
| latitude | float | Real city centroid + small jitter (WGS84) |
| longitude | float | Real city centroid + small jitter (WGS84) |
| store_type | string | supermarket / hypermarket / local grocery |

---

## products.csv  (SKU catalog)
| Column | Type | Description |
|--------|------|-------------|
| sku_id | string | Unique product code (SKU-0001 … SKU-NNNN) |
| product_name | string | Human-readable name including weight/volume unit |
| category | string | Top-level grocery category (Dairy / Bakery / Fruits & Veggies / Food Grains / Beverages / Snacks / Oil & Masala / Meat & Seafood / Ready-to-Eat) |
| sub_category | string | More granular product type within category |
| unit_cost_inr | float | Wholesale / landed cost in INR |
| standard_retail_price_inr | float | Full MRP / shelf price in INR |
| typical_shelf_life_days | int | Expected shelf life from production: Dairy 5-10, Bakery 2-5, Produce 3-7, Grains 180-365, Snacks 60-180 |
| b2b_eligible | bool | Whether bulk B2B ordering is appropriate (True for grains, oils) |

---

## batches.csv  (inventory arrivals)
| Column | Type | Description |
|--------|------|-------------|
| batch_id | string | Unique batch identifier (BAT-000001 … ) |
| store_id | string | FK → stores.store_id |
| sku_id | string | FK → products.sku_id |
| quantity_received | int | Units in the batch at arrival |
| quantity_on_hand | int | Units remaining (snapshot at generation time = quantity_received) |
| received_date | date | Date batch arrived at store (YYYY-MM-DD) |
| expiry_date | date | Best-before / use-by date (YYYY-MM-DD) |
| current_price_inr | float | Price at time of data generation (may be pre-marked down) |
| shelf_section | string | Physical store section (Refrigerated / Produce Rack / etc.) |

---

## sales_history.csv  (core ML training table)
| Column | Type | Description |
|--------|------|-------------|
| record_id | string | Unique sales record (SL-00000001 … ) |
| batch_id | string | FK → batches.batch_id |
| store_id | string | FK → stores.store_id |
| sku_id | string | FK → products.sku_id |
| date | date | Calendar date of sale (YYYY-MM-DD) |
| hour_of_day | int | Hour of transaction (9-21, store hours) |
| units_sold | int | Units sold in this time window |
| price_at_sale_inr | float | Actual sale price in INR (≤ standard_retail_price) |
| discount_depth_pct | float | Percentage discount applied (0 = full price, 50 = half price) |
| time_to_expiry_hours_at_sale | float | Hours remaining until batch expires at time of sale |
| day_of_week | int | 0=Monday … 6=Sunday |
| is_weekend | bool | True if Saturday or Sunday |
| is_holiday | bool | True if Indian public holiday / major festival |
| outcome | string | sold_out / partially_sold / expired_unsold / donated |

**Demand model parameters used:**
- Price elasticity: power-law `demand ∝ (price/retail)^(-elasticity)` with category-specific elasticity (0.7–2.0)
- Urgency: sigmoid boost as time_to_expiry → 0, amplified when discount_depth ≥ 25%
- Weather dampener: rainy −18%, heatwave −12%, cloudy −5%
- Day-of-week: Saturday +20%, Sunday +15%, Friday +5%
- Gaussian noise: σ = 0.15 on top of deterministic signal

---

## weather_history.csv
| Column | Type | Description |
|--------|------|-------------|
| store_id | string | FK → stores.store_id |
| city | string | City name (same as store city) |
| date | date | Calendar date (YYYY-MM-DD) |
| avg_temperature_c | float | Daily average temperature in °C |
| precipitation_probability_pct | int | Estimated rain probability (0-100) |
| condition | string | sunny / cloudy / rainy / heatwave — used as input to sales demand model |

---

## weather_forecast.csv  (48-hour rolling forecast)
| Column | Type | Description |
|--------|------|-------------|
| store_id | string | FK → stores.store_id |
| city | string | City name |
| forecast_datetime | datetime | UTC datetime of forecast horizon |
| hour_ahead | int | 1 to 48 |
| predicted_temp_c | float | Forecast temperature °C |
| precipitation_probability_pct | int | Forecast rain probability |
| predicted_condition | string | sunny / cloudy / rainy |

---

## foot_traffic.csv
| Column | Type | Description |
|--------|------|-------------|
| store_id | string | FK → stores.store_id |
| date | date | Calendar date (YYYY-MM-DD) |
| hour_of_day | int | 0-23 |
| transaction_count | int | Simulated POS transactions in that hour |
| is_weekend | bool | True if Saturday or Sunday |
| local_event | string | Festival/holiday name driving demand spike, or empty string |

---

## users.csv  (privacy-conscious)
| Column | Type | Description |
|--------|------|-------------|
| user_id | string | Unique identifier (USR-00001 … ) |
| city | string | City of user (city-level resolution only) |
| coarse_lat | float | City centroid ± ~15 km jitter — no precise location |
| coarse_lng | float | City centroid ± ~15 km jitter — no precise location |
| phone | string | Fake Indian mobile number: +91-XXXXXXXXXX (starts 6-9) |
| category_opt_ins | string | Pipe-separated list of opted-in categories |
| preferred_channel | string | SMS / WhatsApp / reply-YES |
| reliability_score | float | 0-1: historical claim-to-pickup completion ratio |
| price_sensitivity_threshold_pct | int | Minimum discount % that triggers user action |
| response_latency_minutes_avg | int | Avg minutes from notification to claim |

---

## claims.csv
| Column | Type | Description |
|--------|------|-------------|
| claim_id | string | Unique claim (CLM-0000001 … ) |
| user_id | string | FK → users.user_id |
| batch_id | string | FK → batches.batch_id |
| store_id | string | FK → stores.store_id |
| claimed_at | datetime | Timestamp of claim submission |
| channel_used | string | Channel via which claim was placed |
| discount_at_claim_pct | float | Discount depth at time of claim |
| fulfillment_type | string | pickup / delivery |
| completed | bool | Whether pickup/delivery was actually completed |
| completed_at | datetime | Completion timestamp (null if not completed) |

---

## ngo_standing_orders.csv
| Column | Type | Description |
|--------|------|-------------|
| ngo_id | string | Unique NGO identifier (NGO-001 … ) |
| ngo_name | string | Fictional Indian NGO / shelter name |
| city | string | City of operation |
| verified_status | string | verified / pending |
| category_priority | string | Pipe-separated list of preferred food categories |
| min_quantity_kg | int | Minimum batch size (kg) acceptable |
| priority_time_window_hours | int | Hours before expiry within which this NGO wants notification |
| delivery_or_pickup | string | pickup / delivery preference |

---

## category_shelf_life_curves.csv
| Column | Type | Description |
|--------|------|-------------|
| category | string | Food category |
| avg_shelf_life_days | float | Mean shelf life used by the generator |
| min_shelf_life_days | int | Shortest shelf life in category |
| max_shelf_life_days | int | Longest shelf life in category |
| elasticity_coefficient | float | Price elasticity magnitude (used in sales model) |
| b2b_eligible | bool | Whether category suits bulk B2B orders |

---

## co2e_conversion_factors.csv
| Column | Type | Description |
|--------|------|-------------|
| category | string | Food category |
| kg_co2e_avoided_per_kg_food | float | GHG emissions avoided per kg rescued (published reference constants) |
| source | string | Citation for the constant |
| notes | string | Clarification on India-specific vs. global applicability |

> **Note**: CO2e factors are published global scientific estimates (FAO 2011, USDA ERS). The pricing/currency layer in all other tables is India-specific (INR, Indian cities, Indian retail price ranges).
"""


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ORCHESTRATION
# ─────────────────────────────────────────────────────────────────────────────

def save(df: pd.DataFrame, directory: str, filename: str):
    path = os.path.join(directory, filename)
    df.to_csv(path, index=False)
    print(f"  [OK] {filename:35s}  {len(df):>8,} rows  ->  {path}")
    return path


def main():
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    print("=" * 65)
    print("  OptiMart Synthetic Dataset Generator - Indian Market Edition")
    print(f"  Seed: {SEED}  |  History: {SIM_START_DATE} -> {SIM_END_DATE}")
    print("=" * 65)

    # ── Step 1: Stores
    print("\n[1/10] Generating STORES ...")
    stores = generate_stores(NUM_STORES)
    save(stores, OUT_FULL, "stores.csv")

    # ── Step 2: Products / SKU catalog
    print("\n[2/10] Generating PRODUCTS ...")
    products = generate_products(NUM_SKUS)
    save(products, OUT_FULL, "products.csv")

    # ── Step 3: Inventory Batches
    print("\n[3/10] Generating BATCHES ...")
    batches = generate_batches(stores, products)
    save(batches, OUT_FULL, "batches.csv")

    # ── Step 4: Weather (needed before sales)
    print("\n[4/10] Generating WEATHER ...")
    weather_hist, weather_fc, city_weather = generate_weather(stores)
    save(weather_hist, OUT_FULL, "weather_history.csv")
    save(weather_fc,   OUT_FULL, "weather_forecast.csv")

    # ── Step 5: Sales History (core ML table)
    print("\n[5/10] Generating SALES HISTORY (this may take a moment) ...")
    sales = generate_sales_history(batches, products, weather_hist, city_weather, stores)
    save(sales, OUT_FULL, "sales_history.csv")

    # ── Step 6: Foot Traffic
    print("\n[6/10] Generating FOOT TRAFFIC ...")
    foot_traffic = generate_foot_traffic(stores)
    save(foot_traffic, OUT_FULL, "foot_traffic.csv")

    # ── Step 7: Users
    print("\n[7/10] Generating USERS ...")
    users = generate_users(stores, NUM_USERS)
    save(users, OUT_FULL, "users.csv")

    # ── Step 8: Claims
    print("\n[8/10] Generating CLAIMS ...")
    claims = generate_claims(users, batches, sales)
    save(claims, OUT_FULL, "claims.csv")

    # ── Step 9: NGO Standing Orders
    print("\n[9/10] Generating NGO STANDING ORDERS ...")
    ngo = generate_ngo_standing_orders(stores, NUM_NGOS)
    save(ngo, OUT_FULL, "ngo_standing_orders.csv")

    # ── Step 10: Reference / derived tables
    print("\n[10/10] Generating REFERENCE TABLES ...")
    shelf_curves = generate_shelf_life_curves()
    co2e_factors = generate_co2e_factors()
    save(shelf_curves, OUT_FULL, "category_shelf_life_curves.csv")
    save(co2e_factors, OUT_FULL, "co2e_conversion_factors.csv")

    # ── Data Dictionary
    dd_path = os.path.join(OUT_FULL, "data_dictionary.md")
    with open(dd_path, "w", encoding="utf-8") as f:
        f.write(DATA_DICTIONARY)
    print(f"\n  [OK] {'data_dictionary.md':35s}  ->  {dd_path}")

    # ── Demo Subset
    print(f"\n[DEMO] Carving demo subset: 1 store × {DEMO_NUM_SKUS} SKUs × {DEMO_DAYS} days ...")
    demo_tables = make_demo_subset(
        stores, products, batches, sales, weather_hist,
        foot_traffic, users, claims, ngo
    )
    for fname, ddf in demo_tables.items():
        save(ddf, OUT_DEMO, fname)
    # Copy reference tables into demo folder too
    save(shelf_curves, OUT_DEMO, "category_shelf_life_curves.csv")
    save(co2e_factors, OUT_DEMO, "co2e_conversion_factors.csv")
    dd_demo_path = os.path.join(OUT_DEMO, "data_dictionary.md")
    with open(dd_demo_path, "w", encoding="utf-8") as f:
        f.write(DATA_DICTIONARY)

    # ── Summary
    date_range_str = f"{SIM_START_DATE.isoformat()} to {SIM_END_DATE.isoformat()}"
    print("\n" + "=" * 65)
    print("  GENERATION COMPLETE — SUMMARY")
    print("=" * 65)
    print(f"  Date range covered:       {date_range_str}")
    print(f"  Stores:                   {len(stores):>8,}")
    print(f"  SKUs:                     {len(products):>8,}")
    print(f"  Inventory Batches:        {len(batches):>8,}")
    print(f"  Sales Records:            {len(sales):>8,}")
    print(f"  Weather Records:          {len(weather_hist):>8,}")
    print(f"  Weather Forecast Records: {len(weather_fc):>8,}")
    print(f"  Foot Traffic Records:     {len(foot_traffic):>8,}")
    print(f"  Users:                    {len(users):>8,}")
    print(f"  Claims:                   {len(claims):>8,}")
    print(f"  NGO Standing Orders:      {len(ngo):>8,}")
    print(f"  Categories in model:      {len(CATEGORY_SPEC):>8}")
    total_rows = (len(stores) + len(products) + len(batches) + len(sales) +
                  len(weather_hist) + len(weather_fc) + len(foot_traffic) +
                  len(users) + len(claims) + len(ngo))
    print(f"\n  Total rows across all tables: {total_rows:,}")
    print(f"\n  Full dataset  -> {OUT_FULL}/")
    print(f"  Demo subset   -> {OUT_DEMO}/")
    print("=" * 65)


if __name__ == "__main__":
    main()
