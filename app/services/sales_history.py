from datetime import date
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
from app.models.sales_history import SalesHistory
from app.schemas.sales_history import SalesHistoryCreate, SalesHistoryCSVRow


def create_sales_history_entry(db: Session, data: SalesHistoryCreate) -> SalesHistory:
    """Create or update a daily sales history record for a store and SKU."""
    stmt = insert(SalesHistory).values(
        store_id=data.store_id,
        sku=data.sku,
        date=data.date,
        units_sold=data.units_sold,
        price_at_time=data.price_at_time,
        promotion_flag=data.promotion_flag,
        stockout_flag=data.stockout_flag,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["store_id", "sku", "date"],
        set_={
            "units_sold": stmt.excluded.units_sold,
            "price_at_time": stmt.excluded.price_at_time,
            "promotion_flag": stmt.excluded.promotion_flag,
            "stockout_flag": stmt.excluded.stockout_flag,
        },
    )
    db.execute(stmt)
    db.commit()
    return (
        db.query(SalesHistory)
        .filter(
            SalesHistory.store_id == data.store_id,
            SalesHistory.sku == data.sku,
            SalesHistory.date == data.date,
        )
        .first()
    )


def bulk_upsert_sales_history(
    db: Session, records: List[SalesHistoryCreate]
) -> int:
    """Bulk upsert daily sales history records."""
    if not records:
        return 0

    values = [
        {
            "store_id": r.store_id,
            "sku": r.sku,
            "date": r.date,
            "units_sold": r.units_sold,
            "price_at_time": r.price_at_time,
            "promotion_flag": r.promotion_flag,
            "stockout_flag": r.stockout_flag,
        }
        for r in records
    ]

    stmt = insert(SalesHistory).values(values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["store_id", "sku", "date"],
        set_={
            "units_sold": stmt.excluded.units_sold,
            "price_at_time": stmt.excluded.price_at_time,
            "promotion_flag": stmt.excluded.promotion_flag,
            "stockout_flag": stmt.excluded.stockout_flag,
        },
    )
    db.execute(stmt)
    db.commit()
    return len(records)


def get_sales_history(
    db: Session,
    store_id: Optional[int] = None,
    sku: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    skip: int = 0,
    limit: int = 100,
) -> List[SalesHistory]:
    """Retrieve sales history records filtered by store, SKU, and date range."""
    query = db.query(SalesHistory)
    if store_id is not None:
        query = query.filter(SalesHistory.store_id == store_id)
    if sku is not None:
        query = query.filter(SalesHistory.sku == sku)
    if start_date is not None:
        query = query.filter(SalesHistory.date >= start_date)
    if end_date is not None:
        query = query.filter(SalesHistory.date <= end_date)

    return query.order_by(SalesHistory.date.desc()).offset(skip).limit(limit).all()
