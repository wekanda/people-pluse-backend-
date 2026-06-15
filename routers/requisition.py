from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
import models
from auth import get_current_user
from datetime import datetime

router = APIRouter(prefix="/requisitions", tags=["requisitions"])


@router.post("")
def create_requisition(payload: dict, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    req = models.Requisition(
        title=payload.get('title'),
        department=payload.get('department'),
        location=payload.get('location'),
        job_description=payload.get('job_description'),
        justification=payload.get('justification'),
        vacancy_count=payload.get('vacancy_count') or 1,
        budget=payload.get('budget') or 0.0,
        requested_by=current_user.id,
        priority=payload.get('priority') or 'normal'
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


@router.get("")
def list_requisitions(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    # HR and managers can see all, others only their own
    if current_user.role in ("hr_admin", "project_manager"):
        items = db.query(models.Requisition).order_by(models.Requisition.created_at.desc()).all()
    else:
        items = db.query(models.Requisition).filter(models.Requisition.requested_by == current_user.id).all()
    return items


@router.get("/{req_id}")
def get_requisition(req_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    req = db.query(models.Requisition).filter(models.Requisition.id == req_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Requisition not found")
    # permission check
    if current_user.role not in ("hr_admin", "project_manager") and req.requested_by != current_user.id:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return req


@router.post("/{req_id}/action")
def action_requisition(req_id: int, payload: dict, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    # payload: { action: 'approve'|'reject', note: '...'}
    if current_user.role not in ("hr_admin", "project_manager"):
        raise HTTPException(status_code=403, detail="Insufficient permissions to act on requisitions")
    req = db.query(models.Requisition).filter(models.Requisition.id == req_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Requisition not found")
    action = payload.get('action')
    note = payload.get('note')
    if action == 'approve':
        req.status = 'approved'
        req.approved_by = current_user.id
        req.approved_at = datetime.utcnow()
    elif action == 'reject':
        req.status = 'rejected'
        req.approved_by = current_user.id
        req.approved_at = datetime.utcnow()
    else:
        raise HTTPException(status_code=400, detail='Unknown action')

    approval = models.RequisitionApproval(
        requisition_id=req.id,
        approver_id=current_user.id,
        action=action,
        note=note
    )
    db.add(approval)
    db.add(req)
    db.commit()
    db.refresh(req)
    return req
