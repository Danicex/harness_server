from sqlmodel import SQLModel, Field, Relationship, JSON, Column
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from sqlalchemy.dialects.postgresql import JSONB

class Admin(SQLModel, table=True):
    __tablename__ = "admin"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    password: str
    role: str
    jwt_token: Optional[str] = None
    reset_password_token: Optional[str] = None
    reset_password_expiry: Optional[datetime] = None
    updated_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    
    dataset: List["Dataset"] = Relationship(back_populates="admin")
    products: List["Product"] = Relationship(back_populates="admin")
    customers: List["Customer"] = Relationship(back_populates="admin")
    staff: List["Staff"] = Relationship(back_populates="admin")
    orders: List["Sales"] = Relationship(back_populates="admin")
    rooms: List["Room"] = Relationship(back_populates="admin")
    sales: List["Sales"] = Relationship(back_populates="admin")
    bookings: List["Booking"] = Relationship(back_populates="admin")
    hotel_profile: Optional["HotelProfile"] = Relationship(back_populates="admin", sa_relationship_kwargs={"uselist": False})
    inboxes: List["Inbox"] = Relationship(back_populates="admin")
    blogs: List["Blog"] = Relationship(back_populates="admin")
    datasets: List["Dataset"] = Relationship(back_populates="admin")
    call_logs: List["CallLog"] = Relationship(back_populates="admin")

class Product(SQLModel, table=True):
    __tablename__ = "products"
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
    
class Room(SQLModel, table=True):
    __tablename__ = "rooms"
    id: Optional[int] = Field(default=None, primary_key=True)
    admin_id: Optional[int] = Field(default=None, foreign_key="admin.id")
    number: str
    room_type: Optional[str] = None
    description: Optional[str] = None
    price: str
    status: Optional[str] = None
    image_url: Optional[str] = None
    pictures: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationship back to admin
    admin: Optional[Admin] = Relationship(back_populates="rooms")
        
class Customer(SQLModel, table=True):
    __tablename__ = "customers"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    customer_name: Optional[str] = None
    phone: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    admin_id: int = Field(foreign_key="admin.id")
    admin: Optional[Admin] = Relationship(back_populates="customers")

class Staff(SQLModel, table=True):
    __tablename__ = "staff"
    id: Optional[int] = Field(default=None, primary_key=True)
    admin_id: Optional[int] = Field(default=None, foreign_key="admin.id")
    name: str
    bio: Optional[str] = None
    role: Optional[str] = None
    cv_url: Optional[str] = None
    image_url: Optional[str] = None
    email: str = Field(index=True, unique=True)
    password: str
    prev_password: str
    jwt_token: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationship back to admin
    admin: Optional[Admin] = Relationship(back_populates="staff")
    

    
class Sales(SQLModel, table=True):
    __tablename__ = "sales"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    admin_id: Optional[int] = Field(default=None, foreign_key="admin.id")
    staff_id: Optional[int] = None
    customer_name: Optional[str] = None
    payment_method: Optional[str] = None
    total_amount: float = Field(default=0.0)
    products_data: Optional[List[Dict[str, Any]]] = Field(default=None, sa_type=JSON)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    
    # Relationships
    admin: Optional["Admin"] = Relationship(back_populates="sales")
    
class Booking(SQLModel, table=True):
    __tablename__ = "bookings"
    id: Optional[int] = Field(default=None, primary_key=True)
    admin_id: Optional[int] = Field(default=None, foreign_key="admin.id")
    room_id: int = Field(default=None, foreign_key="rooms.id")
    staff_id: Optional[int] = Field(default=None, foreign_key="staff.id")
    room_number: Optional[str] = None
    price: Optional[str] = None
    status: Optional[str] = None
    reserve_id: Optional[str] = None
    duration: Optional[str] = None
    customer_email: Optional[str] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    payment_method: Optional[str] = None
    check_in: Optional[str] = None
    check_out: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    admin: Optional[Admin] = Relationship(back_populates="bookings")
    room: Optional[Room] = Relationship()
    staff: Optional[Staff] = Relationship()
                   
class HotelProfile(SQLModel, table=True):
    __tablename__ = "hotel_profile"   
    id: Optional[int] = Field(default=None, primary_key=True)
    admin_id: Optional[int] = Field(default=None, foreign_key="admin.id", unique=True) 
    email: str = Field(index=True, unique=True)
    name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    description: Optional[str] = None
    hotel_name: Optional[str] = None
    website_url: Optional[str] = None
    agent_phone: Optional[str] = None
    social_links: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    image_url: Optional[str] = None
    
    admin: Optional["Admin"] = Relationship(back_populates="hotel_profile")

class Inbox(SQLModel, table=True):
    __tablename__ = "inbox"
    id: Optional[int] = Field(default=None, primary_key=True)
    admin_id: Optional[int] = Field(default=None, foreign_key="admin.id")
    email: Optional[str] = None
    body: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    admin: Optional[Admin] = Relationship(back_populates="inboxes")
             
class Blog(SQLModel, table=True):
    __tablename__ = "blogs"
    id: Optional[int] = Field(default=None, primary_key=True)
    admin_id: Optional[int] = Field(default=None, foreign_key="admin.id")
    title: str
    category: str = Field(default="public")
    description: Optional[str] = None
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationship back to admin
    admin: Optional[Admin] = Relationship(back_populates="blogs")
    
class Dataset(SQLModel, table=True):
    __tablename__ = "dataset"

    id: Optional[int] = Field(default=None, primary_key=True)
    admin_id: Optional[int] = Field(default=None, foreign_key="admin.id", unique=True) 
    title: str
    description: Optional[str] = None
    intent: Optional[List[Dict[str, Any]]] = Field(
        default_factory=list,
        sa_type=JSON
    )
    admin: Optional["Admin"] = Relationship(back_populates="dataset")

    
class CallLog(SQLModel, table=True):
    __tablename__ = "call_logs"
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(index=True)
    status: str = Field(default="active")  
    duration: str
    sentiment: str
    admin_id: int = Field(foreign_key="admin.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    admin: Admin = Relationship(back_populates="call_logs")