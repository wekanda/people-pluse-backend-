from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from database import get_db
import models
from auth import get_current_user
from datetime import date
from datetime import datetime

router = APIRouter(prefix="/recruitment", tags=["recruitment"])


@router.post("/jobs")
def create_job(job: dict, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    j = models.JobPosting(
        title=job.get('title'),
        description=job.get('description'),
        department=job.get('department'),
        location=job.get('location'),
        closing_date=job.get('closing_date'),
        created_by=current_user.id
    )
    db.add(j)
    db.commit()
    db.refresh(j)
    return j


@router.get("/jobs")
def list_jobs(db: Session = Depends(get_db)):
    jobs = db.query(models.JobPosting).all()
    return jobs


@router.get("/public/jobs")
def public_jobs(open_only: bool = True, db: Session = Depends(get_db)):
    # Public career page listing (no auth)
    q = db.query(models.JobPosting).filter(models.JobPosting.is_internal == False)
    if open_only:
        q = q.filter(models.JobPosting.status.in_(["open", "published"]))
    return q.order_by(models.JobPosting.posted_at.desc()).all()


@router.get("/jobs/{job_id}")
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(models.JobPosting).filter(models.JobPosting.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/jobs/{job_id}/apply")
def apply_job(job_id: int, payload: dict, db: Session = Depends(get_db)):
    job = db.query(models.JobPosting).filter(models.JobPosting.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    app = models.Application(
        job_id=job_id,
        applicant_name=payload.get('applicant_name'),
        email=payload.get('email'),
        resume_url=payload.get('resume_url'),
        cover_letter=payload.get('cover_letter')
    )
    db.add(app)
    db.commit()
    db.refresh(app)
    return app


@router.put("/jobs/{job_id}")
def update_job(job_id: int, payload: dict, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    job = db.query(models.JobPosting).filter(models.JobPosting.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    # Only creators or HR/manager can update
    if current_user.role not in ("hr_admin", "project_manager") and job.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    for field in ("title", "description", "department", "location", "closing_date", "status", "is_internal"):
        if field in payload:
            setattr(job, field, payload.get(field))

    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@router.get("/applications")
def list_applications(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    # HR and managers see all, others see none
    if current_user.role in ("hr_admin", "project_manager"):
        apps = db.query(models.Application).all()
    else:
        apps = []
    return apps


@router.post("/jobs/{job_id}/publish")
def publish_job(job_id: int, payload: dict, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    # payload: { channels: ['linkedin','indeed'], is_internal: false }
    if current_user.role not in ("hr_admin", "project_manager"):
        raise HTTPException(status_code=403, detail="Insufficient permissions to publish jobs")
    job = db.query(models.JobPosting).filter(models.JobPosting.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    channels = payload.get('channels', []) or []
    is_internal = payload.get('is_internal', False)

    job.is_internal = bool(is_internal)
    job.channels = ','.join(channels) if channels else None
    job.published_at = datetime.utcnow()
    job.status = 'published'

    # Simulate external posting (stub) - record channels used
    if channels:
        # Here you would integrate with external APIs; we just mark as posted
        job.external_posted = True
        job.external_channels = ','.join(channels)
        # In production, enqueue background tasks to push to job boards

    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@router.patch("/applications/{app_id}/status")
def update_application_status(app_id: int, payload: dict, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    app = db.query(models.Application).filter(models.Application.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    app.status = payload.get('status', app.status)
    app.reviewer_id = current_user.id
    db.add(app)
    db.commit()
    db.refresh(app)
    return app


@router.post("/internships")
def create_internship(payload: dict, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    internship = models.Internship(
        candidate_name=payload.get('candidate_name'),
        email=payload.get('email'),
        start_date=payload.get('start_date'),
        end_date=payload.get('end_date'),
        mentor_id=payload.get('mentor_id') or current_user.id,
        notes=payload.get('notes')
    )
    db.add(internship)
    db.commit()
    db.refresh(internship)
    return internship


@router.get("/internships")
def list_internships(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if current_user.role in ("hr_admin", "project_manager"):
        items = db.query(models.Internship).all()
    else:
        items = db.query(models.Internship).filter(models.Internship.email == current_user.email).all()
    return items
