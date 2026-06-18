from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
import models
from auth import get_current_user
from datetime import datetime, date
from datetime import timedelta
from typing import List
import json
import os
import smtplib
from email.message import EmailMessage

router = APIRouter(prefix="/hr", tags=["hr-tools"])


@router.post('/talent_pool')
def add_to_talent_pool(payload: dict, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    # store as an Applicant with source 'talent_pool'
    a = models.Applicant(full_name=payload.get('full_name'), email=payload.get('email'), phone=payload.get('phone'), source='talent_pool', resume_url=payload.get('resume_url'))
    db.add(a); db.commit(); db.refresh(a)
    return a


@router.get('/talent_pool')
def list_talent_pool(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if current_user.role not in ('hr_admin','project_manager'):
        raise HTTPException(status_code=403)
    return db.query(models.Applicant).filter(models.Applicant.source=='talent_pool').all()


@router.get('/referrals')
def list_referrals(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if current_user.role not in ('hr_admin','project_manager'):
        raise HTTPException(status_code=403)
    return db.query(models.Applicant).filter(models.Applicant.source=='referral').all()


@router.post('/referral')
def create_referral(payload: dict, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    # simple: create applicant and record referral in AuditLog
    a = models.Applicant(full_name=payload.get('full_name'), email=payload.get('email'), phone=payload.get('phone'), source='referral')
    db.add(a); db.commit(); db.refresh(a)
    log = models.AuditLog(user_id=current_user.id, action='referral_created', object_type='applicant', object_id=str(a.id), details=str(payload))
    db.add(log); db.commit()
    return a


@router.post('/screen')
def screen_application(payload: dict, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    # payload: { application_id, keywords: ['python','django'] }
    app = db.query(models.Application).filter(models.Application.id==payload.get('application_id')).first()
    if not app:
        raise HTTPException(status_code=404)
    keywords = [k.lower() for k in payload.get('keywords',[])]
    text = (app.cover_letter or '') + ' ' + (app.resume_url or '') + ' ' + (app.cover_letter or '')
    score = 0
    for k in keywords:
        if k in text.lower(): score += 1
    result = { 'application_id': app.id, 'keyword_score': score }
    # create stage
    st = models.ApplicationStage(application_id=app.id, stage='screening', status='scored', note=str(result))
    db.add(st); db.commit(); db.refresh(st)
    return result


def send_email_if_configured(to_email: str, subject: str, body: str) -> bool:
    smtp_host = os.getenv('SMTP_HOST')
    smtp_port = int(os.getenv('SMTP_PORT', '587')) if os.getenv('SMTP_PORT') else 587
    smtp_user = os.getenv('SMTP_USER')
    smtp_password = os.getenv('SMTP_PASSWORD')
    smtp_from = os.getenv('SMTP_FROM', smtp_user or 'no-reply@peoplepluse.com')

    if not smtp_host or not smtp_user or not smtp_password:
        return False

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = smtp_from
    msg['To'] = to_email
    msg.set_content(body)

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as smtp:
            smtp.starttls()
            smtp.login(smtp_user, smtp_password)
            smtp.send_message(msg)
        return True
    except Exception as exc:
        print(f"SMTP send failed: {exc}")
        return False


@router.post('/notify')
def notify_candidate(payload: dict, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    user_email = payload.get('email')
    message = payload.get('message')
    email_sent = False
    if user_email:
        email_sent = send_email_if_configured(
            to_email=user_email,
            subject=payload.get('subject', 'People Plus Notification'),
            body=message
        )

    note = models.Notification(
        user_id=current_user.id,
        message=f"Notify {user_email}: {message}",
        type='candidate_notify',
        read=False
    )
    db.add(note)
    db.commit()
    return {
        'status': 'sent' if email_sent else 'queued',
        'email_sent': email_sent,
        'message': message
    }


@router.post('/offer/generate')
def generate_offer(payload: dict, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    # payload: { application_id, salary, currency, terms }
    offer = models.Offer(application_id=payload.get('application_id'), salary=payload.get('salary'), currency=payload.get('currency','USD'), terms=payload.get('terms'))
    db.add(offer); db.commit(); db.refresh(offer)
    return offer


@router.post('/background/check')
def start_background_check(payload: dict, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    # stub: create BackgroundCheck record and mark pending
    bc = models.BackgroundCheck(application_id=payload.get('application_id'), type=payload.get('type','basic'))
    db.add(bc); db.commit(); db.refresh(bc)
    return bc


@router.get('/analytics/recruitment')
def recruitment_analytics(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    # simple metrics: time-to-fill rough using offers
    total_open = db.query(models.JobPosting).filter(models.JobPosting.status.in_(['open','published'])).count()
    total_applicants = db.query(models.Application).count()
    total_offers = db.query(models.Offer).count()
    return { 'open_positions': total_open, 'total_applicants': total_applicants, 'total_offers': total_offers }


@router.post('/onboarding/checklist')
def create_onboarding_checklist(payload: dict, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    checklist = models.OnboardingChecklist(employee_id=payload.get('employee_id'), application_id=payload.get('application_id'), items_json=payload.get('items_json'))
    db.add(checklist); db.commit(); db.refresh(checklist)
    return checklist


@router.get('/internships')
def list_internships_admin(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if current_user.role not in ('hr_admin','project_manager'):
        raise HTTPException(status_code=403)
    return db.query(models.Internship).all()


@router.get('/offers')
def list_offers(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if current_user.role not in ('hr_admin','project_manager'):
        raise HTTPException(status_code=403)
    return db.query(models.Offer).all()


@router.post('/offer/template')
def create_offer_template(payload: dict, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    # payload: { name, content_template }
    log = models.AuditLog(user_id=current_user.id, action='offer_template_created', object_type='offer_template', object_id=None, details=payload.get('name'))
    db.add(log); db.commit()
    return {'template_id': 'template_' + str(int(datetime.utcnow().timestamp())), 'name': payload.get('name'), 'content': payload.get('content_template')}


@router.post('/offer/sign')
def request_offer_signature(payload: dict, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    # Stub for DocuSign integration
    # payload: { offer_id, candidate_email }
    offer_id = payload.get('offer_id')
    # TODO: In production, call DocuSign API to send for signature
    log = models.AuditLog(user_id=current_user.id, action='offer_signature_requested', object_type='offer', object_id=str(offer_id), details=f"Candidate: {payload.get('candidate_email')}")
    db.add(log); db.commit()
    return {'status': 'signature_requested_stub', 'message': 'Offer sent for signature (DocuSign integration stub)'}


@router.get('/background_checks')
def list_background_checks(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if current_user.role not in ('hr_admin','project_manager'):
        raise HTTPException(status_code=403)
    return db.query(models.BackgroundCheck).all()


@router.post('/background/status')
def update_background_check_status(payload: dict, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    # payload: { check_id, status: 'pending' | 'in_progress' | 'passed' | 'failed' }
    check_id = payload.get('check_id')
    status = payload.get('status', 'pending')
    check = db.query(models.BackgroundCheck).filter(models.BackgroundCheck.id == check_id).first()
    if not check:
        raise HTTPException(status_code=404)
    check.status = status
    db.add(check); db.commit()
    log = models.AuditLog(user_id=current_user.id, action='background_check_updated', object_type='background_check', object_id=str(check_id), details=f"Status: {status}")
    db.add(log); db.commit()
    return check


@router.get('/compliance/consent')
def get_consent_status(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    # Check if user has provided consent for data processing
    log = db.query(models.AuditLog).filter(models.AuditLog.user_id == current_user.id, models.AuditLog.action == 'consent_provided').first()
    return {'consent_provided': log is not None, 'message': 'Compliance: Data processing consent status'}


@router.post('/compliance/consent')
def record_consent(payload: dict, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    # Record user consent for data processing, GDPR compliance
    log = models.AuditLog(user_id=current_user.id, action='consent_provided', object_type='compliance', object_id=None, details=f"Consent given at {datetime.utcnow()}")
    db.add(log); db.commit()
    return {'status': 'consent_recorded', 'message': 'Compliance: User consent recorded'}


@router.get('/audit_log')
def get_audit_log(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if current_user.role not in ('hr_admin',):
        raise HTTPException(status_code=403, detail='Only HR Admins can view audit logs')
    # Return recent audit entries
    return db.query(models.AuditLog).order_by(models.AuditLog.created_at.desc()).limit(100).all()


@router.post('/alerts/scan_contracts')
def scan_contract_expiry_and_create_notifications(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """
    Scan for contracts expiring in the next 30/60/90 days and create notifications
    for HR admins and project managers.
    """
    today = date.today()
    notifications_created = 0
    recipients = db.query(models.User).filter(models.User.role.in_(['hr_admin', 'project_manager'])).all()
    if not recipients:
        return {"message": "No HR or manager users to notify", "created": 0}

    ranges = [30, 60, 90]
    for days in ranges:
        window_end = today + timedelta(days=days)
        expiring = db.query(models.Employee).filter(models.Employee.contract_end.between(today, window_end)).all()
        for emp in expiring:
            # Create a notification for each recipient
            for r in recipients:
                msg = f"Contract for {emp.full_name} (#{emp.file_code}) expires on {emp.contract_end} - within {days} days."
                note = models.Notification(user_id=r.id, message=msg, type='contract_expiry', read=False)
                db.add(note)
                notifications_created += 1
    db.commit()
    return {"message": "Contract expiry scan complete", "created": notifications_created}


@router.get('/onboarding')
def list_onboarding_checklists(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Get all active onboarding checklists."""
    if current_user.role not in ['hr_admin', 'project_manager']:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    checklists = db.query(models.OnboardingChecklist).filter(
        models.OnboardingChecklist.status.in_(['Active', 'In Progress'])
    ).all()
    
    result = []
    for checklist in checklists:
        try:
            items = json.loads(checklist.items_json) if checklist.items_json else []
        except:
            items = []
        
        result.append({
            'id': checklist.id,
            'candidate_name': checklist.candidate_name,
            'status': checklist.status,
            'created_at': str(checklist.created_at),
            'items_json': items
        })
    
    return result


@router.get('/onboarding/{checklist_id}')
def get_onboarding_checklist(checklist_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Get specific onboarding checklist."""
    if current_user.role not in ['hr_admin', 'project_manager']:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    checklist = db.query(models.OnboardingChecklist).filter(models.OnboardingChecklist.id == checklist_id).first()
    if not checklist:
        raise HTTPException(status_code=404, detail="Checklist not found")
    
    try:
        items = json.loads(checklist.items_json) if checklist.items_json else []
    except:
        items = []
    
    return {
        'id': checklist.id,
        'candidate_name': checklist.candidate_name,
        'status': checklist.status,
        'created_at': str(checklist.created_at),
        'items_json': items
    }


@router.put('/onboarding/{checklist_id}')
def update_onboarding_checklist(checklist_id: int, payload: dict, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Update onboarding checklist items."""
    if current_user.role not in ['hr_admin', 'project_manager']:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    checklist = db.query(models.OnboardingChecklist).filter(models.OnboardingChecklist.id == checklist_id).first()
    if not checklist:
        raise HTTPException(status_code=404, detail="Checklist not found")
    
    items = payload.get('items_json', [])
    checklist.items_json = json.dumps(items)
    
    # Mark as complete if all items are done
    if items and all(item.get('completed', False) for item in items):
        checklist.status = 'Completed'
    else:
        checklist.status = 'In Progress'
    
    db.commit()
    db.refresh(checklist)
    
    return {
        'id': checklist.id,
        'status': checklist.status,
        'message': 'Checklist updated'
    }


@router.post('/onboarding/create')
def create_onboarding_checklist(payload: dict, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Create a new onboarding checklist for a new hire."""
    if current_user.role not in ['hr_admin', 'project_manager']:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # Default onboarding tasks
    default_items = [
        {'task': 'Complete employment contract', 'notes': 'Sign and file contract', 'completed': False},
        {'task': 'IT Setup', 'notes': 'Email, laptop, access credentials', 'completed': False},
        {'task': 'Benefits enrollment', 'notes': 'Health insurance, retirement', 'completed': False},
        {'task': 'Orientation training', 'notes': 'Company policies, procedures', 'completed': False},
        {'task': 'Department introduction', 'notes': 'Meet team members', 'completed': False},
        {'task': 'First week check-in', 'notes': 'One-on-one with manager', 'completed': False},
        {'task': 'System access verification', 'notes': 'Confirm all systems working', 'completed': False},
        {'task': 'Document collection', 'notes': 'Tax forms, ID verification', 'completed': False},
    ]
    
    items_json = json.dumps(payload.get('items_json', default_items))
    
    checklist = models.OnboardingChecklist(
        candidate_name=payload.get('candidate_name', 'New Employee'),
        status='Active',
        items_json=items_json,
        created_at=datetime.utcnow()
    )
    
    db.add(checklist)
    db.commit()
    db.refresh(checklist)
    
    return {
        'id': checklist.id,
        'candidate_name': checklist.candidate_name,
        'status': checklist.status,
        'message': 'Checklist created'
    }
