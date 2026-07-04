from typing import Optional
from app.database import SessionDep
from sqlmodel import select, and_, desc, func
from sqlalchemy.sql import extract
from app.model import Admin, Product, HotelProfile, Sales, Staff, Booking, Customer, Inbox, Blog, Dataset, CallLog, Room, HotelProfile
from datetime import datetime, timedelta

obj_map = {
    "product": Product,
    "hotel_profile": HotelProfile,
    "customer": Customer,
    "sale": Sales,
    "booking": Booking,
    "staff": Staff,
    "admin": Admin,
    "profile": HotelProfile,
    "inbox": Inbox,
    "blog": Blog,
    "room": Room,
    "call_log": CallLog,
    "dataset": Dataset,
}

def read_data(obj_name: str, session: SessionDep, limit: int = 100):
    """
    Read multiple records with rate limit
    """
    model_class = obj_map.get(obj_name.lower())
    if not model_class:
        return None
    
    data = session.exec(
        select(model_class).limit(limit)
    ).all()
    return data



def get_single_data(obj_id: int, obj_name: str, session: SessionDep):
    """
    Get a single record by ID
    """
    model_class = obj_map.get(obj_name.lower())
    if not model_class:
        return None
    
    data = session.exec(
        select(model_class).where(model_class.id == obj_id)
    ).first()
    return data

def get_admin_data(admin_id: int, obj_name: str, session: SessionDep):
    model_class = obj_map.get(obj_name.lower())
    if not model_class:
        return None
    
    # Build the query
    query = select(model_class).where(model_class.admin_id == admin_id)
    
    query =query.order_by(model_class.created_at.desc())
    
    data = session.exec(query).all()
    return data


def get_admin_data_single(admin_id: int, obj_name: str, session: SessionDep):
    model_class = obj_map.get(obj_name.lower())
    if not model_class:
        return None
    
    # Build the query
    query = select(model_class).where(model_class.admin_id == admin_id)

    
    data = session.exec(query).first()
    return data

def create_data(obj_name: str, data_obj, session):
    """
    Create a new record
    """
    model_class = obj_map.get(obj_name.lower())
    if not model_class:
        return False, None
    
    instance = model_class(**data_obj.dict() if hasattr(data_obj, 'dict') else data_obj)
    session.add(instance)
    session.commit()
    session.refresh(instance)
    return True, instance

def update_data(obj_name: str, obj_id: int, data_obj, session: SessionDep):
    """
    Update an existing record
    """
    model_class = obj_map.get(obj_name.lower())
    if not model_class:
        return False, None
    
    existing = session.exec(
        select(model_class).where(model_class.id == obj_id)
    ).first()
    
    if not existing:
        return False, None
    
    update_data = data_obj.dict() if hasattr(data_obj, 'dict') else data_obj
    for key, value in update_data.items():
        if value is not None and hasattr(existing, key):
            setattr(existing, key, value)
    
    session.add(existing)
    session.commit()
    session.refresh(existing)
    return True, existing

def delete_data(obj_name: str, obj_id: int, session: SessionDep):
    """
    Delete a record
    """
    model_class = obj_map.get(obj_name.lower())
    if not model_class:
        return False
    
    existing = session.exec(
        select(model_class).where(model_class.id == obj_id)
    ).first()
    
    if not existing:
        return False
    
    session.delete(existing)
    session.commit()
    return True



def get_data_by_period(
    admin_id: int,
    model_name: str,
    session: SessionDep, 
    staff_id: Optional[int] = None, 
    date: Optional[str] = None, 
    period: Optional[str] = None
):
    model_class = obj_map.get(model_name.lower())
    if not model_class:
        return False
    
    query = select(model_class).where(model_class.admin_id == admin_id)
    
    if date:
        parsed_date = datetime.strptime(date, "%Y-%m-%d")
        query = query.where(func.date(model_class.created_at) == parsed_date.date())
        if staff_id:
            query = query.where(model_class.staff_id == staff_id)  # filter by staff_id
    
    elif period:
        year_num = int(period.split('-')[0])
        month_num = int(period.split('-')[1])
        query = query.where(
            extract('year', model_class.created_at) == year_num,
            extract('month', model_class.created_at) == month_num
        )
        if staff_id:
            query = query.where(model_class.staff_id == staff_id)  # filter by staff_id
    
    query = query.order_by(desc(model_class.created_at))
    result = session.exec(query).all()
    return result

