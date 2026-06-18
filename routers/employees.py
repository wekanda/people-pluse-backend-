from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import date
from database import get_db
import models
from auth import get_current_user, check_employee_access, require_role
from typing import List

router = APIRouter(prefix="/api/employees", tags=["employees"])

class EmployeeCreate(BaseModel):
    file_code: str
    full_name: str
    project: str
    status: str = "Active"
    position: str | None = None
    contact_number: str | None = None
    location: str | None = None
    photo_url: str | None = None
    locker: str | None = None
    date_of_appointment: date | None = None
    contract_start: date | None = None
    contract_end: date | None = None
    contract_review_date: date | None = None
    probation_end: date | None = None
    employment_type: str | None = None
    notice_period: str | None = None

class EmployeeUpdate(BaseModel):
    full_name: str | None = None
    status: str | None = None
    position: str | None = None
    contact_number: str | None = None
    location: str | None = None
    photo_url: str | None = None
    contract_end: date | None = None
    missing_app_resume: bool | None = None
    missing_appointment_letter: bool | None = None
    missing_academic_docs: bool | None = None
    missing_national_id: bool | None = None

class EmployeeResponse(BaseModel):
    id: int
    file_code: str
    full_name: str
    project: str | None = None
    status: str | None = None
    position: str | None = None
    contact_number: str | None = None
    location: str | None = None
    photo_url: str | None = None
    employment_type: str | None = None
    contract_end: date | None = None
    class Config:
        from_attributes = True

@router.get("/", response_model=List[EmployeeResponse])
def list_employees(skip: int = 0, limit: int = 100, status: str = None, project: str = None,
                   db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    query = db.query(models.Employee)
    if current_user.role == "project_manager":
        manager = db.query(models.Employee).filter(models.Employee.id == current_user.employee_id).first()
        if manager and manager.project:
            query = query.filter(models.Employee.project == manager.project)
        else:
            query = query.filter(models.Employee.id == -1)
    elif current_user.role == "staff":
        if current_user.employee_id is None:
            raise HTTPException(status_code=403, detail="Access denied")
        query = query.filter(models.Employee.id == current_user.employee_id)

    if status:
        query = query.filter(models.Employee.status == status)
    if project:
        query = query.filter(models.Employee.project == project)
    return query.offset(skip).limit(limit).all()

@router.get("/{employee_id}", response_model=EmployeeResponse)
def get_employee(employee_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if not check_employee_access(current_user, employee_id, db):
        raise HTTPException(status_code=403, detail="Access denied")
    employee = db.query(models.Employee).filter(models.Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    return employee

@router.post("/", response_model=EmployeeResponse)
@require_role("hr_admin")
def create_employee(employee: EmployeeCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    existing = db.query(models.Employee).filter(models.Employee.file_code == employee.file_code).first()
    if existing:
        raise HTTPException(status_code=400, detail="File code already exists")
    db_employee = models.Employee(**employee.dict())
    db.add(db_employee)
    db.commit()
    db.refresh(db_employee)
    return db_employee

@router.put("/{employee_id}", response_model=EmployeeResponse)
@require_role("hr_admin")
def update_employee(employee_id: int, employee: EmployeeUpdate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    db_employee = db.query(models.Employee).filter(models.Employee.id == employee_id).first()
    if not db_employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    for field, value in employee.dict(exclude_unset=True).items():
        setattr(db_employee, field, value)
    db.commit()
    db.refresh(db_employee)
    return db_employee

@router.delete("/{employee_id}")
@require_role("hr_admin")
def delete_employee(employee_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    db_employee = db.query(models.Employee).filter(models.Employee.id == employee_id).first()
    if not db_employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    db.delete(db_employee)
    db.commit()
    return {"message": "Employee deleted"}
