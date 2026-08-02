# OptiMart Synthetic Dataset — Data Dictionary

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
