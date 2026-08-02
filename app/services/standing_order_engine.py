from datetime import datetime, date, timezone
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.batch import Batch
from app.models.standing_order import StandingOrder
from app.models.standing_order_match import StandingOrderMatch


def evaluate_standing_orders(
    db: Session, batch_id: Optional[int] = None
) -> List[StandingOrderMatch]:
    """Scans active inventory batches against active NGO standing order rules.

    Matches batches that:
    1. Are within the standing order's priority window (hours until expiration).
    2. Match the requested category (or category_filter == 'ALL').
    3. Meet or exceed the minimum requested quantity.
    """
    active_standing_orders = (
        db.query(StandingOrder).filter(StandingOrder.is_active == True).all()
    )

    if not active_standing_orders:
        return []

    # Query candidate batches
    batch_query = db.query(Batch).filter(Batch.status.in_(["ACTIVE", "DISCOUNTED"]))
    if batch_id is not None:
        batch_query = batch_query.filter(Batch.id == batch_id)

    candidate_batches = batch_query.all()
    new_matches: List[StandingOrderMatch] = []
    today = date.today()

    for batch in candidate_batches:
        # Calculate approximate hours until expiration
        days_until_expiry = (batch.expiration_date - today).days
        hours_until_expiry = max(0, days_until_expiry * 24)

        for order in active_standing_orders:
            # Check priority time window
            if hours_until_expiry > order.priority_window_hours:
                continue

            # Check category matching
            cat_filter = order.category_filter.strip().lower()
            if cat_filter != "all" and cat_filter != batch.category.strip().lower():
                continue

            # Check minimum quantity
            if batch.quantity < order.min_quantity:
                continue

            # Check if match already recorded for this standing order & batch
            existing_match = (
                db.query(StandingOrderMatch)
                .filter(
                    StandingOrderMatch.standing_order_id == order.id,
                    StandingOrderMatch.batch_id == batch.id,
                )
                .first()
            )
            if existing_match:
                continue

            # Generate zero-cost subsidized priority reservation/allocation for NGO
            match_record = StandingOrderMatch(
                standing_order_id=order.id,
                batch_id=batch.id,
                allocated_quantity=batch.quantity,
                status="RESERVED",
                is_subsidized=True,
            )
            db.add(match_record)
            new_matches.append(match_record)

    if new_matches:
        db.commit()
        for m in new_matches:
            db.refresh(m)

    return new_matches
