from fastapi.testclient import TestClient
from backend.main import app
import openpyxl
import io

client = TestClient(app)


def make_sample_excel():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(['file code', 'period start', 'period end', 'gross_pay', 'tax', 'deductions'])
    ws.append(['EMP001', '2023-01-01', '2023-01-31', 2000, 200, 50])
    bio = io.BytesIO()
    wb.save(bio)
    bio.seek(0)
    return bio


def test_payslip_upload_unauthenticated():
    res = client.post('/upload/payslips_excel', files={'file': ('payslips.xlsx', make_sample_excel(), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')})
    assert res.status_code in (401, 403)


# Note: authenticated test requires token; manual integration test recommended
