from fastapi import APIRouter, Depends, HTTPException, status, Header
from app.crud import create_data, update_data, get_single_data
from app.model import Admin, Staff
from typing import Optional, Dict, Any
import os
from passlib.context import CryptContext
from jose import jwt, JWTError
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta
from sqlmodel import Session, select
from app.database import engine
from typing import List, Union
import random
import redis.asyncio as redis
import json
from app.services.mailer import send_mail
import secrets
from jose.exceptions import JWTError, ExpiredSignatureError

# define all auth routes
router = APIRouter(prefix="/auth")
# config 
REDIS_PORT = os.getenv("REDIS_PORT")
ACCESS_TOKEN_EXPIRE_DAYS = 30
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"

redis_client = redis.Redis(
    host='localhost',
    port=REDIS_PORT,
    db=int(0),
    decode_responses=True
)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Pydantic models for request/response
class LoginData(BaseModel):
    email: EmailStr
    password: str
    role: str

class AdminSignUp(BaseModel):
    email: EmailStr
    password: str
    role: str 

class TokenResponse(BaseModel):
    token: str
    token_type: str
    email: str
    role: str
    admin_id: Optional[int] = None  # Make optional
    staff_id: Optional[int] = None 


# login admin
@router.post('/login', response_model=TokenResponse)
async def login(user_data: LoginData):
    # Find user by email based on role
    with Session(engine) as session:
        user = None
        role = user_data.role.lower()  # Normalize role to lowercase
        
        if role == "admin":
            user = session.exec(
                select(Admin).where(Admin.email == user_data.email)
            ).first()
            user_role = "admin" 
        else:
            user = session.exec(
                select(Staff).where(Staff.email == user_data.email)
            ).first()
            user_role = user.role if user else None
        
        # Check if user exists
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        # Verify password
        if not verify_password(user_data.password, user.password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        # Create JWT token with appropriate role
        token = create_jwt_token(user.email, user_role)
        
        # Update user's jwt_token in database
        user.jwt_token = token
        session.add(user)
        session.commit()
        
        # Return appropriate response based on role
        response_data = {
            "token": token,
            "token_type": "bearer",
            "email": user.email,
            "role": user_role,
        }
        
        # Add role-specific ID to response
        if role == "admin":
            response_data["admin_id"] = user.id
        else:
            response_data["staff_id"] = user.id
        
        return response_data
    
# sign up admin
@router.post('/signup')
async def sign_up(admin_data: AdminSignUp):
    # Check if admin already exists
    with Session(engine) as session:
        existing_admin = session.exec(
            select(Admin).where(Admin.email == admin_data.email)
        ).first()
        
        if existing_admin:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Admin with this email already exists"
            )
        
        # Hash password
        hashed_password = hash_password(admin_data.password)
        
        # Create new admin
        new_admin = Admin(
            email=admin_data.email,
            password=hashed_password,
            role=admin_data.role,
            jwt_token=""  # Will be set after login
        )
        
        session.add(new_admin)
        session.commit()
        session.refresh(new_admin)
        
        # Create JWT token
        token = create_jwt_token(new_admin.email, "admin")
        
        # Update admin's jwt_token
        new_admin.jwt_token = token
        session.add(new_admin)
        session.commit()
        
        return {
            "token": token,
            "token_type": "bearer",
            "email": new_admin.email,
            "admin_id": new_admin.id,
            "role": new_admin.role,
        }

class PasswordResetRequest(BaseModel):
    email: EmailStr
    
@router.post('/send_reset_password_link' )
async def send_reset_password_link(request: PasswordResetRequest):
    with Session(engine) as session:
        admin = session.exec(
            select(Admin).where(Admin.email == request.email)
        ).first()
        
    if not admin:
        return {
            "message": "If an account exists with this email, a password reset link has been sent."
        }
    reset_token = secrets.token_urlsafe(32)
    token_expiry = datetime.utcnow() + timedelta(hours=1)
    
    admin.reset_password_token = reset_token
    admin.reset_password_expiry = token_expiry
    admin.updated_at = datetime.utcnow()
    
    session.add(admin)
    session.commit()
    
    frontend_url = "http://localhost:5173" 
    reset_link = f"{frontend_url}/password_reset?token={reset_token}&email={request.email}"
    subject = "Reset Your Password"
    html_content = f"""
    <html>
        <body>
            <h1>Password Reset Request</h1>
            <p>You requested to reset your password. Click the link below to proceed:</p>
            <a href="{reset_link}">{reset_link}</a>
            <p>This link will expire in 1 hour.</p>
            <p>If you didn't request this, please ignore this email.</p>
            <br>
            <p>Best regards,</p>
            <p>Your App Team</p>
        </body>
    </html>
    """

    try:
        await send_mail(
            to=request.email,
            subject=subject,
            html=html_content
        )
    except Exception as e:
        print(f"Error sending email: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send reset email. Please try again later."
        )
    
    return {
        "message": "If an account exists with this email, a password reset link has been sent."
    }

class ResetPassword(BaseModel):
    email: str
    token: str
    new_password: str
    
@router.post('/reset_password' )
async def reset_password(data: ResetPassword):
    with Session(engine) as session:
        admin = session.exec(
            select(Admin).where(Admin.email == data.email)
        ).first()
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No account found with this email address."
        )
    stored_token = admin.reset_password_token
    token_expiry = admin.reset_password_expiry
    
    if not stored_token or stored_token != data.token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token."
        )
    
    # Check if token has expired
    if token_expiry and token_expiry < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset token has expired. Please request a new password reset link."
        )
        
    hashed_password = hash_password(data.new_password)
    
    # Store the hashed password in the admin and clear reset token fields
    admin.password = hashed_password
    admin.reset_password_token = None
    admin.reset_password_expiry = None
    admin.updated_at = datetime.utcnow()
    
    session.add(admin)
    session.commit()
    
    # Generate and store new access token using create_jwt_token(email, role)
    admin_role = admin.role
    access_token = create_jwt_token(data.email, admin_role)
        
    return {
        "message": "Password reset successful",
        "access_token": access_token,
        "token_type": "bearer"
    }

    
def hash_password(password: str) -> str:
    # Fix: Handle bcrypt's 72-byte limit
    password_bytes = password.encode('utf-8')
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
    return pwd_context.hash(password_bytes)

# verify admin password
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

# check authenticity
def create_jwt_token(email: str, role: str, admin_id: Optional[int] = None) -> str:
    expire = datetime.utcnow() + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    to_encode = {"sub": email, "exp": expire, "role": role}
    
    # Embed admin_id if provided
    if admin_id is not None:
        to_encode["admin_id"] = admin_id
    
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def isAuthorized(token: str) -> Optional[Dict[str, Any]]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        role = payload.get("role")
        
        if not email or not role:
            return None
        
        staff_roles = ["receptionist", "supervisor", "manager", "sales_attendant"]
        
        with Session(engine) as session:
            # Check if user is admin
            if role == "admin":
                user = session.exec(select(Admin).where(Admin.email == email)).first()
                if not user:
                    return None
                if user.jwt_token != token:
                    return None
                # Admin is always authorized
                return {
                    "email": user.email,
                    "admin_id": user.id,
                    "role": user.role,
                    "status": True
                }
            
            # Check if user is staff with valid role
            elif role in staff_roles:
                user = session.exec(select(Staff).where(Staff.email == email)).first()
                if not user:
                    return None
                if user.jwt_token != token:
                    return None
                # Verify the role matches what's in the database
                if user.role != role:
                    return None
                return {
                    "email": user.email,
                    "staff_id": user.id,
                    "admin_id": user.admin_id,
                    "role": user.role,  
                    "status": True
                }
            
            else:
                print(f"Invalid role: {role}")
                return None
                
    except ExpiredSignatureError:
        print("Token has expired")
        return None
    except JWTError:
        print("Invalid token")
        return None
    except Exception as e:
        print(f"Authorization error: {str(e)}")
        return None
class OTPVerification(BaseModel):
    email: EmailStr
    otp: str    

# Email configuration (set these as environment variables in production)
class EmailRequest(BaseModel):
    to: EmailStr

def generate_otp() -> str:
    """Generate a 6-digit OTP"""
    return str(random.randint(100000, 999999))

@router.post("/send-verification-email")
async def send_verification_email(email_request: EmailRequest):
    try:
        otp_code = generate_otp()
        await redis_client.delete(f"otp:{email_request.to}") #delete the data attached to the prev key
        key = f"otp:{email_request.to}"

        data = {
            "email": email_request.to,
            "otp_code": otp_code,
            "attempts": 0
        }

        await redis_client.set(
            key,
            json.dumps(data),
            ex=600  # 10 minutes
        )
        # Create email content
        subject = "Your Verification Code"
        message =  f"""
        <html>
            <body>
                <h2>Email Verification</h2>
                <p>Your verification code is:</p>
                <h1 style="color: #2563eb; font-size: 32px; letter-spacing: 5px;">{otp_code}</h1>
                <p>This code will expire in 10 minutes.</p>
                <p>If you didn't request this code, please ignore this email.</p>
                <br>
                <p>Best regards,<br>Your App Team</p>
            </body>
        </html>
        """
        
        # Send email
        email_sent = await send_mail(
            to= email_request.to,
            subject=subject,
            html=message,
            )
        
        return {
                    "message": "Verification code sent successfully",
                    "email": email_request.to,
                    "expires_in": "10 minutes",
                    "status": email_sent
         }
   
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error sending verification email: {str(e)}")
     
MAX_ATTEMPTS = 5
 
@router.post("/verify-otp")
async def verify_otp(verification: OTPVerification):
    email = verification.email
    user_otp = verification.otp

    key = f"otp:{email}"

    stored_data = await redis_client.get(key)

    # Check if OTP exists
    if not stored_data:
        raise HTTPException(status_code=404, detail="OTP expired or not found")

    otp_data = json.loads(stored_data)

    # Check attempt limit
    if otp_data["attempts"] >= MAX_ATTEMPTS:
        await redis_client.delete(key)
        raise HTTPException(status_code=400, detail="Too many failed attempts")

    # Check OTP
    if user_otp == otp_data["otp_code"]:
        await redis_client.delete(key)
        return {
            "message": "OTP verified successfully",
            "email": email,
            "verified": True
        }

    # Wrong OTP → increment attempts
    otp_data["attempts"] += 1
    remaining_attempts = MAX_ATTEMPTS - otp_data["attempts"]

    await redis_client.set(
        key,
        json.dumps(otp_data),
        ex=600  # keep expiration
    )

    raise HTTPException(
        status_code=400,
        detail=f"Invalid OTP. {remaining_attempts} attempts remaining"
    )
