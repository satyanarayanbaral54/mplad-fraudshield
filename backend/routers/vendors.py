"""Vendors router - vendor management and risk tracking."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models.db_models import Vendor
from schemas.pydantic_schemas import VendorCreate, VendorRead

router = APIRouter()


@router.get("/", response_model=List[VendorRead])
def list_vendors(
    skip: int = 0,
    limit: int = 50,
    blacklisted_only: bool = False,
    db: Session = Depends(get_db),
):
    try:
        q = db.query(Vendor)
        if blacklisted_only:
            q = q.filter(Vendor.blacklisted == True)
        return q.order_by(Vendor.risk_score.desc()).offset(skip).limit(limit).all()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{vendor_id}", response_model=VendorRead)
def get_vendor(vendor_id: int, db: Session = Depends(get_db)):
    v = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return v


@router.post("/", response_model=VendorRead, status_code=201)
def create_vendor(payload: VendorCreate, db: Session = Depends(get_db)):
    vendor = Vendor(**payload.model_dump())
    db.add(vendor)
    db.commit()
    db.refresh(vendor)
    return vendor


@router.patch("/{vendor_id}/blacklist")
def toggle_blacklist(vendor_id: int, blacklisted: bool, db: Session = Depends(get_db)):
    vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    vendor.blacklisted = blacklisted
    db.commit()
    return {"id": vendor_id, "blacklisted": blacklisted}


@router.get("/{vendor_id}/network")
def get_vendor_network(vendor_id: int, db: Session = Depends(get_db)):
    """Return vendor-project network data for graph visualization."""
    try:
        vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
        if not vendor:
            raise HTTPException(status_code=404, detail="Vendor not found")

        nodes = [{"id": f"v_{vendor.id}", "label": vendor.name, "type": "vendor", "risk_score": vendor.risk_score}]
        edges = []

        for project in vendor.projects:
            nodes.append({
                "id": f"p_{project.id}",
                "label": project.title[:40],
                "type": "project",
                "risk_score": project.risk_score,
            })
            edges.append({"source": f"v_{vendor.id}", "target": f"p_{project.id}", "amount": project.allocated_amount})

        return {"nodes": nodes, "edges": edges}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
