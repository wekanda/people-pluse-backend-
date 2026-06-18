"""
Leave Management Router - Phase 1
Handles leave requests, approvals, and balance tracking per Ugandan labor standards.
"""

from fastapi import APIRouter, Depends, HTTPException, status
import logging
import traceback
from sqlalchemy.orm import Session
from datetime import datetime, date, timedelta
from typing import List, Optional
from pydantic import BaseModel
from database import get_db
from auth import get_current_user, check_role, check_employee_access
import models

router = APIRouter(prefix="/leave", tags=["leave"])


# ==================== SCHEMAS ====================

class LeaveTypeSchema(BaseModel):
    id: Optional[int] = None
    name: str
    annual_entitlement_days: float
    description: Optional[str] = None
    is_paid: bool = True
    requires_manager_approval: bool = True

    class Config:
        from_attributes = True


class LeaveBalanceSchema(BaseModel):
    leave_type_id: int
    balance: float
    accrued: float
    used: float

    class Config:
        from_attributes = True


class LeaveRequestSchema(BaseModel):
    employee_id: int
    leave_type_id: int
    start_date: date
    end_date: date
    reason: str
    days: Optional[float] = None  # Auto-calculated if not provided

    class Config:
        from_attributes = True


class LeaveRequestResponseSchema(BaseModel):
    id: int
    employee_id: int
    leave_type_id: int
    start_date: date
    end_date: date
    days: float
    reason: str
    status: str
    submitted_at: datetime
    reviewed_by: Optional[int] = None

    class Config:
        from_attributes = True


class LeaveApprovalSchema(BaseModel):
    action: str  # "approved" or "rejected"
    note: Optional[str] = None


# ==================== UTILITIES ====================

def calculate_working_days(start_date: date, end_date: date) -> float:
    """Calculate working days (Mon-Fri) between two dates, inclusive."""
    total_days = 0
    current = start_date
    while current <= end_date:
        # 0=Mon, 1=Tue, ..., 4=Fri, 5=Sat, 6=Sun
        if current.weekday() < 5:  # Monday to Friday
            total_days += 1
        current += timedelta(days=1)
    return float(total_days)


def check_overlapping_leave(db: Session, employee_id: int, start_date: date, end_date: date) -> bool:
    """Check if employee has overlapping approved/pending leave."""
    overlap = db.query(models.LeaveRequest).filter(
        models.LeaveRequest.employee_id == employee_id,
        models.LeaveRequest.status.in_(["approved", "pending"]),
        models.LeaveRequest.start_date <= end_date,
        models.LeaveRequest.end_date >= start_date
    ).first()
    return overlap is not None


# ==================== ENDPOINTS ====================

@router.get("/types", response_model=List[LeaveTypeSchema])
async def get_leave_types(db: Session = Depends(get_db)):
    """Get all leave types defined in system."""
    types = db.query(models.LeaveType).all()
    return types


@router.post("/types", response_model=LeaveTypeSchema)
async def create_leave_type(
    leave_type: LeaveTypeSchema,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create new leave type (HR Admin only)."""
    if current_user.role != "hr_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only HR Admin can create leave types"
        )
    
    # Check if leave type already exists
    existing = db.query(models.LeaveType).filter(
        models.LeaveType.name == leave_type.name
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Leave type '{leave_type.name}' already exists"
        )
    
    db_leave_type = models.LeaveType(**leave_type.dict())
    db.add(db_leave_type)
    db.commit()
    db.refresh(db_leave_type)
    return db_leave_type


@router.get("/balance/{employee_id}", response_model=List[LeaveBalanceSchema])
async def get_leave_balance(
    employee_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get leave balance for employee (visible to self, manager, or HR Admin)."""
    if not check_employee_access(current_user, employee_id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this employee's leave balance"
        )
    
    balances = db.query(models.LeaveBalance).filter(
        models.LeaveBalance.employee_id == employee_id
    ).all()
    return balances


@router.post("/request", response_model=LeaveRequestResponseSchema)
async def submit_leave_request(
    request: LeaveRequestSchema,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Submit a leave request with server-side logging for debugging."""
    logger = logging.getLogger("leave_management")
    try:
        # Staff can only request for themselves, managers/admin can request for others
        if current_user.role == "staff" and request.employee_id != current_user.employee_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Staff can only request leave for themselves"
            )
        
        if current_user.role not in ["hr_admin", "project_manager"] and request.employee_id != current_user.employee_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to submit leave for other employees"
            )
        
        # Validate dates
        if request.start_date > request.end_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Start date must be before end date"
            )
        
        # Check for overlapping leave
        if check_overlapping_leave(db, request.employee_id, request.start_date, request.end_date):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Employee has overlapping leave request"
            )
        
        # Calculate days if not provided
        days = request.days or calculate_working_days(request.start_date, request.end_date)
        
        # Validate leave type exists
        leave_type = db.query(models.LeaveType).filter(
            models.LeaveType.id == request.leave_type_id
        ).first()
        if not leave_type:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Leave type not found"
            )
        
        # Check leave balance
        balance = db.query(models.LeaveBalance).filter(
            models.LeaveBalance.employee_id == request.employee_id,
            models.LeaveBalance.leave_type_id == request.leave_type_id
        ).first()
        
        if balance and balance.balance < days:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Insufficient leave balance. Available: {balance.balance} days, Requested: {days} days"
            )
        
        # Create leave request
        db_leave_request = models.LeaveRequest(
            employee_id=request.employee_id,
            leave_type_id=request.leave_type_id,
            start_date=request.start_date,
            end_date=request.end_date,
            days=days,
            reason=request.reason,
            status="pending",
            submitted_at=datetime.utcnow()
        )
        db.add(db_leave_request)
        db.commit()
        db.refresh(db_leave_request)
        
        return db_leave_request
    except HTTPException:
        # Re-raise HTTP exceptions without modification
        raise
    except Exception as e:
        tb = traceback.format_exc()
        # Log full traceback
        logger.error("Exception in submit_leave_request: %s", str(e))
        logger.error(tb)
        # Return traceback in response for debugging (can be removed in production)
        raise HTTPException(status_code=500, detail=tb)


@router.get("/request/{request_id}", response_model=LeaveRequestResponseSchema)
async def get_leave_request(
    request_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get details of a leave request."""
    leave_request = db.query(models.LeaveRequest).filter(
        models.LeaveRequest.id == request_id
    ).first()
    
    if not leave_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Leave request not found"
        )
    
    # Check access
    if not check_employee_access(current_user, leave_request.employee_id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this leave request"
        )
    
    return leave_request


@router.post("/request/{request_id}/approve")
async def approve_leave_request(
    request_id: int,
    approval: LeaveApprovalSchema,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Approve or reject a leave request (Manager or HR Admin only)."""
    if current_user.role not in ["hr_admin", "project_manager"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only managers and HR Admin can approve leave"
        )
    
    leave_request = db.query(models.LeaveRequest).filter(
        models.LeaveRequest.id == request_id
    ).first()
    
    if not leave_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Leave request not found"
        )
    
    if leave_request.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve leave request with status: {leave_request.status}"
        )
    
    # Project managers can only approve their team
    if current_user.role == "project_manager":
        if not check_employee_access(current_user, leave_request.employee_id, db):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Can only approve leave for team members"
            )
    
    if approval.action == "approved":
        leave_request.status = "approved"
        
        # Update leave balance
        balance = db.query(models.LeaveBalance).filter(
            models.LeaveBalance.employee_id == leave_request.employee_id,
            models.LeaveBalance.leave_type_id == leave_request.leave_type_id
        ).first()
        
        if balance:
            balance.used += leave_request.days
            balance.balance -= leave_request.days
            balance.last_updated = datetime.utcnow()
    
    elif approval.action == "rejected":
        leave_request.status = "rejected"
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Action must be 'approved' or 'rejected'"
        )
    
    leave_request.reviewed_by = current_user.id
    db.commit()
    db.refresh(leave_request)
    
    return {
        "status": "success",
        "message": f"Leave request {approval.action}",
        "leave_request": leave_request
    }


@router.get("/employee/{employee_id}/requests", response_model=List[LeaveRequestResponseSchema])
async def get_employee_leave_requests(
    employee_id: int,
    status: Optional[str] = None,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all leave requests for an employee."""
    if not check_employee_access(current_user, employee_id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this employee's leave requests"
        )
    
    query = db.query(models.LeaveRequest).filter(
        models.LeaveRequest.employee_id == employee_id
    )
    
    if status:
        query = query.filter(models.LeaveRequest.status == status)
    
    requests = query.all()
    return requests


@router.get("/pending", response_model=List[LeaveRequestResponseSchema])
async def get_pending_approvals(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get pending leave requests for approval (Manager or HR Admin only)."""
    if current_user.role not in ["hr_admin", "project_manager"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only managers and HR Admin can view pending approvals"
        )
    
    query = db.query(models.LeaveRequest).filter(
        models.LeaveRequest.status == "pending"
    )
    
    # Project managers see only their team's requests
    if current_user.role == "project_manager":
        # Get employees in manager's project
        query = query.join(models.Employee).filter(
            models.Employee.project == (
                db.query(models.Employee.project).filter(
                    models.Employee.id == current_user.employee_id
                ).scalar()
            )
        )
    
    requests = query.all()
    return requests
