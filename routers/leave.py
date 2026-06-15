from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import date, datetime
from sqlalchemy import func
import models, schemas
from database import get_db
from auth import get_current_user
from typing import List

router = APIRouter(prefix="/api/leave", tags=["leave"])

class LeaveRequestResponse(schemas.LeaveRequestCreate):
    id: int
    days: float
    status: str
    submitted_at: datetime
    reviewed_by: int | None = None
    class Config:
        from_attributes = True

@router.post("/request", response_model=LeaveRequestResponse)
def create_leave_request(request: schemas.LeaveRequestCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if request.end_date < request.start_date:
        raise HTTPException(status_code=400, detail="End date must be the same or after start date")
    delta = (request.end_date - request.start_date).days + 1
    new_request = models.LeaveRequest(
        employee_id=request.employee_id,
        start_date=request.start_date,
        end_date=request.end_date,
        days=delta,
        reason=request.reason,
        type=request.type,
        status="Pending"
    )
    db.add(new_request)
    db.commit()
    db.refresh(new_request)
    return new_request

@router.get("/balance/{employee_id}")
def get_leave_balance(employee_id: int, db: Session = Depends(get_db)):
    total_allowed = 21
    year = date.today().year
    approved_days = db.query(func.sum(models.LeaveRequest.days)).filter(
        models.LeaveRequest.employee_id == employee_id,
        models.LeaveRequest.status == "Approved",
        models.LeaveRequest.start_date >= date(year, 1, 1),
        models.LeaveRequest.end_date <= date(year, 12, 31)
    ).scalar() or 0
    return {"total_allowed": total_allowed, "used": approved_days, "remaining": total_allowed - approved_days}

@router.get("/requests", response_model=List[LeaveRequestResponse])
def list_leave_requests(employee_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(models.LeaveRequest).order_by(models.LeaveRequest.submitted_at.desc())
    if employee_id:
        query = query.filter(models.LeaveRequest.employee_id == employee_id)
    return query.all()

@router.put("/approve/{request_id}")
def approve_leave(request_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if current_user.role not in ["hr_admin", "project_manager"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    leave = db.query(models.LeaveRequest).filter(models.LeaveRequest.id == request_id).first()
    if not leave:
        raise HTTPException(status_code=404, detail="Not found")
    leave.status = "Approved"
    leave.reviewed_by = current_user.id
    db.commit()
    return {"message": "Leave approved"}

@router.put("/reject/{request_id}")
def reject_leave(request_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if current_user.role not in ["hr_admin", "project_manager"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    leave = db.query(models.LeaveRequest).filter(models.LeaveRequest.id == request_id).first()
    if not leave:
        raise HTTPException(status_code=404, detail="Not found")
    leave.status = "Rejected"
    leave.reviewed_by = current_user.id
    db.commit()
    return {"message": "Leave rejected"}


@router.get("/calendar/{department_or_project}")
def get_leave_calendar(department_or_project: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Get a calendar of approved leave for a department/project."""
    # Query approved leave for employees in the project
    approved_leave = db.query(models.LeaveRequest).filter(
        models.LeaveRequest.status == "Approved"
    ).all()

    # Group by start/end dates and employees
    calendar_events = []
    for leave in approved_leave:
        emp = db.query(models.Employee).filter(models.Employee.id == leave.employee_id).first()
        if emp and emp.project == department_or_project:
            calendar_events.append({
                "employee_id": leave.employee_id,
                "employee_name": emp.full_name,
                "start_date": str(leave.start_date),
                "end_date": str(leave.end_date),
                "type": leave.type,
                "days": leave.days
            })
    
    return {"project": department_or_project, "leave_events": calendar_events}


@router.get("/team_leave")
def get_team_leave_calendar(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Get all approved leave for the current user's team/project."""
    # Find current user's employee record and project
    current_user_emp = db.query(models.Employee).filter(models.Employee.id == current_user.employee_id).first()
    if not current_user_emp:
        return {"message": "User has no employee record", "leave_events": []}

    project = current_user_emp.project
    approved_leave = db.query(models.LeaveRequest).filter(
        models.LeaveRequest.status == "Approved"
    ).all()

    calendar_events = []
    for leave in approved_leave:
        emp = db.query(models.Employee).filter(models.Employee.id == leave.employee_id).first()
        if emp and emp.project == project:
            calendar_events.append({
                "employee_id": leave.employee_id,
                "employee_name": emp.full_name,
                "start_date": str(leave.start_date),
                "end_date": str(leave.end_date),
                "type": leave.type,
                "days": leave.days
            })
    
    return {"project": project, "leave_events": calendar_events}


@router.get("/pending")
def get_pending_leave_approvals(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Get pending leave requests (for HR or managers to approve)."""
    if current_user.role not in ["hr_admin", "project_manager"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    pending = db.query(models.LeaveRequest).filter(
        models.LeaveRequest.status == "Pending"
    ).all()
    
    result = []
    for leave in pending:
        emp = db.query(models.Employee).filter(models.Employee.id == leave.employee_id).first()
        result.append({
            "id": leave.id,
            "employee_id": leave.employee_id,
            "employee_name": emp.full_name if emp else "Unknown",
            "start_date": str(leave.start_date),
            "end_date": str(leave.end_date),
            "type": leave.type,
            "days": leave.days,
            "reason": leave.reason,
            "submitted_at": str(leave.submitted_at)
        })
    
    return {"pending_count": len(result), "requests": result}
