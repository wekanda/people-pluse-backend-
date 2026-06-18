from sqlalchemy import Column, Integer, String, Date, DateTime, Boolean, Float, ForeignKey, Text
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    full_name = Column(String)
    role = Column(String)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=True)

class Employee(Base):
    __tablename__ = "employees"
    id = Column(Integer, primary_key=True, index=True)
    file_code = Column(String, unique=True, index=True)
    full_name = Column(String)
    project = Column(String)
    status = Column(String)
    position = Column(String)
    contact_number = Column(String)
    location = Column(String)
    locker = Column(String)
    date_of_appointment = Column(Date)
    contract_start = Column(Date)
    contract_end = Column(Date)
    contract_review_date = Column(Date)
    probation_end = Column(Date)
    employment_type = Column(String)
    notice_period = Column(String)
    missing_app_resume = Column(Boolean, default=False)
    missing_appointment_letter = Column(Boolean, default=False)
    missing_academic_docs = Column(Boolean, default=False)
    missing_recruitment_notes = Column(Boolean, default=False)
    missing_staff_id_form = Column(Boolean, default=False)
    missing_performance_appraisals = Column(Boolean, default=False)
    missing_national_id = Column(Boolean, default=False)
    missing_policy_declaration = Column(Boolean, default=False)
    missing_end_of_contract_notice = Column(Boolean, default=False)
    photo_url = Column(String, nullable=True)

    leave_requests = relationship("LeaveRequest", back_populates="employee")
    timesheets = relationship("Timesheet", back_populates="employee")
    appraisals = relationship("PerformanceAppraisal", back_populates="employee")

class LeaveRequest(Base):
    __tablename__ = "leave_requests"
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"))
    leave_type_id = Column(Integer, ForeignKey("leave_types.id"), nullable=True)
    start_date = Column(Date)
    end_date = Column(Date)
    days = Column(Float)
    reason = Column(String)
    type = Column(String)
    status = Column(String)
    submitted_at = Column(DateTime, default=datetime.utcnow)
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    employee = relationship("Employee", back_populates="leave_requests")

class Timesheet(Base):
    __tablename__ = "timesheets"
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"))
    date = Column(Date)
    hours_worked = Column(Float, default=0)
    overtime_hours = Column(Float, default=0)
    approved = Column(Boolean, default=False)
    employee = relationship("Employee", back_populates="timesheets")

class PerformanceAppraisal(Base):
    __tablename__ = "performance_appraisals"
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"))
    position = Column(String)
    duration_in_position = Column(String)
    achievements = Column(Text)
    challenges = Column(Text)
    point_outs = Column(Text)
    appraisal_date = Column(Date)
    reviewer_id = Column(Integer, ForeignKey("users.id"))
    employee = relationship("Employee", back_populates="appraisals")

class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    message = Column(String)
    type = Column(String)
    read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Requisition(Base):
    __tablename__ = "requisitions"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    department = Column(String)
    location = Column(String)
    job_description = Column(Text)
    justification = Column(Text)
    vacancy_count = Column(Integer, default=1)
    budget = Column(Float, default=0.0)
    requested_by = Column(Integer, ForeignKey("users.id"))
    status = Column(String, default="pending")
    priority = Column(String, default="normal")
    created_at = Column(DateTime, default=datetime.utcnow)
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)


class RequisitionApproval(Base):
    __tablename__ = "requisition_approvals"
    id = Column(Integer, primary_key=True, index=True)
    requisition_id = Column(Integer, ForeignKey("requisitions.id"))
    approver_id = Column(Integer, ForeignKey("users.id"))
    action = Column(String)  # approved / rejected
    note = Column(Text, nullable=True)
    acted_at = Column(DateTime, default=datetime.utcnow)


class JobPosting(Base):
    __tablename__ = "job_postings"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    description = Column(Text)
    department = Column(String)
    location = Column(String)
    posted_at = Column(DateTime, default=datetime.utcnow)
    closing_date = Column(Date)
    status = Column(String, default="open")
    created_by = Column(Integer, ForeignKey("users.id"))
    is_internal = Column(Boolean, default=False)
    channels = Column(String, nullable=True)  # comma separated channels
    published_at = Column(DateTime, nullable=True)
    external_posted = Column(Boolean, default=False)
    external_channels = Column(String, nullable=True)


class Application(Base):
    __tablename__ = "applications"
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("job_postings.id"))
    applicant_name = Column(String)
    email = Column(String)
    resume_url = Column(String, nullable=True)
    cover_letter = Column(Text, nullable=True)
    status = Column(String, default="submitted")
    applied_at = Column(DateTime, default=datetime.utcnow)
    reviewer_id = Column(Integer, ForeignKey("users.id"), nullable=True)


class Internship(Base):
    __tablename__ = "internships"
    id = Column(Integer, primary_key=True, index=True)
    candidate_name = Column(String)
    email = Column(String)
    start_date = Column(Date)
    end_date = Column(Date)
    mentor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    status = Column(String, default="planned")
    notes = Column(Text, nullable=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=True)


class Payslip(Base):
    __tablename__ = "payslips"
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"))
    period_start = Column(Date)
    period_end = Column(Date)
    gross_pay = Column(Float, default=0.0)
    tax = Column(Float, default=0.0)
    deductions = Column(Float, default=0.0)
    net_pay = Column(Float, default=0.0)
    generated_at = Column(DateTime, default=datetime.utcnow)
    pdf_url = Column(String, nullable=True)
    generated_by = Column(Integer, ForeignKey("users.id"), nullable=True)


Employee.payslips = relationship("Payslip", backref="employee")


class Applicant(Base):
    __tablename__ = "applicants"
    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String)
    email = Column(String, index=True)
    phone = Column(String, nullable=True)
    source = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    resume_url = Column(String, nullable=True)
    consent = Column(Boolean, default=True)


class ApplicationStage(Base):
    __tablename__ = "application_stages"
    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id"))
    stage = Column(String)
    status = Column(String)
    note = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow)


class Interview(Base):
    __tablename__ = "interviews"
    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id"))
    scheduled_at = Column(DateTime)
    duration_minutes = Column(Integer, default=60)
    panel = Column(String, nullable=True)  # comma separated user ids
    location = Column(String, nullable=True)
    status = Column(String, default="scheduled")


class Assessment(Base):
    __tablename__ = "assessments"
    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id"))
    name = Column(String)
    score = Column(Float, nullable=True)
    results_url = Column(String, nullable=True)
    completed_at = Column(DateTime, nullable=True)


class Feedback(Base):
    __tablename__ = "feedback"
    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id"))
    reviewer_id = Column(Integer, ForeignKey("users.id"))
    rating = Column(Integer, nullable=True)
    comments = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Offer(Base):
    __tablename__ = "offers"
    id = Column(Integer, primary_key=True, index=True)
    applicant_id = Column(Integer, ForeignKey("applicants.id"))
    position = Column(String)
    salary = Column(Float, nullable=True)
    start_date = Column(Date, nullable=True)
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)


# ==================== PHASE 1: LEAVE MANAGEMENT ====================

class LeaveType(Base):
    """Define leave types and their entitlements per Ugandan labor standards."""
    __tablename__ = "leave_types"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    annual_entitlement_days = Column(Float)
    description = Column(String, nullable=True)
    is_paid = Column(Boolean, default=True)
    requires_manager_approval = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class LeaveBalance(Base):
    """Track leave balance for each employee per leave type."""
    __tablename__ = "leave_balances"
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), index=True)
    leave_type_id = Column(Integer, ForeignKey("leave_types.id"), index=True)
    balance = Column(Float, default=0.0)
    accrued = Column(Float, default=0.0)
    used = Column(Float, default=0.0)
    last_updated = Column(DateTime, default=datetime.utcnow)
    employee = relationship("Employee", backref="leave_balances")
    leave_type = relationship("LeaveType")


# ==================== PHASE 1: e-PFile (EMPLOYEE DOCUMENTS) ====================

class DocumentType(Base):
    """Define required document types for personnel files."""
    __tablename__ = "document_types"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    category = Column(String)
    is_required = Column(Boolean, default=True)
    expiry_period_days = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class EmployeeDocument(Base):
    """Track documents per employee for e-PFile."""
    __tablename__ = "employee_documents"
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), index=True)
    document_type_id = Column(Integer, ForeignKey("document_types.id"), index=True)
    file_path = Column(String)
    file_name = Column(String)
    uploaded_by = Column(Integer, ForeignKey("users.id"))
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    approved = Column(Boolean, default=False)
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    expiry_date = Column(Date, nullable=True)
    is_expired = Column(Boolean, default=False)
    notes = Column(Text, nullable=True)
    employee = relationship("Employee", backref="documents")
    document_type = relationship("DocumentType")
    uploader = relationship("User", foreign_keys=[uploaded_by], backref="uploaded_documents")
    approver = relationship("User", foreign_keys=[approved_by], backref="approved_documents")
    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id"))
    offered_at = Column(DateTime, default=datetime.utcnow)
    salary = Column(Float, nullable=True)
    currency = Column(String, default='USD')
    terms = Column(Text, nullable=True)
    status = Column(String, default='pending')
    signed_at = Column(DateTime, nullable=True)


class BackgroundCheck(Base):
    __tablename__ = "background_checks"
    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id"))
    type = Column(String)
    status = Column(String, default='pending')
    result = Column(Text, nullable=True)
    checked_at = Column(DateTime, nullable=True)


class OnboardingChecklist(Base):
    __tablename__ = "onboarding_checklists"
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=True)
    items_json = Column(Text, nullable=True)
    completed = Column(Boolean, default=False)
    completed_at = Column(DateTime, nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String)
    object_type = Column(String)
    object_id = Column(String)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
