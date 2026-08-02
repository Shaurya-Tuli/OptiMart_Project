import csv
import io
from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from sqlalchemy import func
from sqlalchemy.orm import Session


from app.db import get_db
from app.models.store import Store
from app.models.batch import Batch
from app.schemas.batch import (
    BatchCreate,
    BatchUpdate,
    BatchResponse,
    CSVImportSummary,
)

router = APIRouter(prefix="/api/v1/inventory", tags=["Inventory"])


@router.post(
    "/batches", response_model=BatchResponse, status_code=status.HTTP_201_CREATED
)
def create_batch(batch_in: BatchCreate, db: Session = Depends(get_db)):
    """Create a new inventory batch."""
    # Verify store exists
    store = db.query(Store).filter(Store.id == batch_in.store_id).first()
    if not store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Store with id {batch_in.store_id} not found",
        )

    current_price = (
        batch_in.current_price
        if batch_in.current_price is not None
        else batch_in.original_selling_price * (1 - batch_in.discount_percentage / 100.0)
    )

    batch = Batch(
        store_id=batch_in.store_id,
        sku=batch_in.sku,
        product_name=batch_in.product_name,
        category=batch_in.category,
        quantity=batch_in.quantity,
        cost_price=batch_in.cost_price,
        original_selling_price=batch_in.original_selling_price,
        current_price=current_price,
        expiration_date=batch_in.expiration_date,
        discount_percentage=batch_in.discount_percentage,
        status=batch_in.status,
    )

    db.add(batch)
    db.commit()
    db.refresh(batch)
    return batch


@router.get("/batches", response_model=List[BatchResponse])
def list_batches(
    store_id: Optional[int] = None,
    category: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    expiring_before: Optional[date] = None,
    expiring_after: Optional[date] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """List inventory batches with optional filtering by store, category, status, and expiration date."""
    query = db.query(Batch)

    if store_id is not None:
        query = query.filter(Batch.store_id == store_id)

    if category:
        query = query.filter(Batch.category.ilike(f"%{category}%"))

    if status_filter:
        query = query.filter(func.upper(Batch.status) == status_filter.upper())


    if expiring_before:
        query = query.filter(Batch.expiration_date <= expiring_before)

    if expiring_after:
        query = query.filter(Batch.expiration_date >= expiring_after)

    return query.offset(skip).limit(limit).all()


@router.get("/batches/{batch_id}", response_model=BatchResponse)
def get_batch(batch_id: int, db: Session = Depends(get_db)):
    """Get details for a specific inventory batch."""
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch with id {batch_id} not found",
        )
    return batch


@router.put("/batches/{batch_id}", response_model=BatchResponse)
def update_batch(
    batch_id: int, batch_in: BatchUpdate, db: Session = Depends(get_db)
):
    """Update inventory batch details."""
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch with id {batch_id} not found",
        )

    update_data = batch_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(batch, field, value)

    # Recalculate current_price if discount_percentage or original_selling_price was updated without explicit current_price
    if ("discount_percentage" in update_data or "original_selling_price" in update_data) and "current_price" not in update_data:
        batch.current_price = batch.original_selling_price * (1 - batch.discount_percentage / 100.0)

    db.commit()
    db.refresh(batch)
    return batch


@router.delete("/batches/{batch_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_batch(batch_id: int, db: Session = Depends(get_db)):
    """Delete an inventory batch."""
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch with id {batch_id} not found",
        )
    db.delete(batch)
    db.commit()
    return None


@router.post("/upload-csv", response_model=CSVImportSummary)
async def upload_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Bulk import inventory batches from CSV file.
    Expected CSV columns: store_id, sku, product_name, category, quantity, cost_price, original_selling_price, current_price, expiration_date, discount_percentage, status
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a CSV (.csv)",
        )

    contents = await file.read()
    try:
        decoded = contents.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV file encoding must be UTF-8",
        )

    reader = csv.DictReader(io.StringIO(decoded))

    total_processed = 0
    successfully_imported = 0
    failed_rows = 0
    errors: List[str] = []

    for row_idx, row in enumerate(reader, start=1):
        total_processed += 1
        try:
            store_id = int(row["store_id"].strip())
            sku = row["sku"].strip()
            product_name = row["product_name"].strip()
            category = row.get("category", "General").strip() or "General"
            quantity = int(row["quantity"].strip())
            cost_price = float(row["cost_price"].strip())
            original_selling_price = float(row["original_selling_price"].strip())
            
            raw_current_price = row.get("current_price", "").strip()
            discount_percentage = float(row.get("discount_percentage", "0").strip() or 0.0)
            
            if raw_current_price:
                current_price = float(raw_current_price)
            else:
                current_price = original_selling_price * (1 - discount_percentage / 100.0)

            exp_date_str = row["expiration_date"].strip()
            expiration_date = date.fromisoformat(exp_date_str)
            status_val = row.get("status", "ACTIVE").strip() or "ACTIVE"

            # Check if store exists
            store = db.query(Store).filter(Store.id == store_id).first()
            if not store:
                raise ValueError(f"Store ID {store_id} does not exist")

            batch = Batch(
                store_id=store_id,
                sku=sku,
                product_name=product_name,
                category=category,
                quantity=quantity,
                cost_price=cost_price,
                original_selling_price=original_selling_price,
                current_price=current_price,
                expiration_date=expiration_date,
                discount_percentage=discount_percentage,
                status=status_val,
            )
            db.add(batch)
            db.commit()
            successfully_imported += 1
        except Exception as e:
            db.rollback()
            failed_rows += 1
            errors.append(f"Row {row_idx}: {str(e)}")

    return CSVImportSummary(
        total_processed=total_processed,
        successfully_imported=successfully_imported,
        failed_rows=failed_rows,
        errors=errors,
    )
