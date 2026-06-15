from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
import models
from auth import get_current_user
from datetime import datetime
from typing import Optional
import json

router = APIRouter(prefix="/documents", tags=["documents"])

# Document templates
TEMPLATES = {
    "appointment_letter": """
APPOINTMENT LETTER

Date: {date}

To: {employee_name}
    {employee_email}
    {employee_address}

Dear {employee_name},

We are pleased to offer you the position of {position} at People Plus HR Systems.

Position Details:
- Position: {position}
- Department: {department}
- Start Date: {start_date}
- Employment Type: {employment_type}
- Reporting To: {manager_name}

Compensation:
- Annual Salary: KES {salary}
- Benefits: {benefits}

Terms of Employment:
1. This is an employment relationship subject to the laws of Kenya.
2. Your employment is subject to satisfactory completion of background checks and verification.
3. You will be subject to our company policies as per the employee handbook.

We look forward to welcoming you to our team.

Best regards,

Human Resources Manager
People Plus HR Systems
""",

    "offer_letter": """
OFFER OF EMPLOYMENT

Date: {date}

Dear {applicant_name},

We are pleased to make you a formal offer of employment for the position of {position} at People Plus HR Systems.

Position Details:
- Job Title: {position}
- Department: {department}
- Location: {location}
- Proposed Start Date: {start_date}
- Employment Type: {employment_type}

Compensation Package:
- Base Salary: KES {base_salary} per annum
- Other Benefits: {benefits}
- Annual Leave: 21 days

Your responsibilities will include:
{responsibilities}

Conditions of Employment:
1. This offer is conditional upon successful background verification.
2. You are required to provide proof of educational qualifications.
3. A medical examination may be required.
4. You will be required to sign our standard employment contract.

If you accept this offer, please confirm your acceptance by {acceptance_deadline}.

We look forward to your response.

Sincerely,

Human Resources Department
People Plus HR Systems
""",

    "contract": """
EMPLOYMENT AGREEMENT

This Employment Agreement is entered into on {date} between:

PEOPLE PLUS HR SYSTEMS (hereinafter "Employer")

AND

{employee_name} (hereinafter "Employee")

WHEREAS, the Employer wishes to employ the Employee and the Employee wishes to be employed by the Employer on the terms and conditions set forth herein:

1. POSITION
The Employee shall be employed as a {position} in the {department} department.

2. TERM
The employment shall commence on {start_date} and shall continue until terminated as per the provisions herein.

3. COMPENSATION
The Employee shall receive an annual salary of KES {salary}, payable in monthly installments.

4. BENEFITS
The Employee shall be entitled to:
- Annual leave of 21 days
- Health insurance coverage
- Pension contributions
- Other benefits as per company policy

5. DUTIES AND RESPONSIBILITIES
The Employee shall perform duties as assigned by management consistent with the position of {position}.

6. CONFIDENTIALITY
The Employee agrees to maintain confidentiality of all company information.

7. TERMINATION
Either party may terminate this agreement by giving 30 days written notice.

8. DISPUTE RESOLUTION
Disputes arising from this agreement shall be governed by the laws of Kenya.

IN WITNESS WHEREOF, the parties have executed this Agreement as of the date first written above.

EMPLOYER:                          EMPLOYEE:

_____________________            _____________________
{employer_name}                  {employee_name}
Authorized Signatory             

Date: _______________            Date: _______________
""",

    "separation_letter": """
LETTER OF SEPARATION / TERMINATION OF EMPLOYMENT

Date: {date}

To: {employee_name}
    {employee_email}

Dear {employee_name},

This letter confirms the termination of your employment with People Plus HR Systems effective {termination_date}.

Reason for Termination: {reason}

Final Paycheck:
Your final paycheck, including accrued leave and any severance as per company policy, will be processed by {payout_date}.

Items to Return:
Please ensure the following items are returned on or before your last day:
- Employee ID Card
- Office Access Card
- Company Equipment (Laptop, Phone, etc.)
- Any other company property

Outstanding Benefits:
{benefits_info}

Reference:
We appreciate your service and will provide employment reference upon request.

If you have any questions, please contact the Human Resources department.

Sincerely,

Human Resources Manager
People Plus HR Systems
"""
}


@router.post("/generate")
def generate_document(payload: dict, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Generate a document from template (appointment letter, contract, offer letter, etc.)"""
    if current_user.role not in ["hr_admin", "project_manager"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    template_type = payload.get("template_type", "").lower()
    if template_type not in TEMPLATES:
        raise HTTPException(status_code=400, detail=f"Template not found. Available: {', '.join(TEMPLATES.keys())}")
    
    template = TEMPLATES[template_type]
    
    # Get employee/applicant details
    employee_id = payload.get("employee_id")
    applicant_id = payload.get("applicant_id")
    
    employee = None
    applicant = None
    if employee_id:
        employee = db.query(models.Employee).filter(models.Employee.id == employee_id).first()
    if applicant_id:
        applicant = db.query(models.Application).filter(models.Application.id == applicant_id).first()
    
    # Build substitution context
    context = {
        "date": datetime.utcnow().strftime("%d %B %Y"),
        "employee_name": employee.full_name if employee else applicant.applicant_name if applicant else "",
        "employee_email": employee.email if employee else applicant.email if applicant else "",
        "employee_address": getattr(employee, 'address', 'Not provided') if employee else "",
        "applicant_name": applicant.applicant_name if applicant else "",
        "position": payload.get("position", "Position Title"),
        "department": payload.get("department", "Department"),
        "location": payload.get("location", "Not specified"),
        "start_date": payload.get("start_date", "To be confirmed"),
        "employment_type": payload.get("employment_type", "Full-time"),
        "salary": payload.get("salary", "Confidential"),
        "base_salary": payload.get("base_salary", "Confidential"),
        "manager_name": payload.get("manager_name", "Your Manager"),
        "employer_name": payload.get("employer_name", "HR Director"),
        "benefits": payload.get("benefits", "As per company policy"),
        "responsibilities": payload.get("responsibilities", "As defined by management"),
        "acceptance_deadline": payload.get("acceptance_deadline", "Within 5 business days"),
        "termination_date": payload.get("termination_date", "To be confirmed"),
        "payout_date": payload.get("payout_date", "Within 30 days"),
        "reason": payload.get("reason", "As per company notice"),
        "benefits_info": payload.get("benefits_info", "As per final settlement"),
    }
    
    # Generate document by substituting placeholders
    try:
        html_content = template.format(**context)
    except KeyError as e:
        raise HTTPException(status_code=400, detail=f"Missing required field: {str(e)}")
    
    # Log document generation
    log = models.AuditLog(
        user_id=current_user.id,
        action="document_generated",
        object_type=template_type,
        object_id=str(employee_id or applicant_id),
        details=json.dumps(context)
    )
    db.add(log)
    db.commit()
    
    return {
        "template_type": template_type,
        "content": html_content,
        "generated_at": datetime.utcnow().isoformat(),
        "generated_by": current_user.full_name
    }


@router.get("/templates")
def list_available_templates(current_user=Depends(get_current_user)):
    """List all available document templates"""
    if current_user.role not in ["hr_admin", "project_manager"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    return {
        "templates": list(TEMPLATES.keys()),
        "count": len(TEMPLATES),
        "descriptions": {
            "appointment_letter": "Letter confirming a new employee's appointment",
            "offer_letter": "Formal job offer to a candidate",
            "contract": "Employment contract with terms and conditions",
            "separation_letter": "Formal separation/termination letter"
        }
    }
