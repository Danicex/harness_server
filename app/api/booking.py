# CRUD booking
from fastapi import APIRouter, HTTPException, Header, Form, status
from fastapi import status as http_status
from typing import Optional
from datetime import datetime
from app.database import SessionDep
from sqlmodel import select
from app.model import Customer, Room
from app.crud import create_data, update_data, delete_data, get_admin_data, get_single_data, get_data_by_period
from app.auth.authentication import isAuthorized
from app.services.mailer import send_mail
import random
import string

router = APIRouter(prefix="/booking")
def generate_reserve():
    reserve_id = (
            "".join(random.choices(string.ascii_uppercase, k=3))
            + "".join(random.choices(string.digits, k=7))
        )
    return reserve_id

def get_html(
  customer_name,
  reserve_id,
  room_number,
  check_in,
  check_out,
  duration,
  price,
  payment_method,
  status
):
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
</head>
<body style="font-family: Arial, Helvetica, sans-serif; color: #333;">
    <div style="max-width:600px;margin:auto;padding:20px;border:1px solid #ddd;border-radius:8px;">
        <h2 style="color:#2c3e50;">Booking Confirmation</h2>

        <p>Hello {customer_name},</p>

        <p>Your booking has been successfully confirmed.</p>

        <table style="width:100%;border-collapse:collapse;margin:20px 0;">
            <tr>
                <td><strong>Reservation ID</strong></td>
                <td>{reserve_id}</td>
            </tr>
            <tr>
                <td><strong>Room</strong></td>
                <td>{room_number}</td>
            </tr>
            <tr>
                <td><strong>Check-in</strong></td>
                <td>{check_in}</td>
            </tr>
            <tr>
                <td><strong>Check-out</strong></td>
                <td>{check_out}</td>
            </tr>
            <tr>
                <td><strong>Duration</strong></td>
                <td>{duration}</td>
            </tr>
            <tr>
                <td><strong>Price</strong></td>
                <td>{price}</td>
            </tr>
            <tr>
                <td><strong>Payment Method</strong></td>
                <td>{payment_method}</td>
            </tr>
            <tr>
                <td><strong>Status</strong></td>
                <td>{status}</td>
            </tr>
        </table>

        <p>
            Please keep your <strong>Reservation ID</strong> as you may be asked
            to provide it during check-in.
        </p>

        <p>We look forward to welcoming you!</p>

        <p>
            Regards,<br>
            <strong>Your Hotel Team</strong>
        </p>
    </div>
</body>
</html>
"""
    return html_content

@router.post('/create_booking')
async def create_booking(
    session: SessionDep,
    room_id: Optional[int] = Form(None),
    staff_id: Optional[int] = Form(None),
    price: Optional[str] = Form(None),
    room_number: Optional[str] = Form(None),
    status: Optional[str] = Form(None),
    duration: Optional[str] = Form(None),
    customer_email: Optional[str] = Form(None),
    customer_name: Optional[str] = Form(None),
    customer_phone: Optional[str] = Form(None),
    payment_method: Optional[str] = Form(None),
    check_in: Optional[str] = Form(None),
    check_out: Optional[str] = Form(None),
    authorization: str = Header(...)
):
    token = authorization.split(" ")[1]
    auth = isAuthorized(token)
    if not auth:
        raise HTTPException(status_code=401, detail="Not authorized")
    res_id = generate_reserve()

    try:
        booking_dict = {
            "admin_id": auth.get("admin_id"),
            "room_id": room_id,
            "room_number": room_number,
            "staff_id": auth.get("staff_id") if auth.get("staff_id") else staff_id,
            "price": price,
            "status": status,
            "reserve_id": res_id, 
            "duration": duration,
            "customer_email": customer_email,
            "customer_name": customer_name,
            "customer_phone": customer_phone,
            "payment_method": payment_method,
            "check_in": check_in,
            "check_out": check_out,
            "created_at": datetime.utcnow()
        }

        existing_customer = session.exec(select(Customer).where(Customer.email == customer_email)).first()
        if not existing_customer:
            new_customer = {
                "email": customer_email,
                "customer_name": customer_name,
                "phone": customer_phone,
                "admin_id": auth.get("admin_id")
            }
            create_data("customer", new_customer, session)
            
        success, booking = create_data("booking", booking_dict, session)
        await send_mail(
            to=customer_email,
            subject="Booking Confirmation",
            html=get_html(customer_name, res_id, room_number, check_in, check_out, duration, price, payment_method, status),
        )
        #update room status
        if status == "comfimed":
            update_data("room",room_id, {"status": "occupied"} ,session)
            
        if not success:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="Failed to create booking"
            )

        return booking  
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating booking: {str(e)}"
        )

@router.post('/customer_booking')
async def create_customer_booking(
    session: SessionDep,
    admin_id: int = Form(...),
    room_id: int = Form(...),
    price: Optional[str] = Form(None),
    room_number: Optional[str] = Form(None),
    duration: Optional[str] = Form(None),
    customer_email: str = Form(...),
    customer_name: str = Form(...),
    customer_phone: Optional[str] = Form(None),
    payment_method: Optional[str] = Form(None),
    check_in: Optional[str] = Form(None),
    check_out: Optional[str] = Form(None),
):
    """
    Public booking endpoint — used by the customer-facing website.
    No Authorization header: admin_id comes straight from form data,
    since this site is tied to a single hotel/admin.
    """
    try:
        room = session.get(Room, room_id)
        if not room:
            raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Room not found")

        if room.status and room.status.lower() == "occupied":
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="This room is no longer available"
            )
        res_id = generate_reserve()
        
        booking_dict = {
            "admin_id": admin_id,
            "room_id": room_id,
            "room_number": room_number or room.number,
            "staff_id": None,              
            "price": price or room.price,
            "status": "pending",            
            "reserve_id": res_id,            
            "duration": duration,
            "customer_email": customer_email,
            "customer_name": customer_name,
            "customer_phone": customer_phone,
            "payment_method": payment_method,
            "check_in": check_in,
            "check_out": check_out,
            "created_at": datetime.utcnow()
        }

        existing_customer = session.exec(select(Customer).where(Customer.email == customer_email)).first()
        if not existing_customer:
            new_customer = {
                "email": customer_email,
                "customer_name": customer_name,
                "phone": customer_phone,
                "admin_id": admin_id
            }
            create_data("customer", new_customer, session)

        success, booking = create_data("booking", booking_dict, session)
       
        await send_mail(
            to=customer_email,
            subject="Booking Confirmation",
            html=get_html(customer_name, res_id, room_number, check_in, check_out, duration, price, payment_method, status),
        )
        if not success:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="Failed to create booking"
            )


        return booking

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating booking: {str(e)}"
        )

@router.get("/get_bookings")
def read_bookings(
    session: SessionDep,
    authorization: str = Header(...)
):
    token = authorization.split(" ")[1]
    auth = isAuthorized(token)
    if not auth:
        raise HTTPException(status_code=401, detail="Not authorized")
   

    try:
        bookings = get_admin_data(auth["admin_id"], "booking", session)

        if not bookings:
            return {"message": "No bookings found", "bookings": []}

        return {"message": "Bookings retrieved successfully", "bookings": bookings}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving bookings: {str(e)}"
        )


@router.get("/{booking_id}")
def get_single_booking(
    session: SessionDep,
    booking_id: int,
    authorization: str = Header(...)
):
    token = authorization.split(" ")[1]
    auth = isAuthorized(token)
    if not auth:
        raise HTTPException(status_code=401, detail="Not authorized")
    

    try:
        booking = get_single_data(booking_id, "booking", session)

        if not booking:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Booking not found"
            )

        return {"message": "Booking retrieved successfully", "booking": booking}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving booking: {str(e)}"
        )

@router.get("/monthly/{month}", status_code=status.HTTP_200_OK)
@router.get("/period/{date}", status_code=status.HTTP_200_OK)
async def get_booking_period(
session: SessionDep,
   month: str = None,
   date: str = None,
   authorization: str = Header(...)
):
    token = authorization.split(" ")[1]
    auth = isAuthorized(token)
    if not auth:
        raise HTTPException(status_code=401, detail="Not authorized")
    staff_id = auth.get("staff_id")
    if month: 
        result = get_data_by_period(
            auth["admin_id"],
            "booking",
            session,
            staff_id,
            period=month,  
        )
    else:
        result = get_data_by_period(
            auth["admin_id"],
            "booking",
            session,
            staff_id,
            date=date,    
        )
    
    return result

@router.put('/update_booking/{booking_id}')
def update_booking(
    session: SessionDep,
    booking_id: int,
    room_id: Optional[int] = Form(None),
    staff_id: Optional[int] = Form(None),
    price: Optional[str] = Form(None),
    status: Optional[str] = Form(None),
    duration: Optional[str] = Form(None),
    customer_email: Optional[str] = Form(None),
    customer_name: Optional[str] = Form(None),
    customer_phone: Optional[str] = Form(None),
    payment_method: Optional[str] = Form(None),
    check_in: Optional[str] = Form(None),
    check_out: Optional[str] = Form(None),
    authorization: str = Header(...)
):
    token = authorization.split(" ")[1]
    auth = isAuthorized(token)
    if not auth:
        raise HTTPException(status_code=401, detail="Not authorized")
    

    try:
        # Get existing booking
        existing_booking = get_single_data(booking_id, "booking", session)
        if not existing_booking:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Booking not found"
            )

        # Verify admin owns this booking
        if existing_booking.admin_id != auth.get("admin_id"):
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update this booking"
            )

        # Prepare update dict (only include fields that are provided)
        booking_dict = {}

        if room_id is not None:
            booking_dict["room_id"] = room_id
        if staff_id is not None:
            booking_dict["staff_id"] = staff_id
        if price is not None:
            booking_dict["price"] = price
        if status is not None:
            booking_dict["status"] = status
        if duration is not None:
            booking_dict["duration"] = duration
        if customer_email is not None:
            booking_dict["customer_email"] = customer_email
        if customer_name is not None:
            booking_dict["customer_name"] = customer_name
        if customer_phone is not None:
            booking_dict["customer_phone"] = customer_phone
        if payment_method is not None:
            booking_dict["payment_method"] = payment_method
        if check_in is not None:
            booking_dict["check_in"] = check_in
        if check_out is not None:
            booking_dict["check_out"] = check_out
            
        if status == "checked_in":
            update_data("room", existing_booking.room_id, {"status": "occupied"} , session)
        # Update booking using CRUD function
        success, updated_booking = update_data("booking", booking_id, booking_dict, session)
        
            
        if not success:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="Failed to update booking"
            )

        return {"message": "Booking updated successfully", "booking": updated_booking}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating booking: {str(e)}"
        )


@router.delete('/delete_booking/{booking_id}')
def delete_booking(
    session: SessionDep,
    booking_id: int,
    # authorization: str = Header(...)
):
    # token = authorization.split(" ")[1]
    # auth = isAuthorized(token)
    # if not auth:
    #     raise HTTPException(status_code=401, detail="Not authorized")
    # if auth.get("role") != "admin":
    #     raise HTTPException(status_code=401, detail="Not authorized")
    auth = {
        "admin_id": 1
    }
    try:
        # Get existing booking
        existing_booking = get_single_data(booking_id, "booking", session)
        if not existing_booking:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Booking not found"
            )

        # Verify admin owns this booking
        if existing_booking.admin_id != auth.get("admin_id"):
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete this booking"
            )
            

        # Delete booking using CRUD function
        success = delete_data("booking", booking_id, session)

        if not success:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="Failed to delete booking"
            )

        return {"message": "Booking deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting booking: {str(e)}"
        )
        
        
        