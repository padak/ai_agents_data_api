from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import jwt
from typing import Annotated

from app.core.config import settings

router = APIRouter()

@router.post("/token")
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
):
    """Generate JWT token for admin access"""
    if (form_data.username != settings.ADMIN_USERNAME or 
        form_data.password != settings.ADMIN_PASSWORD):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create access token
    data = {"sub": form_data.username}
    expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    expire = expires_delta.total_seconds()
    
    access_token = jwt.encode(
        data, settings.JWT_SECRET_KEY, algorithm="HS256"
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": expire
    } 