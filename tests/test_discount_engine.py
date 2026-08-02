import pytest
from app.ml.discount_engine import (
    calculate_discount,
    compute_hours_to_expiry,
    MIN_DISCOUNT,
    MAX_DISCOUNT,
    CURVE_EXPONENT,
    DAMAGE_MULTIPLIERS,
)


def test_compute_hours_to_expiry():
    # Day conversion
    assert compute_hours_to_expiry(days_to_expiry=2.0) == 48.0
    # Explicit hours precedence
    assert compute_hours_to_expiry(days_to_expiry=2.0, hours_to_expiry=36.0) == 36.0
    # Zero/negative clamp
    assert compute_hours_to_expiry(days_to_expiry=-1.0) == 0.0


def test_calculate_discount_zero_risk():
    assert calculate_discount(risk_score=0.0) == 0.0


def test_calculate_discount_smooth_monotonic_scaling():
    spread = [0.1, 0.3, 0.5, 0.7, 0.9, 1.0]
    discounts = [calculate_discount(risk_score=r) for r in spread]
    
    # Check monotonicity
    for i in range(len(discounts) - 1):
        assert discounts[i] <= discounts[i + 1]
    
    # Check bounds
    assert discounts[0] >= MIN_DISCOUNT
    assert discounts[-1] <= MAX_DISCOUNT


def test_calculate_discount_damage_multiplier():
    r = 0.5
    d_excellent = calculate_discount(risk_score=r, product_condition="Excellent")
    d_good = calculate_discount(risk_score=r, product_condition="Good")
    d_fair = calculate_discount(risk_score=r, product_condition="Fair")
    d_poor = calculate_discount(risk_score=r, product_condition="Poor")

    assert d_excellent < d_good < d_fair < d_poor
    # Check clamping to MAX_DISCOUNT
    assert d_poor <= MAX_DISCOUNT


def test_no_hard_cutoff_above_one_day():
    # Dairy 30 hours (1.25 days) vs 20 hours (0.83 days)
    d_30h = calculate_discount(risk_score=0.45)
    d_20h = calculate_discount(risk_score=0.65)

    assert d_30h > 0.0, "Item > 1 day to expiry should still receive a non-zero discount if at risk"
    assert d_20h > d_30h
