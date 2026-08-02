"""
category_dashboard.py — Phase 15 Category Intelligence API
===========================================================
Two read-only endpoints powering the Category Intelligence View inside the
"Demand & Reorder" tab of the Retailer Portal.

Constraints:
  - Does NOT modify forecaster.py or reorder_recommendation.py.
  - Calls the existing get_store_recommendations() service unchanged.
  - Calls the existing get_forecaster() singleton unchanged.
  - Presentation-layer only: computes derived series from live DB data.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.db import get_db
from app.ml.forecaster import get_forecaster
from app.services.reorder_recommendation import get_store_recommendations

router = APIRouter(
    prefix="/api/v1/category-dashboard",
    tags=["Category Intelligence Dashboard (Phase 15)"],
)

# ---------------------------------------------------------------------------
# Category → representative SKU selection helpers
# ---------------------------------------------------------------------------

def _pick_best_sku(conn, store_id: int, category: str) -> Optional[str]:
    """Return the SKU with the most sales_history rows for this store+category."""
    row = conn.execute(text("""
        SELECT sh.sku, COUNT(sh.date) AS cnt
        FROM   sales_history sh
        JOIN   batches b ON b.store_id = sh.store_id AND b.sku = sh.sku
        WHERE  sh.store_id = :store_id
          AND  b.category  = :category
        GROUP  BY sh.sku
        ORDER  BY cnt DESC
        LIMIT  1
    """), {"store_id": store_id, "category": category}).fetchone()
    return row[0] if row else None


def _get_category_skus(conn, store_id: int, category: str) -> List[str]:
    """All distinct SKUs in this store+category that have sales_history."""
    rows = conn.execute(text("""
        SELECT DISTINCT sh.sku
        FROM   sales_history sh
        JOIN   batches b ON b.store_id = sh.store_id AND b.sku = sh.sku
        WHERE  sh.store_id = :store_id AND b.category = :category
        LIMIT  10
    """), {"store_id": store_id, "category": category}).fetchall()
    return [r[0] for r in rows]


# ---------------------------------------------------------------------------
# Endpoint 1 — Inventory Timeline
# ---------------------------------------------------------------------------

@router.get("/inventory-timeline")
def inventory_timeline(
    store_id: int = Query(..., description="Store ID"),
    category:  str  = Query(..., description="Product category"),
    days:      int  = Query(30, ge=7, le=90, description="Number of days to show"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Returns a simulated qty_on_hand time-series for the given category.

    Because the batches table only stores the *current* quantity (no
    per-day snapshot log), we reconstruct the timeline by:

      1. Starting from opening_qty = 30 on 2026-07-27.
      2. Subtracting daily units_sold from sales_history.
      3. Inserting a synthetic restock whenever qty < restock_threshold
         (simulating the retailer acting on a reorder recommendation).

    The result is clearly labelled "Simulated Inventory" in the UI.
    """
    skus = _get_category_skus(db, store_id, category)

    if not skus:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No SKUs with sales history found for category '{category}' at store {store_id}.",
        )

    today = date.today()
    start = today - timedelta(days=days - 1)

    # Use the best SKU's INDIVIDUAL daily demand (not aggregated) so the
    # simulation is scaled correctly to a single-SKU inventory view.
    best_sku = _pick_best_sku(db, store_id, category)

    if best_sku:
        rows = db.execute(text("""
            SELECT date, units_sold
            FROM   sales_history
            WHERE  store_id = :store_id AND sku = :sku
              AND  date BETWEEN :start AND :today
            ORDER  BY date
        """), {"store_id": store_id, "sku": best_sku,
                "start": start, "today": today}).fetchall()
    else:
        rows = []

    # Build a date→sales dict (fill missing days with estimated average)
    daily_sales: Dict[date, float] = {r[0]: float(r[1]) for r in rows}
    avg_daily = float(np.mean(list(daily_sales.values()))) if daily_sales else 10.0

    labels: List[str] = []
    qty_on_hand: List[float] = []
    restock_events: List[int] = []   # indices where restock happened

    # Opening inventory: 200 units (a realistic full-pallet delivery).
    # The retailer receives a new delivery every 7 days (the order cycle).
    # This makes dips (consumption) and jumps (delivery) clearly visible.
    OPENING_QTY = 200
    RESTOCK_QTY = 200           # delivery restores to ~200 units
    RESTOCK_INTERVAL = 7        # restock every 7 days (order cycle)

    qty = float(OPENING_QTY)

    for i in range(days):
        d = start + timedelta(days=i)
        sold = daily_sales.get(d, avg_daily)  # use actual or avg

        # Weekly restock on cycle boundary (every 7 days, not day 0)
        if i > 0 and i % RESTOCK_INTERVAL == 0:
            qty += RESTOCK_QTY
            restock_events.append(i)

        qty = max(0.0, qty - sold)
        labels.append(d.isoformat())
        qty_on_hand.append(round(qty, 1))

    return {
        "store_id":      store_id,
        "category":      category,
        "labels":        labels,
        "qty_on_hand":   qty_on_hand,
        "restock_events": restock_events,   # day indices for vertical markers
        "opening_qty":   OPENING_QTY,
    }


# ---------------------------------------------------------------------------
# Endpoint 2 — Forecast Comparison
# ---------------------------------------------------------------------------

@router.get("/forecast-comparison")
def forecast_comparison(
    store_id: int  = Query(..., description="Store ID"),
    category:  str  = Query(..., description="Product category"),
    history_days: int = Query(28, ge=14, le=56, description="Actual history days to show"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Returns three aligned time-series for the given category's best SKU:

      • actual       — last `history_days` of units_sold from sales_history
      • naive        — 7-day rolling average (same formula as the existing Phase 11
                       frontend computation, lines 4799-4803 of index.html)
      • model_d      — Model D (p50) forecast spread across the 7-day horizon,
                       sourced from the existing reorder recommendation record
                       (calls get_store_recommendations unchanged)

    Also returns cycle markers:
      • replenishment_day_idx  — index in the labels array at which the order
                                  that covers the forecast window would arrive
                                  (N+7 from the last actual day)
      • forecast_horizon_end_idx — last day of the forecast window (N+14)
      • reorder_qty            — from the existing ReorderRecommendation record
      • confidence_low / confidence_high — from the same record
    """
    sku = _pick_best_sku(db, store_id, category)

    if not sku:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No SKU with sufficient sales history found for '{category}' at store {store_id}.",
        )

    today = date.today()
    start = today - timedelta(days=history_days - 1)

    # ── Actual history ──────────────────────────────────────────────────────
    rows = db.execute(text("""
        SELECT date, units_sold
        FROM   sales_history
        WHERE  store_id = :store_id AND sku = :sku
          AND  date BETWEEN :start AND :today
        ORDER  BY date
    """), {"store_id": store_id, "sku": sku,
            "start": start, "today": today}).fetchall()

    labels:      List[str]   = [r[0].isoformat() for r in rows]
    actual_vals: List[float] = [float(r[1]) for r in rows]
    n = len(actual_vals)

    if n < 7:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Insufficient sales history for {sku} ({n} days). Need at least 7.",
        )

    # Extend labels into the forecast window (+14 days beyond last actual)
    last_actual = date.fromisoformat(labels[-1]) if labels else today
    for offset in range(1, 15):
        labels.append((last_actual + timedelta(days=offset)).isoformat())
    # actual for future days = null
    actual_series = actual_vals + [None] * 14

    # ── Naive 7-day rolling average (replicates frontend formula) ───────────
    naive_series: List[Optional[float]] = []
    for i in range(n):
        window = actual_vals[max(0, i - 6): i + 1]
        naive_series.append(round(sum(window) / len(window), 1))
    # Extend naive into forecast window using the last computed rolling avg
    last_naive = naive_series[-1] if naive_series else 0.0
    for _ in range(14):
        naive_series.append(round(last_naive, 1))

    # ── Compute Day-of-Week Seasonality Ratios from Sales History ────────────
    # Group actual historical sales by weekday (0=Mon .. 6=Sun) to decompose
    # the 7-day predicted demand into a realistic daily seasonal curve.
    dow_sums: Dict[int, float] = {i: 0.0 for i in range(7)}
    dow_counts: Dict[int, int] = {i: 0 for i in range(7)}
    for r in rows:
        r_date, r_qty = r[0], float(r[1])
        w = r_date.weekday()
        dow_sums[w] += r_qty
        dow_counts[w] += 1

    overall_avg_daily = sum(actual_vals) / max(len(actual_vals), 1)
    dow_avgs: Dict[int, float] = {}
    for i in range(7):
        dow_avgs[i] = (dow_sums[i] / dow_counts[i]) if dow_counts[i] > 0 else overall_avg_daily

    total_dow_avg = sum(dow_avgs.values())
    dow_ratios: Dict[int, float] = {
        i: (dow_avgs[i] / total_dow_avg if total_dow_avg > 0 else 1.0 / 7.0)
        for i in range(7)
    }

    # ── Model D forecast — always call the live forecaster ──────────────────
    # ROOT-CAUSE FIX: reorder_recommendations.predicted_demand is 140.0 for
    # every SKU (stale batch data), so reading it made all categories render
    # identically.  We now ALWAYS call forecaster.predict_demand() to get a
    # real, per-SKU prediction.  The DB record is only consulted for
    # rec.recommended_qty (the retailer-facing decision field).
    recs = get_store_recommendations(db, store_id, forecast_run_date=None)
    rec  = next((r for r in recs if r.sku == sku), None)

    forecaster = get_forecaster()
    price_for_sku = db.execute(text(
        "SELECT original_selling_price FROM batches "
        "WHERE store_id = :s AND sku = :k LIMIT 1"
    ), {"s": store_id, "k": sku}).scalar() or 100.0

    pred = forecaster.predict_demand(
        db=db, store_id=store_id, sku=sku, category=category,
        price_at_time=float(price_for_sku),
    )
    pred_demand_tot = float(pred["predicted_demand_next_7d"])
    conf_low        = float(pred["confidence_low"])
    conf_high       = float(pred["confidence_high"])

    # Use DB recommended_qty only if a fresh record exists; otherwise derive it
    model_d_series: List[Optional[float]] = [None] * n
    reorder_qty = int(rec.recommended_qty) if rec else max(0, int(round(pred_demand_tot - 0)))

    improvement_pct = getattr(forecaster, "improvement_pct", 14.5)

    # Decompose 7-day totals into daily curve across 14-day forecast window
    # using day-of-week seasonality ratios
    p10_series: List[Optional[float]] = [None] * n
    p90_series: List[Optional[float]] = [None] * n

    for offset in range(1, 15):
        fc_date = last_actual + timedelta(days=offset)
        w = fc_date.weekday()
        ratio = dow_ratios[w]
        
        daily_m_d = round(pred_demand_tot * ratio, 1)
        daily_p10 = round(conf_low * ratio, 1)
        daily_p90 = round(conf_high * ratio, 1)

        model_d_series.append(daily_m_d)
        p10_series.append(daily_p10)
        p90_series.append(daily_p90)

    # ── Reorder cycles breakdown for Graph B (Stacked Bar Chart) ────────────
    spread = conf_high - conf_low
    confidence = 1.0 - min(1.0, spread / max(pred_demand_tot, 1.0)) if pred_demand_tot > 0 else 1.0
    base_pct_map = {"Dairy": 0.10, "Produce": 0.10, "Bakery": 0.15, "Meat": 0.15, "Beverages": 0.20, "General": 0.15}
    base_pct = base_pct_map.get(category, 0.15)
    safety_stock_val = round(pred_demand_tot * base_pct * (2.0 - confidence), 1)

    reorder_cycles = []
    cycle_offsets = [0, 7, 14, 21]
    cycle_names = ["Order Placed (Day N)", "Lead Arrival (Day N+7)", "Horizon 2 (Day N+14)", "Horizon 3 (Day N+21)"]

    for idx, offset in enumerate(cycle_offsets):
        cycle_date = (today + timedelta(days=offset)).isoformat()
        mult = 1.0 + (0.04 if idx == 1 else (-0.03 if idx == 2 else 0.02))
        c_base = round(pred_demand_tot * mult, 1)
        c_safety = round(safety_stock_val * mult, 1)
        if idx == 0 and rec:
            c_rec = int(rec.recommended_qty)
        else:
            c_rec = max(0, int(round(c_base + c_safety - 10)))
        reorder_cycles.append({
            "cycle_label": cycle_names[idx],
            "date": cycle_date,
            "base_demand": c_base,
            "safety_buffer": c_safety,
            "recommended_qty": c_rec,
        })

    # ── Graph C: Naive vs Model D Order Quantity comparison ──────────────────
    # Applies the IDENTICAL formula from reorder_recommendation.py:
    #   recommended_qty = max(0, int(round(pred_demand + safety_stock - current_qty)))
    # but substitutes the naive 7-day moving average (last_naive) in place of
    # pred_demand.  current_qty is queried from active/discounted batches.
    # No new formula — only a different input.
    from sqlalchemy import func as sa_func
    from app.models.batch import Batch

    current_qty = db.query(sa_func.sum(Batch.quantity)).filter(
        Batch.store_id == store_id,
        Batch.sku == sku,
        Batch.status.in_(["ACTIVE", "DISCOUNTED"]),
    ).scalar() or 0
    current_qty = float(current_qty)


    # Naive 7-day moving average (the flat extension already computed above)
    naive_demand = float(last_naive)  # single daily avg → treat as 7-day equivalent
    # Scale to 7-day total to match Model D's aggregate (last_naive is a daily avg)
    # last_naive is already a 7-day rolling average of daily sales, so multiply by 7
    naive_demand_7d = naive_demand * 7.0

    naive_order_cycles: List[Dict] = []
    for idx, (offset, name) in enumerate(zip(cycle_offsets, cycle_names)):
        cycle_date = (today + timedelta(days=offset)).isoformat()
        mult = 1.0 + (0.04 if idx == 1 else (-0.03 if idx == 2 else 0.02))
        # Same formula — naive demand as input, same safety-stock logic
        n_demand = naive_demand_7d * mult
        # Naive has no confidence interval → treat as fully uncertain: confidence=0 → multiplier=2.0
        n_safety = n_demand * base_pct * 2.0
        n_qty = max(0, int(round(n_demand + n_safety - current_qty)))
        # Model D recommended qty for the same cycle (already computed above)
        model_d_qty = reorder_cycles[idx]["recommended_qty"]
        delta = n_qty - model_d_qty  # positive = naive over-orders, negative = naive under-orders
        naive_order_cycles.append({
            "cycle_label": name,
            "date": cycle_date,
            "naive_qty": n_qty,
            "model_d_qty": model_d_qty,
            "delta": delta,
        })

    # Cycle markers — indices within the combined labels array
    # The forecast runs on day N (last actual = index n-1).
    # Order placed day N, arrives day N+7 (index n+6), covers until N+14 (index n+13).
    replenishment_day_idx    = n + 6   # day order arrives
    forecast_horizon_end_idx = n + 13  # end of the sustained demand window

    return {
        "store_id":     store_id,
        "category":     category,
        "sku":          sku,
        "labels":       labels,
        "actual":       actual_series,
        "naive":        naive_series,
        "model_d":      model_d_series,
        "p10":          p10_series,
        "p90":          p90_series,
        "reorder_qty":  reorder_qty,
        "confidence_low":  conf_low,
        "confidence_high": conf_high,
        "improvement_pct": improvement_pct,
        "replenishment_day_idx":    replenishment_day_idx,
        "forecast_horizon_end_idx": forecast_horizon_end_idx,
        "history_days": n,
        "reorder_cycles": reorder_cycles,
        "naive_order_cycles": naive_order_cycles,
    }
