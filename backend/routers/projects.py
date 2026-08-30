"""Projects router - CRUD + analysis for MPLAD projects."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_

from database import get_db
from models.db_models import Project, Flag, Vendor
from schemas.pydantic_schemas import ProjectCreate, ProjectRead, ProjectDetail, FlagRead

router = APIRouter()


@router.get("/", response_model=List[ProjectRead])
def list_projects(
    skip: int = 0,
    limit: int = 50,
    state: Optional[str] = None,
    risk_level: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """List all MPLAD projects with optional filters."""
    try:
        q = db.query(Project)
        if state:
            q = q.filter(Project.state == state)
        if risk_level:
            q = q.filter(Project.risk_level == risk_level)
        if search:
            q = q.filter(
                or_(Project.title.ilike(f"%{search}%"), Project.mp_name.ilike(f"%{search}%"))
            )
        projects = q.offset(skip).limit(limit).all()
        return projects
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{project_id}", response_model=ProjectDetail)
def get_project(project_id: int, db: Session = Depends(get_db)):
    """Get a single project with all flags and vendor info."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post("/", response_model=ProjectRead, status_code=201)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    """Create a new MPLAD project."""
    project = Project(**payload.model_dump())
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.post("/{project_id}/analyze")
def analyze_project(project_id: int, db: Session = Depends(get_db)):
    """Run all fraud detection engines on a single project and save flags."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    from tasks.batch_analysis import run_full_analysis_on_project

    p_dict = {
        "id": project.id,
        "title": project.title,
        "description": project.description,
        "allocated_amount": project.allocated_amount,
        "disbursed_amount": project.disbursed_amount,
        "expenditure": project.expenditure,
        "status": project.status.value if project.status else "PROPOSED",
    }
    vendor_dict = None
    if project.vendor:
        vendor_dict = {
            "id": project.vendor.id,
            "blacklisted": project.vendor.blacklisted,
            "total_contracts": project.vendor.total_contracts,
        }

    result = run_full_analysis_on_project(p_dict, vendor_dict)

    # Persist risk score
    project.risk_score = result["risk_score"]
    project.risk_level = result["risk_level"]

    # Save flags
    for flag in result["flags"]:
        db_flag = Flag(
            project_id=project.id,
            flag_type=flag["flag_type"],
            severity=flag["severity"],
            description=flag["description"],
            engine_source=flag.get("engine_source"),
            evidence=flag.get("evidence"),
        )
        db.add(db_flag)

    db.commit()
    return result


@router.get("/{project_id}/flags", response_model=List[FlagRead])
def get_project_flags(project_id: int, db: Session = Depends(get_db)):
    """Get all flags for a project."""
    flags = db.query(Flag).filter(Flag.project_id == project_id).all()
    return flags
