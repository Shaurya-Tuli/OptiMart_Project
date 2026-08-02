import csv
import io
from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.sales_history import (
    SalesHistoryCreate,
    SalesHistoryResponse,
    SalesHistoryBulkCreate,
)
from app.schemas.batch import CSVImportSummary
from app.services.sales_history import (
    create_sales_history_entry,
    bulk_upsert_sales_history,
    get_sales_history,
)

router = APIRouter(prefix="/api/v1/sales-history", tags=["Sales History"])


@router.post("", response_model=SalesHistoryResponse, status_code=status.HTTP_201_CREATED)
def record_sales_history(
    payload: SalesHistoryCreate, db: Session = Depends(get_db)
):
    """Record or update daily sales history entry for a store and SKU."""
    return create_sales_history_entry(db, payload)


@router.post("/bulk", status_code=status.HTTP_201_CREATED)
def bulk_record_sales_history(
    payload: SalesHistoryBulkCreate, db: Session = Depends(get_db)
):
    """Bulk record or update daily sales history entries."""
    count = bulk_upsert_sales_history(db, payload.records)
    return {"status": "success", "inserted_or_updated": count}


@router.get("", response_model=List[SalesHistoryResponse])
def list_sales_history(
    store_id: Optional[int] = Query(None, description="Filter by store ID"),
    sku: Optional[str] = Query(None, description="Filter by SKU"),
    start_date: Optional[date] = Query(None, description="Filter by start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="Filter by end date (YYYY-MM-DD)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Retrieve sales history records with optional filters."""
    return get_sales_history(
        db=db,
        store_id=store_id,
        sku=sku,
        start_date=start_date,
        end_date=end_date,
        skip=skip,
        limit=limit,
    )


@router.post("/upload-csv", response_model=CSVImportSummary)
async def upload_sales_history_csv(
    file: UploadFile = File(...), db: Session = Depends(get_db)
):
    """Import sales history records from a CSV file.
    CSV header format: store_id,sku,date,units_sold,price_at_time,promotion_flag,stockout_flag
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a CSV file",
        )

    content = await file.read()
    decoded = content.decode("utf-8")
    csv_reader = csv.DictReader(io.StringIO(decoded))

    records_to_upsert: List[SalesHistoryCreate] = []
    errors: List[str] = []
    total_processed = 0

    for row_idx, row in enumerate(csv_reader, start=2):
        total_processed += 1
        try:
            parsed_date = date.fromisoformat(row["date"].strip())
            promo = row.get("promotion_flag", "false").strip().lower() in ("true", "1", "yes")
            stockout = row.get("stockout_flag", "false").strip().lower() in ("true", "1", "yes")

            record = SalesHistoryCreate(
                store_id=int(row["store_id"]),
                sku=row["sku"].strip(),
                date=parsed_date,
                units_sold=int(row["units_sold"]),
                price_at_time=float(row["price_at_time"]),
                promotion_flag=promo,
                stockout_flag=stockout,
            )
            records_to_upsert.append(record)
        except Exception as e:
            errors.append(f"Row {row_idx}: {str(e)}")

    inserted_count = 0
    if records_to_upsert:
        inserted_count = bulk_upsert_sales_history(db, records_to_upsert)

    return CSVImportSummary(
        total_processed=total_processed,
        successfully_imported=inserted_count,
        failed_rows=len(errors),
        errors=errors,
    )
