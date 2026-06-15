from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from database import get_db
import models
from auth import get_current_user
from datetime import datetime
import io
import re
import os
from email.utils import parseaddr

try:
    from pdfminer.high_level import extract_text
except ImportError:
    extract_text = None

STATIC_UPLOAD_DIR = os.path.join(os.path.dirname(__file__), '..', 'static', 'uploads')
os.makedirs(STATIC_UPLOAD_DIR, exist_ok=True)

router = APIRouter(prefix="/ats", tags=["ats"])


@router.post('/applicants')
def create_applicant(payload: dict, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    a = models.Applicant(
        full_name=payload.get('full_name'),
        email=payload.get('email'),
        phone=payload.get('phone'),
        source=payload.get('source'),
        resume_url=payload.get('resume_url')
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


@router.get('/applicants')
def list_applicants(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if current_user.role in ('hr_admin','project_manager'):
        items = db.query(models.Applicant).order_by(models.Applicant.created_at.desc()).all()
    else:
        items = db.query(models.Applicant).filter(models.Applicant.email == current_user.email).all()
    return items


@router.get('/applications')
def list_applications(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if current_user.role in ('hr_admin','project_manager'):
        return db.query(models.Application).all()
    return []


@router.post('/applications/{app_id}/advance')
def advance_application(app_id: int, payload: dict, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    app = db.query(models.Application).filter(models.Application.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail='Application not found')
    stage = payload.get('stage')
    status = payload.get('status') or 'in_progress'
    note = payload.get('note')
    st = models.ApplicationStage(application_id=app.id, stage=stage, status=status, note=note)
    db.add(st)
    db.commit()
    return st


@router.post('/applications/{app_id}/interviews')
def schedule_interview(app_id: int, payload: dict, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    app_obj = db.query(models.Application).filter(models.Application.id == app_id).first()
    if not app_obj:
        raise HTTPException(status_code=404, detail='Application not found')
    scheduled_at = payload.get('scheduled_at')
    try:
        scheduled = datetime.fromisoformat(scheduled_at)
    except Exception:
        scheduled = datetime.utcnow()
    interview = models.Interview(application_id=app_id, scheduled_at=scheduled, duration_minutes=payload.get('duration_minutes',60), panel=','.join(map(str,payload.get('panel',[]))), location=payload.get('location'))
    db.add(interview)
    db.commit()
    db.refresh(interview)
    return interview


@router.post('/applications/{app_id}/feedback')
def add_feedback(app_id: int, payload: dict, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    fb = models.Feedback(application_id=app_id, reviewer_id=current_user.id, rating=payload.get('rating'), comments=payload.get('comments'))
    db.add(fb)
    db.commit()
    db.refresh(fb)
    return fb


@router.post('/applications/{app_id}/offer')
def create_offer(app_id: int, payload: dict, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    offer = models.Offer(application_id=app_id, salary=payload.get('salary'), currency=payload.get('currency','USD'), terms=payload.get('terms'))
    db.add(offer)
    db.commit()
    db.refresh(offer)
    return offer


@router.post('/applications/{app_id}/onboard')
def convert_to_employee(app_id: int, payload: dict, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    app_obj = db.query(models.Application).filter(models.Application.id == app_id).first()
    if not app_obj:
        raise HTTPException(status_code=404, detail='Application not found')
    # Minimal conversion: create Employee from applicant details
    applicant = db.query(models.Applicant).filter(models.Applicant.email == app_obj.email).first() if hasattr(app_obj, 'email') else None
    if not applicant:
        # try to find by application fields
        applicant = None
    emp = models.Employee(full_name=app_obj.applicant_name, file_code=payload.get('file_code') or f"EMP{int(datetime.utcnow().timestamp())}", project=payload.get('project','New Hire'), status='Active', position=payload.get('position','New Hire'), contact_number=payload.get('phone'))
    db.add(emp)
    db.commit()
    db.refresh(emp)
    # create onboarding checklist
    checklist = models.OnboardingChecklist(employee_id=emp.id, application_id=app_id, items_json=payload.get('items_json'))
    db.add(checklist)
    db.commit()
    return { 'employee': emp, 'checklist': checklist }


@router.post('/applications/{app_id}/upload_resume')
def upload_resume(app_id: int, file: UploadFile = File(...), db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    # store file to /static/uploads/ and save URL (simple implementation)
    content = file.file.read()
    filename = f"resume_{app_id}_{int(datetime.utcnow().timestamp())}_{file.filename}"
    path = f"backend/static/uploads/{filename}"
    with open(path, 'wb') as f:
        f.write(content)
    # attach to application
    app_obj = db.query(models.Application).filter(models.Application.id == app_id).first()
    if app_obj:
        app_obj.resume_url = f"/static/uploads/{filename}"
        db.add(app_obj)
        db.commit()
    return { 'url': f"/static/uploads/{filename}" }


@router.post('/applications/{app_id}/parse_resume')
def parse_resume(app_id: int, file: UploadFile = File(None), db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Enhanced resume parsing: extract text from PDF/text files and parse for contact info."""
    text = ''
    try:
        if file:
            raw = file.file.read()
            filename_lower = file.filename.lower() if file.filename else ''
            
            # Try PDF extraction if pdfminer is available and file is PDF
            if filename_lower.endswith('.pdf') and extract_text:
                try:
                    text = extract_text(io.BytesIO(raw))
                except Exception as pdf_err:
                    # Fallback to generic text extraction
                    text = raw.decode('utf-8', errors='ignore')
            else:
                # Plain text extraction
                text = raw.decode('utf-8', errors='ignore')
        else:
            app_obj = db.query(models.Application).filter(models.Application.id == app_id).first()
            if not app_obj or not getattr(app_obj, 'resume_url', None):
                raise HTTPException(status_code=404, detail='No resume available')
            path = app_obj.resume_url.lstrip('/')
            full = os.path.join(os.path.dirname(__file__), '..', path)
            if os.path.exists(full):
                with open(full, 'rb') as f:
                    raw = f.read()
                    filename_lower = full.lower()
                    if filename_lower.endswith('.pdf') and extract_text:
                        try:
                            text = extract_text(io.BytesIO(raw))
                        except Exception:
                            text = raw.decode('utf-8', errors='ignore')
                    else:
                        text = raw.decode('utf-8', errors='ignore')

        # Parse extracted text for contact information
        # Extract emails
        emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', text)
        email = emails[0] if emails else None

        # Extract phone numbers (international and local formats)
        phones = re.findall(r'\+?\d[\d\s\-\(\)]{7,}\d|\(\d{3}\)[\d\s\-]{7,}\d', text)
        phone = phones[0].strip() if phones else None

        # Extract name: look for lines with capitalized words at start (common resume format)
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        name = None
        for l in lines[:15]:
            # Match capitalized first and last name
            if re.match(r'^[A-Z][a-z]+\s+[A-Z][a-z]+', l):
                name = l.strip()
                break

        # Extract skills (simple heuristic: look for keywords)
        skills = []
        skill_keywords = ['python', 'java', 'javascript', r'c\+\+', 'c#', 'sql', 'react', 'angular', 'django', 'node', 'aws', 'gcp', 'azure', 'docker', 'kubernetes', 'git', 'agile', 'scrum']
        for skill in skill_keywords:
            if re.search(r'\b' + skill + r'\b', text, re.IGNORECASE):
                skills.append(skill.title())

        return {
            'name': name,
            'email': email,
            'phone': phone,
            'skills': skills[:5],  # Top 5 detected skills
            'text_preview': text[:500]  # First 500 chars for reference
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'Resume parsing error: {str(e)}')


def _create_ics(invite):
    # invite: dict with organizer, attendees (list of emails), start_dt (ISO), end_dt, summary, description, location
    uid = f"invite-{int(datetime.utcnow().timestamp())}"
    start = invite.get('start_dt')
    end = invite.get('end_dt')
    summary = invite.get('summary', 'Interview')
    description = invite.get('description', '')
    location = invite.get('location', '')

    # Simple ICS content
    ics = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//PeoplePluse//EN
BEGIN:VEVENT
UID:{uid}
DTSTAMP:{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}
DTSTART:{start.replace('-','').replace(':','').replace('T','T')}
DTEND:{end.replace('-','').replace(':','').replace('T','T')}
SUMMARY:{summary}
DESCRIPTION:{description}
LOCATION:{location}
END:VEVENT
END:VCALENDAR
"""
    filename = f"invite_{uid}.ics"
    path = os.path.join(STATIC_UPLOAD_DIR, filename)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(ics)
    return f"/static/uploads/{filename}"


@router.post('/applications/{app_id}/invite')
def create_invite(app_id: int, payload: dict, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    app_obj = db.query(models.Application).filter(models.Application.id == app_id).first()
    if not app_obj:
        raise HTTPException(status_code=404, detail='Application not found')
    # payload should include start_dt (ISO), end_dt (ISO), attendees (list), location, summary, description
    ics_url = _create_ics({
        'start_dt': payload.get('start_dt'),
        'end_dt': payload.get('end_dt'),
        'summary': payload.get('summary', f'Interview: {app_obj.applicant_name}'),
        'description': payload.get('description',''),
        'location': payload.get('location','')
    })
    # create Interview record
    interview = models.Interview(application_id=app_id, scheduled_at=datetime.fromisoformat(payload.get('start_dt')), duration_minutes=payload.get('duration_minutes',60), panel=','.join(payload.get('panel',[])), location=payload.get('location'))
    db.add(interview)
    db.commit()
    db.refresh(interview)
    return { 'invite_url': ics_url, 'interview': interview }


@router.post('/assessments/score')
def score_assessment(payload: dict, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    # payload: { application_id, name, answers: {q1: 'a', q2:'b'}, key: {q1:'a', q2:'c'} }
    answers = payload.get('answers', {})
    key = payload.get('key', {})
    total = len(key)
    correct = 0
    for q, correct_a in key.items():
        if answers.get(q) is not None and str(answers.get(q)).strip().lower() == str(correct_a).strip().lower():
            correct += 1
    score = (correct / total * 100) if total > 0 else 0
    assessment = models.Assessment(application_id=payload.get('application_id'), name=payload.get('name'), score=score, results_url=None, completed_at=datetime.utcnow())
    db.add(assessment)
    db.commit()
    db.refresh(assessment)
    return { 'score': score, 'assessment': assessment }


@router.get('/pipeline')
def pipeline(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    # Return applications grouped by latest stage
    apps = db.query(models.Application).all()
    pipeline = {}
    for app in apps:
        latest = db.query(models.ApplicationStage).filter(models.ApplicationStage.application_id == app.id).order_by(models.ApplicationStage.updated_at.desc()).first()
        stage = latest.stage if latest else 'new'
        pipeline.setdefault(stage, []).append({ 'application': app, 'latest_stage': latest })
    return pipeline
