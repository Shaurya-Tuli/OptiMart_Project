"""
discount_engine.py — OptiMart Single Source of Truth for Dynamic Discount Calculation
=======================================================================================
Calculates discount percentages continuously based on normalized risk_score, 
hours_to_expiry, and product damage condition multipliers.

Guarantees:
- Smooth, monotonic, bounded discount curve.
- No hard cutoffs (e.g. days_to_expiry > 1 showing 0% discount).
- Product damage multiplier is applied multiplicatively and clamped to [MIN_DISCOUNT, MAX_DISCOUNT].
"""

from __future__ import annotations

from typing import Dict, Any, Optional

# ---------------------------------------------------------------------------
# Configurable Constants
# ---------------------------------------------------------------------------
MIN_DISCOUNT: float = 5.0      # Minimum discount % for items with any non-zero risk
MAX_DISCOUNT: float = 70.0     # Maximum allowable discount %
CURVE_EXPONENT: float = 1.2    # Ramping aggressiveness exponent (1.0 = linear, >1.0 = convex)

DAMAGE_MULTIPLIERS: Dict[str, float] = {
    "Excellent": 1.0,
    "Good": 1.05,
    "Fair": 1.15,
    "Poor": 1.35,
}


def compute_hours_to_expiry(days_to_expiry: float, hours_to_expiry: Optional[float] = None) -> float:
    """Standardize time-to-expiry representation in hours for all categories.
    
    If hours_to_expiry is explicitly provided (> 0), use it;
    otherwise convert days_to_expiry to hours (days_to_expiry * 24).
    """
    if hours_to_expiry is not None and hours_to_expiry >= 0:
        return float(hours_to_expiry)
    return max(0.0, float(days_to_expiry) * 24.0)


def calculate_discount(
    risk_score: float,
    product_condition: str = "Excellent",
    category: str = "Dairy",
    custom_min_discount: Optional[float] = None,
    custom_max_discount: Optional[float] = None,
    custom_exponent: Optional[float] = None,
) -> float:
    """Calculate dynamic discount percentage continuously from risk_score.
    
    Formula:
      1. risk_score = clamp(risk_score, 0.0, 1.0)
      2. If risk_score == 0.0: return 0.0 (no risk = no discount)
      3. base_discount = MIN_DISCOUNT + (MAX_DISCOUNT - MIN_DISCOUNT) * (risk_score ** CURVE_EXPONENT)
      4. damage_multiplier = DAMAGE_MULTIPLIERS.get(product_condition, 1.0)
      5. discount = base_discount * damage_multiplier
      6. Return clamp(discount, MIN_DISCOUNT, MAX_DISCOUNT) rounded to 2 decimal places.
    """
    min_d = custom_min_discount if custom_min_discount is not None else MIN_DISCOUNT
    max_d = custom_max_discount if custom_max_discount is not None else MAX_DISCOUNT
    exp = custom_exponent if custom_exponent is not None else CURVE_EXPONENT

    # Clamp risk score to [0, 1]
    r = max(0.0, min(1.0, float(risk_score)))
    if r <= 0.0:
        return 0.0

    # Smooth, monotonic base discount scaling
    base_discount = min_d + (max_d - min_d) * (r ** exp)

    # Damage multiplier
    damage_mult = DAMAGE_MULTIPLIERS.get(product_condition, 1.0)

    # Apply damage multiplier and clamp to bounds
    discount = base_discount * damage_mult
    clamped_discount = max(min_d, min(max_d, discount))

    return round(clamped_discount, 2)


if __name__ == "__main__":
    print("=== OptiMart Discount Engine Sanity Check ===")
    print(f"Constants: MIN_DISCOUNT={MIN_DISCOUNT}%, MAX_DISCOUNT={MAX_DISCOUNT}%, CURVE_EXPONENT={CURVE_EXPONENT}\n")
    
    spread = [0.0, 0.1, 0.3, 0.5, 0.7, 0.9, 1.0]
    conditions = ["Excellent", "Good", "Fair", "Poor"]
    
    print(f"{'Risk Score':<12} | " + " | ".join([f"{cond:<12}" for cond in conditions]))
    print("-" * 70)
    
    for r in spread:
        row_str = f"{r:<12.1f} | "
        cols = []
        for cond in conditions:
            d = calculate_discount(r, product_condition=cond)
            cols.append(f"{d:<12.2f}%")
        row_str += " | ".join(cols)
        print(row_str)
