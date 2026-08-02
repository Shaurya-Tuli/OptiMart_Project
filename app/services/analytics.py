"""Analytics service aggregating waste reduction, CO2 offset, financial recovery, and NGO allocations."""
from typing import Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.batch import Batch
from app.models.claim import Claim
from app.models.store import Store
from app.models.standing_order import StandingOrder
from app.models.standing_order_match import StandingOrderMatch


KG_WASTE_PER_ITEM = 0.5   # Estimated 0.5 kg waste prevented per item rescued
KG_CO2_PER_KG_WASTE = 2.5 # Estimated 2.5 kg CO2e saved per kg food waste prevented


def get_analytics_summary(db: Session) -> Dict[str, Any]:
    """Calculates platform-wide waste impact, financial recovery, NGO allocations, and conversion rates."""
    total_batches = db.query(func.count(Batch.id)).scalar() or 0

    # Rescued claims (status IN 'PAID', 'FULFILLED')
    rescued_claims = (
        db.query(Claim)
        .filter(Claim.status.in_(["PAID", "FULFILLED"]))
        .all()
    )

    items_rescued = sum(c.reserved_quantity for c in rescued_claims)
    waste_prevented_kg = round(items_rescued * KG_WASTE_PER_ITEM, 2)
    co2_saved_kg = round(waste_prevented_kg * KG_CO2_PER_KG_WASTE, 2)

    # Financial impact calculation
    total_revenue_recovered = 0.0
    total_discounts_given = 0.0

    for claim in rescued_claims:
        batch = db.query(Batch).filter(Batch.id == claim.batch_id).first()
        if batch:
            revenue = batch.current_price * claim.reserved_quantity
            original_value = batch.original_selling_price * claim.reserved_quantity
            total_revenue_recovered += revenue
            total_discounts_given += max(0.0, original_value - revenue)

    # Average discount percentage across all batches
    avg_discount = db.query(func.avg(Batch.discount_percentage)).scalar() or 0.0

    # Standing orders & NGO metrics
    total_standing_orders = db.query(func.count(StandingOrder.id)).scalar() or 0
    total_ngo_matches = db.query(func.count(StandingOrderMatch.id)).scalar() or 0
    total_subsidized_items = (
        db.query(func.sum(StandingOrderMatch.allocated_quantity)).scalar() or 0
    )

    # Category breakdown
    category_counts = {}
    cat_rows = (
        db.query(Batch.category, func.count(Batch.id))
        .group_by(Batch.category)
        .all()
    )
    for cat, count in cat_rows:
        category_counts[cat] = count

    # Conversion rate: ratio of claims that converted to PAID/FULFILLED vs total claims created
    total_claims_created = db.query(func.count(Claim.id)).scalar() or 0
    successful_claims_count = len(rescued_claims)

    conversion_rate = (
        round((successful_claims_count / total_claims_created) * 100, 2)
        if total_claims_created > 0
        else 0.0
    )

    return {
        "waste_impact": {
            "total_batches_tracked": total_batches,
            "total_items_rescued": items_rescued,
            "total_waste_prevented_kg": waste_prevented_kg,
            "total_co2_saved_kg": co2_saved_kg,
        },
        "financial_impact": {
            "total_revenue_recovered": round(total_revenue_recovered, 2),
            "total_discounts_given": round(total_discounts_given, 2),
            "average_discount_percentage": round(float(avg_discount), 2),
        },
        "standing_orders": {
            "total_standing_orders": total_standing_orders,
            "total_ngo_matches": total_ngo_matches,
            "total_subsidized_items_allocated": int(total_subsidized_items),
        },
        "category_breakdown": category_counts,
        "claim_conversion_rate_percentage": conversion_rate,
    }


def get_store_analytics(db: Session, store_id: int) -> Dict[str, Any]:
    """Calculates store-specific analytics."""
    store = db.query(Store).filter(Store.id == store_id).first()
    if not store:
        return {}

    active_count = (
        db.query(func.count(Batch.id))
        .filter(Batch.store_id == store_id, Batch.status.in_(["ACTIVE", "DISCOUNTED"]))
        .scalar()
        or 0
    )

    expired_count = (
        db.query(func.count(Batch.id))
        .filter(Batch.store_id == store_id, Batch.status == "EXPIRED")
        .scalar()
        or 0
    )

    rescued_count = (
        db.query(func.count(Batch.id))
        .filter(Batch.store_id == store_id, Batch.status == "RESCUED")
        .scalar()
        or 0
    )

    store_claims = (
        db.query(Claim)
        .join(Batch, Claim.batch_id == Batch.id)
        .filter(Batch.store_id == store_id, Claim.status.in_(["PAID", "FULFILLED"]))
        .all()
    )

    items_rescued = sum(c.reserved_quantity for c in store_claims)
    revenue = 0.0

    for c in store_claims:
        b = db.query(Batch).filter(Batch.id == c.batch_id).first()
        if b:
            revenue += b.current_price * c.reserved_quantity

    return {
        "store_id": store.id,
        "store_name": store.name,
        "total_active_batches": active_count,
        "total_expired_batches": expired_count,
        "total_rescued_batches": rescued_count,
        "revenue_recovered": round(revenue, 2),
        "items_rescued": items_rescued,
    }
