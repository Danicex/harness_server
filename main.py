from typing import Union, Optional, Annotated, List, Type, Dict, Any
from fastapi import Depends, FastAPI, BackgroundTasks,   HTTPException, status, Header, Request, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.dialects.postgresql import JSON
from sqlmodel import Field, Session, SQLModel, Column, create_engine, select, Relationship, JSON, String, DateTime, Boolean
from jose import jwt
from datetime import datetime, timedelta
from passlib.context import CryptContext
from pydantic import BaseModel,  EmailStr
from dotenv import load_dotenv
from fastapi.responses import JSONResponse
import os
import random
from datetime import datetime, timezone, date
import resend
from typing import Dict
import time
from twilio.rest import Client
import uuid
from enum import Enum
from apscheduler.schedulers.background import BackgroundScheduler
from contextlib import asynccontextmanager
import atexit
import httpx
import redis.asyncio as redis
import json
import re
import hmac
import hashlib
import requests
from paystackapi.paystack import Paystack
import pytz

# Load environment variables
load_dotenv()

# JWT and Security
SECRET_KEY =os.getenv("SECRET_KEY")
MAX_ALLOWED_SPEED_KMH = 300
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 30
PAYSTACK_API_URL = "https://api.paystack.co"
PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY")

paystack = Paystack(secret_key=PAYSTACK_SECRET_KEY)

REDIS_PORT = os.getenv("REDIS_PORT")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

postgres_url = os.getenv("POSTGRES_URL")

redis_client = redis.Redis(
    host='localhost',
    port=REDIS_PORT,
    db=int(0),
    decode_responses=True
)

# ----- FASTAPI APP SETUP -----
app = FastAPI()
scheduler = BackgroundScheduler()
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
# ------- allow endpoints --------
origins = [
    "http://localhost:5173",
    "http://localhost:5500",
    "https://harness.encheiron.com",
    "http://localhost:8080",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
#-------------- databse setup -------------------
engine = create_engine(postgres_url, echo=True)  # echo=True for debug logs

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)
    
def get_session():
    with Session(engine) as session:
        yield session
        
SessionDep = Annotated[Session, Depends(get_session)]



def job():
    with Session(engine) as session:
        update_room_status(session)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Schedule the job
    scheduler.add_job(
        update_room_status,
        trigger="interval",
        hours=24,
        next_run_time=datetime.combine(datetime.now().date(), time(hour=2))
    )
    
    scheduler.start()
    atexit.register(lambda: scheduler.shutdown())
    
    yield
    
    scheduler.shutdown()

#-------------- databse setup -------------------

#-------------- models --------------------------------
# ──────────────────────────────
# Admin model
# ──────────────────────────────
class Admin(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    password: str
    role: str = Field(default="user")
    jwt_token: Optional[str] = None
    
    paystack_subscription_code: Optional[str] = Field(sa_column=Column(String, nullable=True))
    paystack_email_token: Optional[str] = Field(sa_column=Column(String, nullable=True))
    plan_type: Optional[str] = Field(sa_column=Column(String, nullable=True))
    manage_subscription_link: Optional[str] = Field(sa_column=Column(String, nullable=True))
    is_active: bool = Field(default=False, sa_column=Column(Boolean, default=False))
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    # Relationships
    rooms: List["Room"] = Relationship(back_populates="admin", sa_relationship_kwargs={"cascade": "all, delete"})
    products: List["Product"] = Relationship(back_populates="admin", sa_relationship_kwargs={"cascade": "all, delete"})
    staff_members: List["Staff"] = Relationship(back_populates="admin", sa_relationship_kwargs={"cascade": "all, delete"})
    blogs: List["Blog"] = Relationship(back_populates="admin", sa_relationship_kwargs={"cascade": "all, delete"})
    inboxes: List["Inbox"] = Relationship(back_populates="admin", sa_relationship_kwargs={"cascade": "all, delete"})
    customer: List["Customer"] = Relationship(back_populates="admin", sa_relationship_kwargs={"cascade": "all, delete"})
    sales: List["Sale"] = Relationship(back_populates="admin", sa_relationship_kwargs={"cascade": "all, delete"})
    bookings: List["Booking"] = Relationship(back_populates="admin", sa_relationship_kwargs={"cascade": "all, delete"})
    
    
    datasets: List["Dataset"] = Relationship(back_populates="admin")
    call_log: List["CallLog"] = Relationship(back_populates="admin")
    hotel_profile_id: Optional[int] = Field(default=None, foreign_key="hotelprofile.id")
    subscription_id: Optional[int] = Field(default=None, foreign_key="subscription.id")
    hotel_profile: Optional["HotelProfile"] = Relationship(back_populates="admin", sa_relationship_kwargs={"uselist": False})
    subscription: Optional["Subscription"] = Relationship(back_populates="admin", sa_relationship_kwargs={"uselist": False})
    
# ──────────────────────────────
# subscription model
# ──────────────────────────────
class Subscription(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    admin_id: Optional[int] = Field(default=None,  unique=True) 
    plan: str = Field(default="none")
    exp_date: str = Field(default="none")
    start_date: str = Field(default="none")
    admin: Optional["Admin"] = Relationship(back_populates="subscription", sa_relationship_kwargs={"uselist": False})

    
# ──────────────────────────────
# Hotel info model
# ──────────────────────────────
class HotelProfile(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    admin_id: Optional[int] = Field(default=None,  unique=True) 
    email: str = Field(index=True, unique=True)
    name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    description: Optional[str] = None
    hotel_name: Optional[str] = None
    website_url: Optional[str] = None
    agent_phone: Optional[str] = None
    social_links: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    image_url: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    
    admin: Optional["Admin"] = Relationship(back_populates="hotel_profile", sa_relationship_kwargs={"uselist": False})
# ──────────────────────────────
# Room model
# ──────────────────────────────
class Room(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    admin_id: Optional[int] = Field(default=None, foreign_key="admin.id")
    number: str
    description: Optional[str] = None
    price: str
    status: Optional[str] = None
    image_url: Optional[str] = None
    pictures: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationship back to admin
    admin: Optional[Admin] = Relationship(back_populates="rooms")
# ──────────────────────────────
# Product model
# ──────────────────────────────
class Product(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    admin_id: Optional[int] = Field(default=None, foreign_key="admin.id")
    name: str
    description: Optional[str] = None
    price: str
    category: Optional[str] = None
    quantity: Optional[str] = None
    image_url: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationship back to admin
    admin: Optional[Admin] = Relationship(back_populates="products")
# ──────────────────────────────
# Staff model
# ──────────────────────────────
class Staff(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    admin_id: Optional[int] = Field(default=None, foreign_key="admin.id")
    name: str
    bio: Optional[str] = None
    role: Optional[str] = None
    cv_url: Optional[str] = None
    image_url: Optional[str] = None
    email: str = Field(index=True, unique=True)
    password: str
    token: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationship back to admin
    admin: Optional[Admin] = Relationship(back_populates="staff_members")
# ──────────────────────────────
# Blog model
# ──────────────────────────────
class Blog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    admin_id: Optional[int] = Field(default=None, foreign_key="admin.id")
    title: str = None
    category: str = Field(default="public")
    description: Optional[str] = None
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationship back to admin
    admin: Optional[Admin] = Relationship(back_populates="blogs")
# ──────────────────────────────
# Booking model
# ──────────────────────────────
class Booking(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    admin_id: Optional[int] = Field(default=None, foreign_key="admin.id")
    room_id: Optional[int] = Field(default=None, foreign_key="room.id")
    staff_id: Optional[int] = Field(default=None, foreign_key="staff.id")
    price: Optional[str] = None
    status: Optional[str] = None
    duration: Optional[str] = None
    customer_email: Optional[str] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    payment_method: Optional[str] = None
    check_in: Optional[str] = None
    check_out: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    admin: Optional[Admin] = Relationship(back_populates="bookings")
# ──────────────────────────────
# Sales model
# ──────────────────────────────
class Sale(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    admin_id: Optional[int] = Field(default=None, foreign_key="admin.id")
    product_id: Optional[int] = Field(default=None, foreign_key="product.id")
    staff_id: Optional[int] = Field(default=None, foreign_key="staff.id")
    price: Optional[str] = None
    quantity: Optional[str] = None
    name: Optional[str] = None
    payment_method: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    admin: Optional[Admin] = Relationship(back_populates="sales")
    
class Inbox(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    admin_id: Optional[int] = Field(default=None, foreign_key="admin.id")
    email: Optional[str] = None
    body: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    admin: Optional[Admin] = Relationship(back_populates="inboxes")

class Customer(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    admin_id: Optional[int] = Field(default=None, foreign_key="admin.id")
    email: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    
    admin: Optional[Admin] = Relationship(back_populates="customer")

class Dataset(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(index=True)
    description: str
    intents: List[Dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    status: str = Field(default="active")  # active, draft, archived
    admin_id: int = Field(foreign_key="admin.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    admin: Admin = Relationship(back_populates="datasets")
    
class CallLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(index=True)
    status: str = Field(default="active")  
    duration: str = Field(default="active")
    sentiment: str
    admin_id: int = Field(foreign_key="admin.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    admin: Admin = Relationship(back_populates="call_log")
    
@app.on_event("startup")

def on_startup():
    create_db_and_tables()
    
@app.get("/")
async def root():
    return {"message": "harness"}


# ---------- UTILS ----------
def hash_password(password: str) -> str:
    # Fix: Handle bcrypt's 72-byte limit
    password_bytes = password.encode('utf-8')
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
    return pwd_context.hash(password_bytes)

#----- verify admin password ------
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

# check authenticity
def create_jwt_token(email: str) -> str:
    expire = datetime.utcnow() + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    to_encode = {"sub": email, "exp": expire}
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def isAuthorized(token: str) -> bool:
    """
    Check if the token is valid, not expired, belongs to an admin, 
    and matches the stored token in database.
    
    Returns:
        bool: True if authorized, False otherwise
    """
    try:
        # Decode and verify JWT token (automatically checks expiration)
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        # Extract email from payload
        email = payload.get("sub")
        if not email:
            return False

        with Session(engine) as session:
            # Find admin by email
            admin = session.exec(select(Admin).where(Admin.email == email)).first()
            
            # Check all authorization conditions
            if not admin:
                return False  # Admin not found
            if admin.jwt_token != token:
                return False  # Token doesn't match stored token
            if admin.role != "admin":
                return False  # User is not an admin

        return True  # All checks passed

    except jwt.ExpiredSignatureError:
        # Token has expired
        return False
    except jwt.InvalidTokenError:
        # Any other JWT validation error
        return False
    except Exception:
        # Catch any other unexpected errors
        return False

#--------------------------auth-----------------------

class StaffLoginParam(BaseModel):
    email: str
    password: str
    admin_id: int

@app.post("/staff_login")
def staff_login(params: StaffLoginParam):
    with Session(engine) as session:
        existing = session.exec(
                select(Admin).where(Admin.id == params.admin_id)
            ).first()
        if not existing:
            raise HTTPException(status_code=400, detail="No admin assigned")
        
        try:
            #get the staff details
            staff = session.exec(
               select(Staff)
                .where(Staff.email == params.email)
                .where(Staff.admin_id == params.admin_id)
            ).first()
            
              # Check if staff exists
            if not staff:
                raise HTTPException(status_code=400, detail="Staff not found for this admin")
            
            # Verify password
            if staff.password != params.password:
                raise HTTPException(status_code=400, detail="Invalid password")
            
            else:
                token = create_jwt_token(params.email)
                #store token under staff
                staff.token = token
                session.add(staff)
                session.commit()
                session.refresh(staff)
                
                return staff
            
        except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

class SignParam(BaseModel):
    email: str
    password: str
    role: str

@app.post("/signup")
def signup(params: SignParam):
    with Session(engine) as session:
        # Check if admin already exists
        existing = session.exec(
            select(Admin).where(Admin.email == params.email)
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Admin already exists")
        
        hashed = hash_password(params.password)
        token = create_jwt_token(params.email)

        try:
            # Create Admin
            admin = Admin(
                email=params.email,
                password=hashed,
                role = params.role,
                jwt_token=token,
            )

            session.add(admin)
            session.commit()
            session.refresh(admin)
            

            return {
                "admin_id": admin.id,
                "token": token,
                "email": admin.email,
                "message": "Admin created successfully"
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

class LoginParam(BaseModel):
    email: str
    password: str
    
@app.post("/login")    
def login(params: LoginParam):
    with Session(engine) as session:
        admin = session.exec(select(Admin).where(Admin.email == params.email)).first()
        if not admin or not verify_password(params.password, admin.password):
            raise HTTPException(status_code=401, detail="Invalid email or password")

        # Generate new token each time
       # Generate new token
        token = create_jwt_token(params.email)
        admin.jwt_token = token

        session.add(admin)        # Optional but safe
        session.commit()          # This will now persist the token
        session.refresh(admin)  
        return {
            "token": token, 
                "message": "Login successful", 
                "admin_id": admin.id,
                "email": admin.email, 
                "joined_at": admin.created_at, 
                }
        
      
#------------------------- CRUD -------------------------------
# ──────────────────────────────
# Create
# ──────────────────────────────
class ObjectParams(BaseModel):
    model_name: str
    params: dict 
    #the file
    
@app.post("/create/{model_name}")
async def create_object(
    model_name: str,
    session: SessionDep,
    authorization: str = Header(...),
    file: Optional[UploadFile] = File(None),
    cv: Optional[UploadFile] = File(None),  
    video: Optional[UploadFile] = File(None),  
    data: str = Form(...), 
):
    # Validate authorization
    token = authorization.split(" ")[1]
    auth = isAuthorized(token)
    
    if not auth:
        raise HTTPException(status_code=401, detail="Not authorized")
    
    # Parse the ObjectParams from JSON
    try:
        obj_params = ObjectParams.parse_raw(data)
    except:
        raise HTTPException(status_code=400, detail="Invalid data format")
    
    # Map of model names to SQLModel classes
    model_map = {
        "room": Room,
        "product": Product,
        "blog": Blog,
        "staff": Staff,
        "hotel_profile": HotelProfile
    }

    model_class = model_map.get(obj_params.model_name.lower())
    if not model_class:
        raise HTTPException(status_code=400, detail=f"Unknown model: {model_name}")

    try:
        # Handle file upload
        if file and file.filename:
            file_path = upload_file(file)
            obj_params.params["image_url"] = file_path
        if cv and cv.filename:
                cv_path = upload_file(cv)
                obj_params.params["cv_url"] = cv_path
        if video and video.filename:
                video_path = upload_file(video)
                obj_params.params["video_url"] = video_path
        
        
        # Create instance
        model_instance = model_class(**obj_params.params)
        session.add(model_instance)
        session.commit()
        session.refresh(model_instance)
        
        return {
            "success": True, 
            "data": model_instance,
            "file_uploaded": bool(file and file.filename)
        }
        
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    
# ──────────────────────────────
# Read model
# ──────────────────────────────
#customer end get rooms
@app.get("/room/{admin_id}")
def get_rooms(admin_id: int, session: SessionDep):
    rooms = session.exec(
            select(Room).where(Room.admin_id == admin_id)
        ).all()
    return rooms

class BookingParam(BaseModel):
    room_id: int
    price: str
    status: str
    duration: str
    customer_email: str
    customer_name: str
    customer_phone: str
    check_in: str
    check_out: str
    
@app.post("/booking/{admin_id}")
def create_booking(
    admin_id: int,
    booking_data: BookingParam,
    session: Session = Depends(get_session)
):
    # Check if admin exists
    admin = session.exec(
        select(Admin).where(Admin.id == admin_id)
    ).first()
    
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Admin with id {admin_id} not found"
        )
    
    # Check if room  exists and belongs to this admin
    room = session.exec(
        select(Room).where(Room.id == booking_data.room_id)
    ).first()
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Room with id {booking_data.room_id} not found"
        )
    
    if room.admin_id != admin_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Room {booking_data.room_id} does not belong to admin {admin_id}"
        )

    # Create booking
    booking = Booking(
        admin_id=admin_id,
        room_id=booking_data.room_id,
        price=booking_data.price,
        status=booking_data.status,
        duration=booking_data.duration,
        customer_email=booking_data.customer_email,
        customer_name=booking_data.customer_name,
        customer_phone=booking_data.customer_phone,
        check_in=booking_data.check_in,
        check_out=booking_data.check_out
    )
    
    session.add(booking)
    session.commit()
    session.refresh(booking)
    
    return booking


@app.get("/inventory/{admin_id}")
def get_inventory(admin_id: int, session: SessionDep):
    inventory = session.exec(
            select(Product).where(Product.admin_id == admin_id)
        ).all()
    return inventory




@app.get("/get/{model_name}/{admin_id}")
def get_data(model_name: str, admin_id: int, session: SessionDep, authorization: str = Header(...)
             ):
    # Verify authorization and authentication
    token = authorization.split(" ")[1]
    auth = isAuthorized(token)
    
    if not auth:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authorized"
        )
    
    # Map of model names to SQLModel classes
    model_map: dict[str, Type] = {
        "room": Room,
        "product": Product,
        "blog": Blog,
        "sales": Sale,
        "booking": Booking,
        "staff": Staff,
        "hotel_profile": HotelProfile,
        "inbox": Inbox,
        "subscription": Subscription
    }
    
    if model_name == "analytics":
        booking = session.exec(
            select(Booking).where(Booking.admin_id == admin_id)
        ).all()
        sales = session.exec(
            select(Booking).where(Booking.admin_id == admin_id)
        ).all()
        
        total_bookings = len(booking)
        total_booking_price = sum(float(b.price) for b in booking)
        
        total_sale = len(sales)
        total_sale_price = sum(float(s.price) for s in sales)
        
        result = {
        "total_booking": total_bookings,
        "total_booking_price": total_booking_price,
        "total_sale": total_sale,
        "total_sale_price": total_sale_price,
        }
        
        return result
        
    # Lookup the correct model class
    model_class = model_map.get(model_name.lower())
    if not model_class:
        raise HTTPException(status_code=400, detail=f"Unknown model: {model_name}")

    try:
        # Get all items for this admin
        items = session.exec(
            select(model_class).where(model_class.admin_id == admin_id)
        ).all()
        
        if model_class == "hotel_profile":
            return items
        items = items[::-1]
        
        return items
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
# ──────────────────────────────
# Update model
# ──────────────────────────────
class UpdateObjectParam(BaseModel):
    model_name: str
    params: dict 
    
@app.put("/update/{model_name}/{admin_id}/{item_id}")
def update_data(model_name: str, admin_id: int, item_id: int, data: UpdateObjectParam, session: SessionDep, authorization: str = Header(...)):
    # Verify authorization and authentication
    token = authorization.split(" ")[1]
    auth = isAuthorized(token)
    
    if not auth:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authorized"
        )
    
    # Map of model names to SQLModel classes
    model_map: dict[str, Type] = {
        "room": Room,
        "product": Product,
        "blog": Blog,
        "staff": Staff,
    }

    # Lookup the correct model class
    model_class = model_map.get(model_name.lower())
    if not model_class:
        raise HTTPException(status_code=400, detail=f"Unknown model: {model_name}")

    try:
        # Find the item to update
        item = session.exec(
            select(model_class).where(
                model_class.admin_id == admin_id,
                model_class.id == item_id
            )
        ).first()
        
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
        
        # Update item with new data
        for key, value in data.params.items():
            if hasattr(item, key):
                setattr(item, key, value)
        
        session.add(item)
        session.commit()
        session.refresh(item)
        
        return {"success": True, "data": item, "message": "Item updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# ──────────────────────────────
# Delete model
# ──────────────────────────────
@app.delete("/delete/{model_name}/{admin_id}/{item_id}")
def delete_data(model_name: str, admin_id: int, item_id: int, session: SessionDep, authorization: str = Header(...)):
    # Verify authorization and authentication
    token = authorization.split(" ")[1]
    auth = isAuthorized(token)
    
    if not auth:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authorized"
        )
    
    # Map of model names to SQLModel classes
    model_map: dict[str, Type] = {
        "room": Room,
        "product": Product,
        # "blog": Blog,
        "staff": Staff,
    }

    # Lookup the correct model class
    model_class = model_map.get(model_name.lower())
    if not model_class:
        raise HTTPException(status_code=400, detail=f"Unknown model: {model_name}")

    try:
        # Find the item to delete
        item = session.exec(
            select(model_class).where(
                model_class.admin_id == admin_id,
                model_class.id == item_id
            )
        ).first()
        
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
        
        # Delete the item
        session.delete(item)
        session.commit()
        
        return {"success": True, "message": "Item deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    
# ──────────────────────────────
# Analytics for booking, sales, 
# ──────────────────────────────  
    

@app.get("/analytic/{admin_id}")
def get_analytics(admin_id: int, session: SessionDep, authorization: str = Header(...), limit: Optional[int] = 100) -> List[Dict[str, Any]]:
    """
    Get sales analytics data with pagination
    """
    token = authorization.split(" ")[1]
    auth = isAuthorized(token)
    
    if not auth:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authorized"
        )
    try:
        # Fetch sales data with limit
        sales = session.exec(
            select(Sale)
            .where(Sale.admin_id == admin_id)
            .order_by(Sale.created_at.desc())
            .limit(limit)
        ).all()
        
        # Fetch booking data with limit
        bookings = session.exec(
            select(Booking)
            .where(Booking.admin_id == admin_id)
            .order_by(Booking.created_at.desc())
            .limit(limit)
        ).all()
        
        result = []
        
        # Helper function to parse duration
        def parse_duration(duration_str: str) -> str:
            if not duration_str:
                return "1h"
            
            # Try to extract numeric value and unit
            match = re.match(r'(\d+)\s*([hmd]?)', str(duration_str).lower())
            if match:
                num, unit = match.groups()
                num = int(num)
                if unit == 'm':
                    return f"{num}m"
                elif unit == 'h':
                    return f"{num}h"
                elif unit == 'd':
                    return f"{num}d"
                else:
                    # Default to hours if no unit specified
                    return f"{num}h"
            return "1h"
        
        # Process sales
        for sale in sales:
            amount = 0.0
            try:
                base_price = float(sale.price) if sale.price else 0.0
                quantity = int(sale.quantity) if sale.quantity and sale.quantity.isdigit() else 1
                amount = base_price * quantity
            except (ValueError, TypeError):
                amount = 0.0
            
            sale_item = {
                "id": f"S-{1000 + (sale.id or 0)}",
                "type": "SALES",
                "timestamp": sale.created_at.isoformat() if sale.created_at else datetime.utcnow().isoformat(),
                "amount": round(amount, 2),
                "paymentMethod": sale.payment_method or "cash",
                "items": [
                    {
                        "id": f"p{sale.id}" if sale.id else "p0",
                        "name": sale.name or "Unnamed Product",
                        "quantity": int(sale.quantity) if sale.quantity and sale.quantity.isdigit() else 1,
                        "price": float(sale.price) if sale.price else 0.0,
                        "category": "General"
                    }
                ],
                "booking": None
            }
            result.append(sale_item)
        
        # Process bookings
        for booking in bookings:
            amount = 0.0
            try:
                amount = float(booking.price) if booking.price else 0.0
            except (ValueError, TypeError):
                amount = 0.0
            
            # Get service type from room or use default
            service_type = "Booking"
            
            booking_item = {
                "id": f"B-{1000 + (booking.id or 0)}",
                "type": "BOOKING",
                "timestamp": booking.created_at.isoformat() if booking.created_at else datetime.utcnow().isoformat(),
                "amount": round(amount, 2),
                "paymentMethod": booking.payment_method or "cash",
                "items": None,
                "booking": {
                    "customerName": booking.customer_email or "Customer",
                    "serviceType": service_type,
                    "startTime": booking.check_in or (booking.created_at.isoformat() if booking.created_at else datetime.utcnow().isoformat()),
                    "duration": parse_duration(booking.duration),
                    "status": booking.status or "pending"
                }
            }
            result.append(booking_item)
        
        # Sort by timestamp (most recent first)
        result.sort(key=lambda x: x["timestamp"], reverse=True)
        
        # Apply final limit if needed
        if len(result) > limit:
            result = result[:limit]
            
        return result
        
    except Exception as e:
        # Log the error
        print(f"Error fetching analytics: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )
# ──────────────────────────────
# FILE UPLOAD
# ──────────────────────────────  
UPLOAD_DIR = "uploads"
IMAGES_DIR = os.path.join(UPLOAD_DIR, "images")
DOCUMENTS_DIR = os.path.join(UPLOAD_DIR, "documents")
VIDEOS_DIR = os.path.join(UPLOAD_DIR, "videos")

os.makedirs(IMAGES_DIR, exist_ok=True)
os.makedirs(DOCUMENTS_DIR, exist_ok=True)
os.makedirs(VIDEOS_DIR, exist_ok=True)

def upload_file(file: UploadFile = File(...)):
    """Simple file upload - returns file path"""
    
    # Get extension
    ext = os.path.splitext(file.filename)[1].lower()
    
        # Choose directory based on extension
    if ext in ['.jpg', '.jpeg', '.png', '.gif']:
        save_dir = IMAGES_DIR
    elif ext == '.mp4':
        save_dir = VIDEOS_DIR
    else:
        save_dir = DOCUMENTS_DIR
    
    # Create unique filename
    unique_name = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(save_dir, unique_name)
    
    # Save file
    with open(file_path, "wb") as f:
        f.write(file.file.read())
    
    return file_path


    
# ──────────────────────────────
# Sales endpoint
# ──────────────────────────────

def validate_staff(token):
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    email = payload.get("sub")
    exp = payload.get("exp")
    with Session(engine) as session:   
        staff = session.exec(
            select(Staff).where(Staff.email == email)
        ).first()
    
    if exp < datetime.now(timezone.utc).timestamp():
       raise HTTPException(status_code=401, detail="Expired token")
    
    if token != staff.token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    if staff:
        return True
    return False
  
  
@app.get('/staff_endpoint/get/{model_name}/{admin_id}/{staff_id}')
def sales_get(staff_id: int, model_name: str, admin_id: int, session: SessionDep, authorization: str = Header(...)):

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    
    model_map: dict[str, Type] = {
        "room": Room,
        "product": Product,
        "staff_sale": Sale,
        "profile": Staff,
        "blog": Blog,
        "staff_booking": Booking,
    }

    model_class = model_map.get(model_name.lower())
    if not model_class:
        raise HTTPException(status_code=400, detail=f"Unknown model: {model_name}")
    
    
    token = authorization.split(" ")[1]
    staff = validate_staff(token)
    if not staff:
        raise HTTPException(status_code=401, detail="Invalid token: missing email")
        
    try:
        if staff:
            if model_name in ('staff_sale', 'staff_booking'):
                # query the database for the staff_id
                items = session.exec(
                    select(model_class).where(
                        model_class.admin_id == admin_id,
                        model_class.staff_id == staff_id
                    )
                ).all()
                return items[::-1]
            
            if model_name == "profile":
                items = session.exec(
                    select(model_class).where(
                        model_class.admin_id == admin_id,
                        model_class.id == staff_id
                    )
                ).all()
                return items  # Added return statement
            
            items = session.exec(
                select(model_class).where(
                    model_class.admin_id == admin_id
                )
            ).all()
            
            return items[::-1]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/pending_booking/{admin_id}")
def get_pending_booking(
    admin_id: int,
    session: SessionDep,
    authorization: str = Header(...)
):
    # --- Auth ---
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = authorization.split(" ")[1]
    auth = validate_staff(token)

    if not auth:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authorized"
        )

    # --- Query pending bookings ---
    bookings = session.exec(
        select(Booking).where(
            Booking.admin_id == admin_id,
            Booking.status == "pending"
        )
    ).all()

    return bookings

#-------------------
class StaffObjectParams(BaseModel):
    model_name: str
    params: dict

@app.post('/staff_endpoint/create/{model_name}/{admin_id}')
def staff_inputs(model_name: str, admin_id: int, data: StaffObjectParams, session: SessionDep, authorization: str = Header(...)):
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    
    model_map: dict[str, Type] = {
        "booking": Booking,
        "sale": Sale,
    }

    model_class = model_map.get(model_name.lower())
    if not model_class:
        raise HTTPException(status_code=400, detail=f"Unknown model: {model_name}")
    
    token = authorization.split(" ")[1]
    auth = validate_staff(token)
    
    if not auth:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authorized"
    )
        
    try:
        if auth:
            model_instance = model_class(**data.params)
            session.add(model_instance)
            session.commit()
            session.refresh(model_instance)
            
            if model_name == "booking":
            # update room model: room.status = occupied
                room_id = model_instance.room_id
                if room_id:
                    room = session.exec(
                        select(Room).where(Room.id == room_id) )
                    if room:
                        room.status = "occupied"
                        session.commit()
                return {"success": True, "data": model_instance}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class UpdateBookingStatus(BaseModel):
    status: str
    
@app.put("/update/booking/{admin_id}/{room_id}/{booking_id}")
def update_booking(
    admin_id: int,
    room_id: int,
    booking_id: int,
    session: SessionDep,
    status_update: UpdateBookingStatus,
    authorization: str = Header(...)
):
    # --- Auth ---
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = authorization.split(" ")[1]
    auth = validate_staff(token)

    if not auth:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authorized"
        )

    # --- Get booking ---
    booking = session.exec(
        select(Booking).where(
            Booking.id == booking_id,
            Booking.admin_id == admin_id
        )
    ).first()

    if not booking:
        raise HTTPException(
            status_code=404,
            detail="Booking not found"
        )

    # --- Get room ---
    room = session.exec(
        select(Room).where(
            Room.id == room_id,
            Room.admin_id == admin_id
        )
    ).first()

    if not room:
        raise HTTPException(
            status_code=404,
            detail="Room not found"
        )

    # --- Update booking status ---
    booking.status = status_update.status
    
    if status_update.status == "confirmed":  
        room.status = "occupied"
    elif status_update.status in ["cancelled", "completed"]:
        room.status = "available"
        
    booking.room_id = room_id

    session.add(booking)
    session.add(room)
    session.commit()
    session.refresh(booking)
    session.refresh(room)

    return {
        "success": True,
        "message": "Booking updated successfully",
        "data": booking
    }

# -------------------
# inbox
class InboxParam(BaseModel):
    email: str
    body: str

@app.post("/inbox/{admin_id}")
def create_inbox(admin_id: int, params: InboxParam, session: SessionDep):
    try:
        # Start a transaction — ensures atomic commit
        with session.begin():
            # 1️⃣ Create inbox message
            inbox = Inbox(
                email=params.email,
                body=params.body,
                admin_id=admin_id
            )
            session.add(inbox)

            # 2️⃣ Get existing customer for this admin
            customer = session.exec(
                select(Customer).where(Customer.admin_id == admin_id)
            ).first()

            # 3️⃣ If customer doesn't exist, create new
            if not customer:
                customer = Customer(
                    admin_id=admin_id,
                    email=[params.email]
                )
                session.add(customer)
            else:
                # 4️⃣ Update existing customer's email list if needed
                if params.email not in customer.email:
                    customer.email.append(params.email)
                    # session.add(customer) not required, already tracked

        # ✅ Commit automatically happens when 'with' block exits

        # Refresh objects after commit
        session.refresh(inbox)
        session.refresh(customer)

        return {
            "message": "Inbox created successfully",
            "data": inbox,
            "customer_emails": customer.email,
        }

    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error creating inbox: {str(e)}"
        )
        

#______________________________________
#email verification
resend.api_key = os.environ["RESEND_API_KEY"]

#use background task to handle the send mail function
tasks_store: Dict[str, dict] = {} 

class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SENT = "sent"
    FAILED = "failed"
    COMPLETED = "completed"
    
class OTPVerification(BaseModel):
    email: EmailStr
    otp: str
    
class EmailParam(BaseModel):
    emails: Union[str, List[str]]
    subject: str
    body: str
    from_email: str = "Acme <noreply@encheiron.com>"
    
def send_resend_email(
    task_id: str, 
    to: Union[str, List[str]],
    subject: str,
    body: str,
    from_email: str = "Acme <noreply@encheiron.com>"
):
    try:
        # Update task status to processing
        tasks_store[task_id]["status"] = TaskStatus.PROCESSING
        tasks_store[task_id]["started_at"] = datetime.utcnow().isoformat()
        
        # Convert single email to list
        if isinstance(to, str):
            to = [to]
        
        # Prepare email parameters
        params = {
            "from": from_email,
            "to": to,
            "subject": subject,
            "html": body,
        }
        
        # Send email via Resend
        response = resend.Emails.send(params)
        
        # Update task with results
        tasks_store[task_id]["status"] = TaskStatus.SENT
        tasks_store[task_id]["completed_at"] = datetime.utcnow().isoformat()
        tasks_store[task_id]["result"] = {
            "success": True,
            "email_count": len(to),
            "resend_id": response.get("id"),
            "recipients": to,
            "sent_at": datetime.utcnow().isoformat()
        }
    except Exception as e:
         # Handle errors
        tasks_store[task_id]["status"] = TaskStatus.FAILED
        tasks_store[task_id]["completed_at"] = datetime.utcnow().isoformat()
        tasks_store[task_id]["error"] = str(e)
        

@app.post('/send_mails/{admin_id}')
async def send_email_endpoint(
    data: EmailParam,
    admin_id: int,
    background_tasks: BackgroundTasks,
    session: SessionDep, authorization: str = Header(...)
) -> JSONResponse:
    """
    Send email(s) to single or multiple recipients
    """
    # Generate unique task ID
    task_id = str(uuid.uuid4())
    token = authorization.split(" ")[1]
    auth = isAuthorized(token)
    
    if not auth:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authorized"
        )
        
    admin = session.exec(
        select(Admin).where(Admin.id == admin_id)
    )
    
    if not admin:
        raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Not authorized"
                )    
        
    emails_list = [data.emails] if isinstance(data.emails, str) else data.emails
    
    tasks_store[task_id] = {
        "status": TaskStatus.PENDING,
        "emails": emails_list,
        "subject": data.subject,
        "from_email": data.from_email,
        "created_at": datetime.utcnow().isoformat(),
    }
    
    # Add background task
    background_tasks.add_task(
        send_resend_email,
        task_id,
        data.emails,
        data.subject,
        data.body,
        data.from_email,
    )
    
    return JSONResponse(
        status_code=202,  # Accepted
        content={
            "task_id": task_id,
            "status": "queued",
            "message": f"Email task queued for {len(emails_list)} recipient(s)",
            "tracking_url": f"/tasks/{task_id}",
        }
    )      
    
#______________________________________


    
async def send_resend_vr(
    to: Union[str, List[str]],
    subject: str,
    html: str,
    from_email: str = "Acme <noreply@encheiron.com>"
) -> bool:
    """Simple function to send email via Resend"""
    try:
        # Convert single email to list
        if isinstance(to, str):
            to = [to]
        
        # Prepare email parameters
        params = {
            "from": from_email,
            "to": to,
            "subject": subject,
            "html": html,
        }
        
        # Send email via Resend
        response = resend.Emails.send(params)
        
        # Check if email was sent successfully
        if response and 'id' in response:
            return True
        return False
        
    except Exception as e:
        print(f"Error sending email: {e}")
        return False
 
# Email configuration (set these as environment variables in production)
class EmailRequest(BaseModel):
    to: EmailStr

def generate_otp() -> str:
    """Generate a 6-digit OTP"""
    return str(random.randint(100000, 999999))

@app.post("/send-verification-email")
async def send_verification_email(email_request: EmailRequest):
    try:
        otp_code = generate_otp()
        redis_client.delete(f"otp:{email_request.to}") #delete the data attached to the prev key
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
        email_sent = await send_resend_vr(
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
 
@app.post("/verify-otp")
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

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "email-verification"}

# Cleanup expired OTPs (optional - you can run this as a background task)
def cleanup_expired_otps(key:str):
    """Clean up expired OTPs from storage"""
    current_time = time.time()
    redis_client.delete(key)

#------------------SMS AND MAILING

#mailing

class EmailRequest(BaseModel):
    from_email: str
    from_name: str
    emails: List[EmailStr]
    subject: str
    message: str
    
@app.post("/send-emails")
async def send_emails(email_request: EmailRequest):
    try:
        results = await send_resend_email(
            to= email_request.from_email,
            subject=email_request.subject,
            html=email_request.message,
        )

        return {
            "message": (
                f"Emails sent. Successful: {len(results['successful'])}, "
                f"Failed: {len(results['failed'])}"
            ),
            "results": results,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    #-----------get emails from admin
@app.get('/get_mails/{admin_id}')

def get_mails(admin_id: int, session: SessionDep, authorization: str = Header(...)):
    token = authorization.split(" ")[1]
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing"
        )
    
    auth = isAuthorized(token)    
    if not auth:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authorized"
        )
    
    try:
        # Query bookings
        bookings = session.exec(
            select(Booking).where(Booking.admin_id == admin_id)
        ).all()
        
        # Query inbox messages
        inbox_messages = session.exec(
            select(Inbox).where(Inbox.admin_id == admin_id)
        ).all()
        
        x_emails = [booking.customer_email for booking in bookings if booking.customer_email]
        y_emails = [msg.email for msg in inbox_messages if msg.email]  # Changed _email to email
        x_phones = [booking.customer_phone for booking in bookings if booking.customer_phone]
    
    
        all_emails = x_emails + y_emails
        unique_emails = list(set(filter(None, all_emails))) 
        
        unique_phones = list(set(filter(None, x_phones)))  
        return {
            "emails": unique_emails,
            "phone_numbers": unique_phones
        }
        
    except Exception as e:
        print(f"Error fetching mails: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
        
def update_room_status():
    """Background job to update room statuses"""
    with Session(engine) as session:
        today = date.today()
        bookings = session.exec(
            select(Booking).where(Booking.status == "confirmed")
        ).all()
        
        if not bookings:
            print("No confirmed bookings found")
            return
        
        updated_rooms = []
        
        for booking in bookings:
            # Check if booking is currently active
            if booking.check_in >= today > booking.check_out:
                room = session.exec(
                    select(Room).where(Room.id == booking.room_id)
                ).first()
                
                if room and room.status != "avialable":
                    room.status = "avialable"
                    session.add(room)
                    updated_rooms.append(room.id)
        
        session.commit()
        print(f"Updated rooms at {datetime.now()}: {updated_rooms}")
 
#-------send sms
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

#bg task

def send_twilio_sms(
    task_id: str,
    to_numbers: Union[str, List[str]],
    message: str,
    from_phone: str = TWILIO_PHONE_NUMBER
):
    """
    Background task to send SMS via Twilio
    """
    try:
        # Update task status to processing
        tasks_store[task_id]["status"] = TaskStatus.PROCESSING
        tasks_store[task_id]["started_at"] = datetime.utcnow().isoformat()
        
        # Convert single phone number to list
        if isinstance(to_numbers, str):
            to_numbers = [to_numbers]
        
        # Validate phone numbers (basic validation)
        validated_numbers = []
        for number in to_numbers:
            # Remove any non-digit characters except +
            cleaned = ''.join(c for c in number if c.isdigit() or c == '+')
            if cleaned:
                validated_numbers.append(cleaned)
        
        # Store validated numbers
        tasks_store[task_id]["validated_numbers"] = validated_numbers
        
        # Send SMS to each phone number
        results = []
        successful_sends = 0
        
        for phone_number in validated_numbers:
            try:
                # Send SMS via Twilio
                message_instance = twilio_client.messages.create(
                    body=message,
                    from_=from_phone,
                    to=phone_number
                )
                
                # Record successful send
                results.append({
                    "phone_number": phone_number,
                    "success": True,
                    "message_sid": message_instance.sid,
                    "status": message_instance.status,
                    "error": None
                })
                successful_sends += 1
                
            except Exception as e:
                # Record failed send
                results.append({
                    "phone_number": phone_number,
                    "success": False,
                    "message_sid": None,
                    "status": "failed",
                    "error": str(e)
                })
        
        # Update task with results
        tasks_store[task_id]["status"] = TaskStatus.COMPLETED
        tasks_store[task_id]["completed_at"] = datetime.utcnow().isoformat()
        tasks_store[task_id]["result"] = {
            "total_attempted": len(validated_numbers),
            "successful_sends": successful_sends,
            "failed_sends": len(validated_numbers) - successful_sends,
            "results": results,
            "sent_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        # Handle general errors
        tasks_store[task_id]["status"] = TaskStatus.FAILED
        tasks_store[task_id]["completed_at"] = datetime.utcnow().isoformat()
        tasks_store[task_id]["error"] = str(e)
        
class SMSRequest(BaseModel):
    phone_numbers: Union[str, List[str]]
    message: str
    from_phone: str = TWILIO_PHONE_NUMBER 
        
class TaskResponse(BaseModel):
    task_id: str
    status: str
    message: str
       
#api endpoint for sms
@app.post("/api/sms/send", response_model=TaskResponse)
async def send_sms(
    sms_request: SMSRequest,
    background_tasks: BackgroundTasks
):
    """
    API endpoint to send SMS via background task
    """
    # Generate a unique task ID
    task_id = str(uuid.uuid4())
    
    # Initialize task in store
    tasks_store[task_id] = {
        "status": TaskStatus.PENDING,
        "created_at": datetime.utcnow().isoformat(),
        "request": {
            "phone_numbers": sms_request.phone_numbers,
            "message": sms_request.message,
            "from_phone": sms_request.from_phone,
            "message_length": len(sms_request.message)
        }
    }
    
    # Add task to background tasks
    background_tasks.add_task(
        send_twilio_sms,
        task_id=task_id,
        to_numbers=sms_request.phone_numbers,
        message=sms_request.message,
        from_phone=sms_request.from_phone
    )
    
    return TaskResponse(
        task_id=task_id,
        status="pending",
        message="SMS sending task queued successfully"
    )



class Intent(BaseModel):
    id: str
    question: str
    response: str
    followUpQuestion: Optional[str] = None
    redirect: Optional[str] = None


class DatasetCreate(BaseModel):
    title: str
    description: str
    intents: List[Intent]
     
@app.post('/create_dataset/{admin_id}')
def create_dataset(
    admin_id: int, 
    dataset_data: DatasetCreate, 
    session: SessionDep,
    authorization: str = Header(...),
):
    token = authorization.split(" ")[1]
    auth = isAuthorized(token)
    if not auth:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authorized"
        )
        
    admin = session.exec(select(Admin).where(Admin.id == admin_id)).first()
    if not admin:
         raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="admin not found"
        )
         
    """Create a new dataset with intents and actions"""
    try:
        
        # Convert intents to dict for JSON storage
        intents_dict = [intent.dict() for intent in dataset_data.intents]
        
        # Create new dataset
        dataset = Dataset(
            title=dataset_data.title,
            description=dataset_data.description,
            intents=intents_dict,
            status="active",
            admin_id=admin_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        session.add(dataset)
        session.commit()
        session.refresh(dataset)
        
        return {
            "status": "success",
            "message": "Dataset created successfully",
            "data": {
                "id": dataset.id,
                "title": dataset.title,
                "description": dataset.description,
                "intents": dataset.intents,
                "created_at": dataset.created_at
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create dataset: {str(e)}")


@app.get('/call_logs/{admin_id}')  
def get_call_logs(
    admin_id: int, 
    session: SessionDep,
    page: int = 1,
    limit: int = 10,
    authorization: str = Header(...),
):
    token = authorization.split(" ")[1]
    auth = isAuthorized(token)
    if not auth:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authorized"
        )
        
    admin = session.exec(select(Admin).where(Admin.id == admin_id)).first()
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Admin not found"
        )
    
    try:
        # Get total count for pagination
        total_count = session.exec(
            select(CallLog).where(CallLog.admin_id == admin_id)
        ).all()
        total = len(total_count)
        
        # Apply pagination
        offset = (page - 1) * limit
        call_logs = session.exec(
            select(CallLog)
            .where(CallLog.admin_id == admin_id)
            .offset(offset)
            .limit(limit)
        ).all()
        
        # Calculate total pages
        total_pages = (total + limit - 1) // limit
        
        return {
            "data": call_logs,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": total_pages
        }
        
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to fetch call logs: {str(e)}"
        )
          
class CallLogsCreate(BaseModel):
    title: str
    status: str
    duration: str
    sentiment: str
    
@app.post('/store_call_logs/{admin_id}')
async def store_call_logs(
    admin_id: int, 
    call_log_data: CallLogsCreate,  # Add request body
    session: SessionDep
):
    # Verify admin exists
    admin = session.exec(select(Admin).where(Admin.id == admin_id)).first()
    
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,  # Changed to 404 for not found
            detail="Admin not found"
        )
    
    try:
        # Create new call log
        new_call_log = CallLog(
            admin_id=admin_id,
            title=call_log_data.title,
            status=call_log_data.status,
            duration=call_log_data.duration,
            sentiment=call_log_data.sentiment
        )
        
        # Store call logs
        session.add(new_call_log)
        session.commit()
        session.refresh(new_call_log)
        
        return new_call_log
        
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create call log: {str(e)}")

# ai action room book
headers = {
            "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

class PaymentModel(BaseModel):
    email: str
    plan_code: str
    amount: int
    
@app.post("/initialize-transaction/{admin_id}")
async def initialize_transaction(data: PaymentModel, admin_id: int, session: SessionDep, authorization: str = Header(...)):
    token = authorization.split(" ")[1]
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing"
        )
    
    auth = isAuthorized(token)    
    if not auth:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authorized"
        )
    admin = session.exec(select(Admin).where(Admin.id == admin_id)).first()
    if not admin:
        raise HTTPException(status_code=400, detail="user not found")
    
    email = data.email
    amount = data.amount
    plan = data.plan_code

    if not all([email, amount, plan]):
        raise HTTPException(status_code=400, detail="Please provide email, amount, and plan code")
    
    trial_end_date = (datetime.now(pytz.utc) + timedelta(days=30)).isoformat()
    
    plans  = {
        'PLN_v3o2ntamoh7bgae':'monthly',
        'PLN_ls4chsrcaz52tf1':'3 months',
        'PLN_lw7fn7o13j0gr3c':'1 year',
    }
    if plan not in plans:
        raise HTTPException(status_code=400, detail="Plan not found")
    
    
    response = paystack.transaction.initialize(
        email=email,
        amount=amount * 100,
        plan=plan,
        channels=['card'],
        start_date=trial_end_date,
        callback_url="https://www.harness.encheiron.com/dashboard"
    )
    if not response['status']:
        raise HTTPException(status_code=400, detail=response['message'])
    
    admin.plan_type = plans[plan]
    session.add(admin)
    session.commit()
    session.refresh(admin)
        
    return response['data']



@app.get('/admin/{admin_id}/subscription')
def get_admin_sub(session: SessionDep,  admin_id: int, authorization: str = Header(...)):
    token = authorization.split(" ")[1]
    auth = isAuthorized(token)
    
    if not auth:
        raise HTTPException(status_code=401, detail="Not authorized")
    
    admin = session.exec(
        select(Admin).where(Admin.id == admin_id)
    ).first()
    
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Admin with id {admin_id} not found"
        )
    return {
        "is_active": admin.is_active,
        "manage_link": admin.manage_subscription_link,
        "plan_type": admin.plan_type
    }
    
async def get_subscriptions(email: str):
    url = "https://api.paystack.co/subscription"

    headers = {
        "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"
    }

    async with httpx.AsyncClient() as client:
        res = await client.get(url, headers=headers)
        data = res.json()

  
    if not data.get("status"):
        return None

    subscriptions = data.get("data", [])


    for sub in subscriptions:
        customer_email = sub.get("customer", {}).get("email", "").lower()

        if customer_email == email.lower():
            return {
                "sub_code":sub.get("subscription_code"),
                "email_token": sub.get("email_token")
                }  
            
    return None

def get_paystack_manage_link(subscription_code):
    url = f"https://api.paystack.co/subscription/{subscription_code}/manage/link"
    
    headers = {
        "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status() 
        data = response.json()
        
        if data.get('status'):
            return data['data']['link']
        else:
            print(f"Error: {data.get('message')}")
            return None

    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return None

@app.post("/paystack-webhook")
async def paystack_webhook(
    request: Request, 
    session: SessionDep, 
    x_paystack_signature: str = Header(None)
):
    payload = await request.body()
    
    # 1. Verify Signature
    signature = hmac.new(
        PAYSTACK_SECRET_KEY.encode('utf-8'),
        payload,
        hashlib.sha512
    ).hexdigest()

    if signature != x_paystack_signature:
        raise HTTPException(status_code=401, detail="Invalid signature")

    event_data = json.loads(payload)
    event = event_data.get("event")
    data = event_data.get("data")
    
    # 2. Find the User
    customer_email = data.get("customer", {}).get("email")
    admin = session.exec(select(Admin).where(Admin.email == customer_email)).first()
    print(data)
    if not admin:
        return {"status": "user not found"}
    
    # 3. Handle Events
    # Fixed the condition - now properly checks both events
    if event in ["subscription.create", "charge.success"]:
        # Get subscription code from Paystack API
        sub_code = await get_subscriptions(customer_email)
        
        if sub_code:
            admin.paystack_subscription_code = sub_code["sub_code"] 
            admin.paystack_email_token = sub_code["email_token"] 
            admin.manage_subscription_link = get_paystack_manage_link(sub_code["sub_code"])
            admin.is_active = True
            
           
        else:
            # If no subscription found but it's a charge.success, still activate
            if event == "charge.success":
                admin.is_active = True
            print(f"No subscription found for {customer_email}")

    elif event in ["subscription.disable", "subscription.not_renew", "invoice.payment_failed"]:
        # Revoke access
        admin.is_active = False

    # 4. Save Changes to DB
    session.add(admin)
    session.commit()
    session.refresh(admin)

    return {"status": "webhook processed"}
