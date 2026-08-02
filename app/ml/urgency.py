"""
urgency.py — OptiMart Model A
=============================
Category-relative urgency normalization.

The core insight: raw days_to_expiry is meaningless without category context.
2 days left is a crisis for Dairy but barely noticeable for Food Grains.

This module provides `compute_urgency()` which normalizes time-to-expiry into
a [0, 1] urgency score using a per-category baseline from category_shelf_life.json.

Curve types:
  - linear_convex  : perishables (Dairy, Bakery, Meat, Produce) — urgency rises
                     from ~0 at purchase, accelerating in the final window.
  - sigmoid        : long-shelf items (Pantry, Perfume, Frozen) — stays near 0
                     until the final 5–10% of shelf life, then rises sharply.

Usage:
    from app.ml.urgency import compute_urgency, load_shelf_life_lookup
    lookup = load_shelf_life_lookup()
    score = compute_urgency(days_to_expiry=2, category="Dairy", lookup=lookup)
    # => ~0.87

Run tests directly:
    python -m pytest app/ml/urgency.py -v
    # or:
    python app/ml/urgency.py
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


# ---------------------------------------------------------------------------
# Config path — relative to this file so it works in Docker + local
# ---------------------------------------------------------------------------
_DEFAULT_CONFIG_PATH = Path(__file__).parent / "category_shelf_life.json"


def load_shelf_life_lookup(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load the category shelf-life lookup table from JSON.

    Args:
        config_path: Override path to category_shelf_life.json.
                     Defaults to the sibling file in app/ml/.

    Returns:
        dict with category entries and a _default_fallback entry.
    """
    path = Path(config_path) if config_path else _DEFAULT_CONFIG_PATH
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return raw


def _sigmoid_urgency(
    days_to_expiry: float,
    shelf_life: float,
    steepness: float,
    inflection_fraction: float,
) -> float:
    """Sigmoid urgency curve for long-shelf-life categories.

    Stays near 0 until the product approaches the inflection_fraction point of
    its shelf life, then rises sharply. Designed so urgency is near-irrelevant
    for most of the shelf life and only spikes in the final window.

    Args:
        days_to_expiry: Days remaining until expiry (>= 0).
        shelf_life: Typical shelf life in days for this category.
        steepness: Sigmoid steepness (k). Higher = sharper spike.
        inflection_fraction: Fraction of shelf life at which urgency hits 0.5.
                             e.g. 0.95 means urgency=0.5 when 5% of life remains.

    Returns:
        Urgency score in [0, 1].
    """
    # Convert days_to_expiry into "fraction of shelf life remaining"
    frac_remaining = max(0.0, min(1.0, days_to_expiry / shelf_life))
    # We want urgency to be HIGH when frac_remaining is LOW.
    # Inflection at frac_remaining == (1 - inflection_fraction).
    inflection = 1.0 - inflection_fraction  # e.g. 0.05 for inflection_fraction=0.95
    # Standard logistic: 1 / (1 + exp(k * (x - inflection)))
    # where x = frac_remaining. When x < inflection => urgency approaches 1.
    urgency = 1.0 / (1.0 + math.exp(steepness * (frac_remaining - inflection)))
    return float(urgency)


def _linear_convex_urgency(
    days_to_expiry: float,
    shelf_life: float,
    convex_power: float,
) -> float:
    """Linear-to-convex urgency curve for short-shelf perishables.

    Urgency rises from near 0 at purchase, accelerating toward expiry.
    A power > 1 creates a convex shape — urgency accelerates in the final days.

    Args:
        days_to_expiry: Days remaining until expiry (>= 0).
        shelf_life: Typical shelf life in days for this category.
        convex_power: Exponent for the convex bend. 1.0 = linear, 1.5 = strongly convex.

    Returns:
        Urgency score in [0, 1].
    """
    frac_remaining = max(0.0, min(1.0, days_to_expiry / shelf_life))
    # frac_elapsed = 1 - frac_remaining.  Apply convex power to elapsed fraction.
    urgency = (1.0 - frac_remaining) ** convex_power
    # Re-normalize so urgency is truly [0, 1] given power distortion.
    # At frac_remaining=0 (expired), urgency = 1.0^power = 1.0. Good.
    # At frac_remaining=1 (just stocked), urgency = 0.0. Good.
    return float(urgency)


def compute_urgency(
    days_to_expiry: float,
    category: str,
    lookup: Dict[str, Any],
    hours_to_expiry: Optional[float] = None,
) -> Tuple[float, bool]:
    """Compute a normalized urgency score in [0, 1] for a given batch.

    This is the PRIMARY time signal fed to the pricing model.
    It replaces raw days_to_expiry so the model learns category-relative urgency
    rather than a meaningless absolute number.

    Args:
        days_to_expiry: Days remaining until expiry. Must be >= 0.
        category: Product category string.
        lookup: The loaded shelf-life config dict.
        hours_to_expiry: Optional hours remaining until expiry (if provided, takes precedence).

    Returns:
        Tuple of:
          - urgency_score: float in [0.0, 1.0]
          - is_invalid: bool. True if days_to_expiry > shelf_life (impossible input
                        or data error). Caller should log/flag this.

    Examples:
        >>> lookup = load_shelf_life_lookup()
        >>> compute_urgency(2, "Dairy", lookup)
        (0.87..., False)   # milk at 2 days left => high urgency
        >>> compute_urgency(60, "Perfume & Cosmetics", lookup)
        (0.00..., False)   # perfume at 60 days left => near-zero urgency
        >>> compute_urgency(60, "Dairy", lookup)
        (1.0, True)        # milk at 60 days is impossible => flagged as invalid
    """
    if hours_to_expiry is not None and hours_to_expiry >= 0:
        days_to_expiry = hours_to_expiry / 24.0

    categories = lookup.get("categories", {})
    cat_config = categories.get(category)

    # Unknown category → fall back to default
    if cat_config is None:
        cat_config = lookup["_default_fallback"]
        is_fallback = True
    else:
        is_fallback = False

    shelf_life = float(cat_config["typical_shelf_life_days"])

    # Validate input: days_to_expiry cannot meaningfully exceed shelf_life
    # for a category (e.g. milk can't have 60 days left).
    is_invalid = days_to_expiry > shelf_life

    # Clamp negative days (already expired) → urgency = 1.0
    clamped_days = max(0.0, days_to_expiry)

    curve = cat_config.get("urgency_curve", "sigmoid")

    if curve == "linear_convex":
        power = float(cat_config.get("convex_power", 1.3))
        raw_urgency = _linear_convex_urgency(clamped_days, shelf_life, power)
    else:  # sigmoid (default for long-shelf categories)
        steepness = float(cat_config.get("sigmoid_steepness", 10.0))
        inflection_fraction = float(cat_config.get("sigmoid_inflection_fraction", 0.90))
        raw_urgency = _sigmoid_urgency(clamped_days, shelf_life, steepness, inflection_fraction)

    urgency_score = float(max(0.0, min(1.0, raw_urgency)))

    # For impossible inputs (days > shelf life), clamp to 1.0 and flag as invalid
    if is_invalid:
        urgency_score = 1.0

    return urgency_score, is_invalid


# ---------------------------------------------------------------------------
# Module-level singleton lookup (populated lazily so import is free)
# ---------------------------------------------------------------------------
_LOOKUP: Optional[Dict[str, Any]] = None


def get_lookup() -> Dict[str, Any]:
    """Return the module-level cached shelf-life lookup."""
    global _LOOKUP
    if _LOOKUP is None:
        _LOOKUP = load_shelf_life_lookup()
    return _LOOKUP


# ---------------------------------------------------------------------------
# Unit tests (pytest-compatible; also runnable as __main__)
# ---------------------------------------------------------------------------

def _run_tests() -> None:
    """Run all unit tests. Called when the module is executed directly."""
    import sys

    errors = []

    def assert_close(label: str, val: float, expected: float, tol: float = 0.05) -> None:
        if abs(val - expected) > tol:
            errors.append(f"FAIL [{label}]: got {val:.4f}, expected ~{expected:.4f} ±{tol}")
        else:
            print(f"  PASS [{label}]: {val:.4f}")

    def assert_true(label: str, cond: bool) -> None:
        if not cond:
            errors.append(f"FAIL [{label}]: condition was False")
        else:
            print(f"  PASS [{label}]")

    lookup = load_shelf_life_lookup()
    print("\n=== OptiMart urgency.py unit tests ===\n")

    # -----------------------------------------------------------------------
    # Test 1 — Perfume at 60 days left: urgency should be near 0
    # Perfume typical shelf life = 900 days. 60 days left = 93.3% of life consumed.
    # Inflection at 95% consumed (5% remaining = 45 days). 60 days > 45 days,
    # so we're not yet at the critical spike point → should be < 0.15
    # -----------------------------------------------------------------------
    print("Test 1 — Perfume & Cosmetics at 60 days remaining (near-zero urgency expected):")
    score, invalid = compute_urgency(60, "Perfume & Cosmetics", lookup)
    assert_close("perfume 60d urgency", score, 0.0, tol=0.15)
    assert_true("perfume 60d not invalid", not invalid)

    # -----------------------------------------------------------------------
    # Test 2 — Perfume at 30 days left: urgency rising but still low-moderate
    # 30 days left on a 900-day life = 96.7% consumed. Past the inflection.
    # Should be in the 0.4 - 0.85 range (sigmoid is steep here).
    # -----------------------------------------------------------------------
    print("Test 2 — Perfume & Cosmetics at 30 days remaining (sigmoid rising):")
    score, invalid = compute_urgency(30, "Perfume & Cosmetics", lookup)
    assert_true("perfume 30d urgency > 0.2", score > 0.2)
    assert_true("perfume 30d not invalid", not invalid)

    # -----------------------------------------------------------------------
    # Test 3 — Milk at 60 days left: IMPOSSIBLE / invalid input
    # Dairy shelf life = 12 days. 60 days is physically impossible.
    # Should return urgency=1.0 and is_invalid=True.
    # -----------------------------------------------------------------------
    print("Test 3 — Dairy (Milk) at 60 days remaining (impossible — should be flagged invalid):")
    score, invalid = compute_urgency(60, "Dairy", lookup)
    assert_close("milk 60d urgency clamped to 1.0", score, 1.0, tol=0.001)
    assert_true("milk 60d is_invalid=True", invalid)

    # -----------------------------------------------------------------------
    # Test 4 — Milk at 2 days left: HIGH urgency (>0.8)
    # Dairy shelf life = 12 days. 2 days left = ~83% consumed.
    # Linear-convex with power=1.3. frac_remaining=2/12=0.167 → urgency≈0.86
    # -----------------------------------------------------------------------
    print("Test 4 — Dairy (Milk) at 2 days remaining (HIGH urgency > 0.8 expected):")
    score, invalid = compute_urgency(2, "Dairy", lookup)
    assert_true("milk 2d urgency > 0.80", score > 0.80)
    assert_true("milk 2d not invalid", not invalid)

    # -----------------------------------------------------------------------
    # Test 5 — Dairy at 0 days (expired): urgency = 1.0
    # -----------------------------------------------------------------------
    print("Test 5 — Dairy at 0 days (expired):")
    score, invalid = compute_urgency(0, "Dairy", lookup)
    assert_close("dairy 0d urgency = 1.0", score, 1.0, tol=0.001)
    assert_true("dairy 0d not invalid (0 is a valid edge)", not invalid)

    # -----------------------------------------------------------------------
    # Test 6 — Bakery at 1 day left: CRITICAL urgency
    # Shelf life = 4 days. 1 day left = 75% consumed.
    # -----------------------------------------------------------------------
    print("Test 6 — Bakery at 1 day remaining (CRITICAL urgency > 0.7):")
    score, invalid = compute_urgency(1, "Bakery", lookup)
    assert_true("bakery 1d urgency > 0.70", score > 0.70)
    assert_true("bakery 1d not invalid", not invalid)

    # -----------------------------------------------------------------------
    # Test 7 — Food Grains at 270 days left (full shelf life): near-zero urgency
    # -----------------------------------------------------------------------
    print("Test 7 — Food Grains at 270 days (brand new, near-zero urgency):")
    score, invalid = compute_urgency(270, "Food Grains", lookup)
    assert_close("food grains 270d urgency ≈ 0", score, 0.0, tol=0.05)
    assert_true("food grains 270d not invalid", not invalid)

    # -----------------------------------------------------------------------
    # Test 8 — Unknown category uses fallback (no crash)
    # -----------------------------------------------------------------------
    print("Test 8 — Unknown category falls back to default (no crash):")
    score, invalid = compute_urgency(10, "Unicorn Dust", lookup)
    assert_true("unknown category score in [0,1]", 0.0 <= score <= 1.0)
    print(f"  fallback score: {score:.4f}")

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    print("\n" + "=" * 40)
    if errors:
        print(f"FAILURES ({len(errors)}):")
        for e in errors:
            print(f"  {e}")
        sys.exit(1)
    else:
        print(f"All tests passed.")


# pytest hooks — functions prefixed test_ are collected automatically
def test_perfume_near_zero_urgency():
    lookup = load_shelf_life_lookup()
    score, invalid = compute_urgency(60, "Perfume & Cosmetics", lookup)
    assert score < 0.15, f"Expected near-zero urgency for perfume at 60d, got {score}"
    assert not invalid


def test_milk_impossible_input_flagged():
    lookup = load_shelf_life_lookup()
    score, invalid = compute_urgency(60, "Dairy", lookup)
    assert invalid, "Milk at 60 days should be flagged as invalid input"
    assert score == 1.0, "Invalid input should clamp to urgency=1.0"


def test_milk_2d_high_urgency():
    lookup = load_shelf_life_lookup()
    score, invalid = compute_urgency(2, "Dairy", lookup)
    assert score > 0.80, f"Expected urgency > 0.80 for milk at 2 days, got {score}"
    assert not invalid


def test_expired_item_urgency_one():
    lookup = load_shelf_life_lookup()
    score, _ = compute_urgency(0, "Dairy", lookup)
    assert abs(score - 1.0) < 0.001


def test_bakery_critical():
    lookup = load_shelf_life_lookup()
    score, invalid = compute_urgency(1, "Bakery", lookup)
    assert score > 0.70
    assert not invalid


def test_grains_new_stock_near_zero():
    lookup = load_shelf_life_lookup()
    score, invalid = compute_urgency(270, "Food Grains", lookup)
    assert score < 0.05
    assert not invalid


def test_unknown_category_no_crash():
    lookup = load_shelf_life_lookup()
    score, _ = compute_urgency(10, "Unicorn Dust", lookup)
    assert 0.0 <= score <= 1.0


if __name__ == "__main__":
    _run_tests()
