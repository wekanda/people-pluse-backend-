from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from datetime import date
from pydantic import BaseModel
import models
from database import get_db
from auth import get_current_user
from typing import List
import os
from pathlib import Path
import shutil

router = APIRouter(prefix="/api/documents", tags=["documents"])

class DocumentCreate(BaseModel):
    employee_id: int
    document_type: str
    file_path: str

class DocumentResponse(BaseModel):
    id: int
    employee_id: int
    document_type: str
    created_at: date
    class Config:
        from_attributes = True

@router.post("/upload")
async def upload_doc(employee_id: int, document_type: str, file: UploadFile = File(...), db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    # Store file on disk under ./uploads/<employee_id>/
    upload_root = Path("uploads")
    dest_dir = upload_root / str(employee_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    safe_filename = f"{document_type}_{file.filename}"
    dest_path = dest_dir / safe_filename
    try:
        with dest_path.open("wb") as out_file:
            shutil.copyfileobj(file.file, out_file)
    finally:
        file.file.close()

    # Optionally record audit or link into Employee record (not implemented here)
    return {"message": f"Document {document_type} uploaded successfully", "path": str(dest_path)}

@router.get("/employee/{employee_id}")
def get_employee_documents(employee_id: int, db: Session = Depends(get_db)):
    employee = db.query(models.Employee).filter(models.Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    missing_docs = []
    doc_fields = {
        "Application/Resume": employee.missing_app_resume,
        "Appointment Letter": employee.missing_appointment_letter,
        "Academic Docs": employee.missing_academic_docs,
        "Staff ID Form": employee.missing_staff_id_form,
        "Performance Appraisals": employee.missing_performance_appraisals,
        "National ID": employee.missing_national_id,
        "Policy Declaration": employee.missing_policy_declaration,
        "End of Contract Notice": employee.missing_end_of_contract_notice,
    }
    
    for doc_name, is_missing in doc_fields.items():
        if is_missing:
            missing_docs.append(doc_name)
    
    return {"employee_id": employee_id, "full_name": employee.full_name, "missing_documents": missing_docs}
