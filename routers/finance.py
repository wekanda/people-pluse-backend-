from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from database import get_db
import models
from auth import get_current_user
from datetime import datetime

router = APIRouter(prefix="/finance", tags=["finance"])


@router.post("/payslips/generate")
def generate_payslip(payload: dict, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    # basic permission check
    if current_user.role not in ("hr_admin", "project_manager", "pay"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    employee_id = payload.get('employee_id')
    period_start = payload.get('period_start')
    period_end = payload.get('period_end')
    gross = float(payload.get('gross_pay', 0))
    tax = float(payload.get('tax', 0))
    deductions = float(payload.get('deductions', 0))

    net = gross - tax - deductions

    payslip = models.Payslip(
        employee_id=employee_id,
        period_start=period_start,
        period_end=period_end,
        gross_pay=gross,
        tax=tax,
        deductions=deductions,
        net_pay=net,
        generated_at=datetime.utcnow(),
        generated_by=current_user.id
    )
    db.add(payslip)
    db.commit()
    db.refresh(payslip)
    return payslip


@router.get("/payslips")
def list_payslips(employee_id: int = None, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    query = db.query(models.Payslip)
    if employee_id:
        query = query.filter(models.Payslip.employee_id == employee_id)
    else:
        # default to user's employee if available
        if current_user.employee_id:
            query = query.filter(models.Payslip.employee_id == current_user.employee_id)
        else:
            # only admin can list all
            if current_user.role not in ("hr_admin",):
                return []
    return query.all()


@router.get('/reports/payslips_summary')
def payslips_summary(start: str = None, end: str = None, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if current_user.role not in ("hr_admin", "project_manager", "pay"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    q = db.query(
        func.count(models.Payslip.id),
        func.coalesce(func.sum(models.Payslip.gross_pay), 0),
        func.coalesce(func.sum(models.Payslip.tax), 0),
        func.coalesce(func.sum(models.Payslip.deductions), 0),
        func.coalesce(func.sum(models.Payslip.net_pay), 0),
    )
    if start:
        q = q.filter(models.Payslip.period_start >= start)
    if end:
        q = q.filter(models.Payslip.period_end <= end)

    total_count, total_gross, total_tax, total_deductions, total_net = q.one()
    return {
        "count": int(total_count),
        "gross": float(total_gross),
        "tax": float(total_tax),
        "deductions": float(total_deductions),
        "net": float(total_net),
    }


@router.get('/reports/payslips_csv')
def payslips_csv(start: str = None, end: str = None, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if current_user.role not in ("hr_admin", "project_manager", "pay"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    query = db.query(models.Payslip)
    if start:
        query = query.filter(models.Payslip.period_start >= start)
    if end:
        query = query.filter(models.Payslip.period_end <= end)

    rows = query.all()

    import io, csv
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "employee_id", "period_start", "period_end", "gross_pay", "tax", "deductions", "net_pay", "generated_at", "pdf_url"])
    for p in rows:
        writer.writerow([p.id, p.employee_id, str(p.period_start), str(p.period_end), p.gross_pay, p.tax, p.deductions, p.net_pay, str(p.generated_at), p.pdf_url])

    output.seek(0)
    from fastapi.responses import StreamingResponse
    return StreamingResponse(iter([output.getvalue().encode('utf-8')]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=payslips.csv"})
