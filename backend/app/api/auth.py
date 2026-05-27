from datetime import timedelta
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, Field

from app.db.database import get_db
from app.db.models import User
from app.core import security
from app.api import deps
from app.core.mail import send_reset_password_email

router = APIRouter()

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)

class PasswordRecovery(BaseModel):
    email: EmailStr

class ResetPassword(BaseModel):
    token: str
    new_password: str = Field(min_length=8)

class UserResponse(BaseModel):
    id: str
    email: str
    is_active: bool

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

@router.post("/register", response_model=UserResponse)
def register_user(user_in: UserCreate, db: Session = Depends(get_db)) -> Any:
    """
    Create new user.
    """
    email_lower = user_in.email.lower()
    user = db.query(User).filter(User.email == email_lower).first()
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system.",
        )
    user = User(
        email=email_lower,
        hashed_password=security.get_password_hash(user_in.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login/access-token", response_model=Token)
def login_access_token(
    db: Session = Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends()
) -> Any:
    """
    OAuth2 compatible token login, get an access token for future requests
    """
    email_lower = form_data.username.lower()
    user = db.query(User).filter(User.email == email_lower).first()
    if not user or not security.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    elif not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    access_token_expires = timedelta(minutes=security.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    return {
        "access_token": security.create_access_token(
            user.id, expires_delta=access_token_expires
        ),
        "token_type": "bearer",
    }


@router.get("/users/me", response_model=UserResponse)
def read_users_me(
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Get current user.
    """
    return current_user

@router.post("/password-recovery")
async def recover_password(body: PasswordRecovery, db: Session = Depends(get_db)):
    """
    Password Recovery.
    """
    user = db.query(User).filter(User.email == body.email.lower()).first()
    
    if user:
        token = security.generate_password_reset_token(email=user.email)
        await send_reset_password_email(email_to=user.email, token=token)

    return {"msg": "E-mail z linkiem resetującym hasło został wysłany."}


@router.post("/reset-password")
def reset_password(body: ResetPassword, db: Session = Depends(get_db)):
    """
    Reset password.
    """
    email = security.verify_password_reset_token(body.token)
    if not email:
        raise HTTPException(status_code=400, detail="Invalid or expired token.")
        
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
        
    user.hashed_password = security.get_password_hash(body.new_password)
    db.commit()
    
    return {"msg": "Password updated successfully."}
