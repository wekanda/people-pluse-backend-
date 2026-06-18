import inspect
import os
from dotenv import load_dotenv
import bcrypt
from datetime import datetime, timedelta
from functools import wraps
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from database import get_db
import models

load_dotenv()
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-this")
ALGORITHM = "HS256"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def get_password_hash(password: str) -> str:
    if isinstance(password, str):
        password = password.encode('utf-8')
    if len(password) > 72:
        password = password[:72]
    return bcrypt.hashpw(password, bcrypt.gensalt()).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    plain = plain_password.encode('utf-8')
    if len(plain) > 72:
        plain = plain[:72]
    return bcrypt.checkpw(plain, hashed_password.encode('utf-8'))

def authenticate_user(db: Session, email: str, password: str):
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user or not verify_password(password, user.hashed_password):
        return False
    return user

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    # Ensure 'sub' is a string
    if "sub" in to_encode and not isinstance(to_encode["sub"], str):
        to_encode["sub"] = str(to_encode["sub"])
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        user_id = int(user_id)  # Convert back to int for database query
    except (JWTError, ValueError) as e:
        print(f"JWT validation error: {e}")
        raise credentials_exception
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user is None:
        raise credentials_exception
    return user


# ==================== PHASE 1: ROLE-BASED ACCESS CONTROL ====================

def require_role(*allowed_roles: str):
    """Decorator to enforce role-based access control.
    
    Usage:
        @require_role("hr_admin", "project_manager")
        def get_employees(current_user: User = Depends(get_current_user)):
            pass
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, current_user: models.User = Depends(get_current_user), **kwargs):
            if current_user.role not in allowed_roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied. Required role(s): {', '.join(allowed_roles)}"
                )
            if inspect.iscoroutinefunction(func):
                return await func(*args, current_user=current_user, **kwargs)
            return func(*args, current_user=current_user, **kwargs)
        return wrapper
    return decorator


def check_role(current_user: models.User, *required_roles: str) -> bool:
    """Check if user has one of the required roles."""
    return current_user.role in required_roles


def check_permission(current_user: models.User, permission: str) -> bool:
    """Check if user has permission based on role.
    
    Permissions matrix:
    - hr_admin: all
    - project_manager: employees (team only), leave (approve team), timesheet
    - staff: own data only, leave (request own), timesheet (own)
    """
    permissions = {
        "hr_admin": [
            "manage_employees", "manage_users", "manage_leave", "manage_documents",
            "manage_timesheets", "manage_appraisals", "manage_recruitment",
            "manage_payroll", "view_reports", "manage_access"
        ],
        "project_manager": [
            "view_team_employees", "approve_leave", "view_team_timesheets",
            "manage_team_timesheets", "view_team_appraisals"
        ],
        "staff": [
            "view_own_data", "request_leave", "submit_timesheet",
            "view_own_appraisals", "view_own_documents"
        ],
        "pay": [
            "manage_payroll", "generate_payslips", "view_payroll_reports"
        ]
    }
    
    role_permissions = permissions.get(current_user.role, [])
    return permission in role_permissions


def check_employee_access(current_user: models.User, employee_id: int, db: Session) -> bool:
    """Check if user has access to view/modify an employee's data.
    
    Rules:
    - hr_admin: can access all
    - project_manager: can access their team members
    - staff: can access only themselves
    """
    if current_user.role == "hr_admin":
        return True
    
    if current_user.role == "project_manager":
        # Check if employee is in their team
        employee = db.query(models.Employee).filter(models.Employee.id == employee_id).first()
        if employee and current_user.employee_id and \
           db.query(models.Employee).filter(
               models.Employee.id == current_user.employee_id,
               models.Employee.project == employee.project
           ).first():
            return True
        return False
    
    if current_user.role == "staff":
        # Can only access their own record
        return current_user.employee_id == employee_id
    
    return False
