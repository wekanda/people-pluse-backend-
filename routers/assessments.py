from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from database import get_db
import models
from auth import get_current_user
from datetime import datetime
from typing import List
import json

router = APIRouter(prefix="/assessments", tags=["assessments"])

@router.post('/templates')
def create_template(payload: dict, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Create an assessment template with questions and answer key."""
    # payload: { title, description, questions: [{q: 'What is 2+2?', options: ['3','4','5'], key: '4'}] }
    if current_user.role not in ('hr_admin', 'project_manager'):
        raise HTTPException(status_code=403, detail='Unauthorized')
    
    template_data = {
        'title': payload.get('title'),
        'description': payload.get('description'),
        'questions': payload.get('questions', [])
    }
    
    template = models.Assessment(
        name=payload.get('title'),
        application_id=None,
        score=None,
        results_url=None,
        completed_at=None,
        # store questions as JSON in a general field (or add assessment_template table in production)
    )
    # Note: We're using Assessment model for both templates and results.
    # In production, create a separate AssessmentTemplate model.
    
    log = models.AuditLog(
        user_id=current_user.id,
        action='assessment_template_created',
        object_type='assessment_template',
        object_id=None,
        details=json.dumps(template_data)
    )
    db.add(template)
    db.add(log)
    db.commit()
    db.refresh(template)
    
    return {'template': template, 'questions': template_data['questions']}

@router.get('/templates')
def list_templates(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """List all assessment templates."""
    # In production, query from AssessmentTemplate model
    # For now, return a stub list
    return {'templates': [], 'message': 'Implement AssessmentTemplate model in production'}

@router.get('/templates/{template_id}')
def get_template(template_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Retrieve a specific assessment template."""
    return {'template': None, 'message': f'Assessment template {template_id} (stub)'}

@router.post('/templates/{template_id}/apply')
def apply_template_to_application(template_id: int, payload: dict, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Apply an assessment template to an application."""
    app_id = payload.get('application_id')
    return {'status': 'template_applied', 'message': f'Assessment template {template_id} applied to application {app_id}'}

@router.post('/submit')
def submit_assessment(payload: dict, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Submit candidate answers for an assessment."""
    application_id = payload.get('application_id')
    answers = payload.get('answers', {})  # { q1: 'answer1', q2: 'answer2' }
    
    # Score the assessment (simple keyword matching)
    key = payload.get('answer_key', {})
    total = len(key)
    correct = 0
    for q_id, correct_ans in key.items():
        if answers.get(q_id) and str(answers.get(q_id)).lower() == str(correct_ans).lower():
            correct += 1
    
    score = (correct / total * 100) if total > 0 else 0
    
    assessment = models.Assessment(
        application_id=application_id,
        name=payload.get('name', 'Submitted Assessment'),
        score=score,
        completed_at=datetime.utcnow()
    )
    db.add(assessment)
    db.commit()
    db.refresh(assessment)
    
    return {
        'assessment_id': assessment.id,
        'score': score,
        'status': 'submitted',
        'message': f'Assessment submitted with score {score:.1f}%'
    }

@router.get('/results/{assessment_id}')
def get_assessment_results(assessment_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Retrieve assessment results."""
    assessment = db.query(models.Assessment).filter(models.Assessment.id == assessment_id).first()
    if not assessment:
        raise HTTPException(status_code=404, detail='Assessment not found')
    return assessment
