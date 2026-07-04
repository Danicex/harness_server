from fastapi import APIRouter, HTTPException, status, Header, Form
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from app.database import SessionDep
from app.crud import get_admin_data, get_data_by_period
from app.auth.authentication import isAuthorized
from sqlmodel import select, func
from app.model import Product, Room, Sales, Booking  # Import your models

router = APIRouter(prefix="/analytics")

@router.get('/dashboard')
async def get_dashboard_data(
        session: SessionDep,
        date: Optional[str] = None,
        period: Optional[str] = None,
        # authorization: str = Header(...)
):
    auth = {
        "admin_id": 1
    }
    # token = authorization.split(" ")[1]
    # auth = isAuthorized(token)
    # if not auth:
    #     raise HTTPException(status_code=401, detail="Not authorized")
    # if auth.get("role") != "admin":
    #     raise HTTPException(status_code=403, detail="Not authorized - Admin access required")
    
    try:
        # Get all data (no date filter for totals)
        room_data = get_admin_data(auth["admin_id"], 'room', session)
        product_data = get_admin_data(auth["admin_id"], 'product', session)
        
        # Get filtered data by period
        if date:
            booking_data = get_data_by_period(auth["admin_id"], model_name='booking', session=session, date=date)
            sales_data = get_data_by_period(auth["admin_id"],model_name='sale', session=session, date=date)
        else:
            booking_data = get_data_by_period(auth["admin_id"], model_name='booking', session=session, period=period)
            sales_data = get_data_by_period(auth["admin_id"], model_name='sale', session=session, period=period)
       
        
        # Rest of your code remains the same...
        dashboard_data = {
            # Overview Statistics
            "overview": {
                "total_rooms": len(room_data),
                "total_products": len(product_data),
                "total_bookings": len(booking_data),
                "total_sales_transactions": len(sales_data),
                "date_range": date
            },
            
            # Room Statistics
            "rooms": {
                "all_rooms": [
                    {
                        "id": room.id,
                        "number": room.number,
                        "price": room.price,
                        "status": room.status,
                        "created_at": room.created_at
                    } for room in room_data
                ],
                "available_rooms": sum(1 for room in room_data if room.status == "available"),
                "occupied_rooms": sum(1 for room in room_data if room.status == "occupied"),
                "maintenance_rooms": sum(1 for room in room_data if room.status == "maintenance"),
                "total_room_revenue": sum(float(booking.price) for booking in booking_data if booking.price)
            },
            
            # Product Statistics
            "products": {
                "all_products": [
                    {
                        "id": product.id,
                        "name": product.name,
                        "price": product.price,
                        "category": product.category,
                        "quantity": product.quantity,
                        "created_at": product.created_at
                    } for product in product_data
                ],
                "total_products_value": sum(float(product.price) * int(product.quantity) 
                                           for product in product_data 
                                           if product.price and product.quantity),
                "categories": list(set(product.category for product in product_data if product.category)),
                "low_stock_products": [
                    {
                        "id": product.id,
                        "name": product.name,
                        "quantity": product.quantity
                    } for product in product_data 
                    if product.quantity and int(product.quantity) < 10
                ]
            },
            
            # Sales Statistics (filtered by date)
            "sales": {
                "transactions": [
                    {
                        "id": sale.id,
                        "product_name": sale.name,
                        "price": sale.price,
                        "quantity": sale.quantity,
                        "payment_method": sale.payment_method,
                        "staff_id": sale.staff_id,
                        "created_at": sale.created_at
                    } for sale in sales_data
                ],
                "total_revenue": sum(float(sale.price) * int(sale.quantity) 
                                    for sale in sales_data 
                                    if sale.price and sale.quantity),
                "total_items_sold": sum(int(sale.quantity) 
                                       for sale in sales_data 
                                       if sale.quantity),
                "payment_methods": {
                    method: sum(1 for sale in sales_data if sale.payment_method == method)
                    for method in set(sale.payment_method for sale in sales_data if sale.payment_method)
                },
                "average_transaction_value": (
                    sum(float(sale.price) * int(sale.quantity) for sale in sales_data if sale.price and sale.quantity) / 
                    len(sales_data) if sales_data else 0
                )
            },
            
            # Booking Statistics (filtered by date)
            "bookings": {
                "all_bookings": [
                    {
                        "id": booking.id,
                        "room_id": booking.room_id,
                        "customer_name": booking.customer_name,
                        "customer_email": booking.customer_email,
                        "price": booking.price,
                        "status": booking.status,
                        "check_in": booking.check_in,
                        "check_out": booking.check_out,
                        "payment_method": booking.payment_method,
                        "created_at": booking.created_at
                    } for booking in booking_data
                ],
                "total_booking_revenue": sum(float(booking.price) 
                                            for booking in booking_data 
                                            if booking.price),
                "booking_status": {
                    status: sum(1 for booking in booking_data if booking.status == status)
                    for status in set(booking.status for booking in booking_data if booking.status)
                },
                "active_bookings": sum(1 for booking in booking_data 
                                      if booking.status == "confirmed" or booking.status == "checked_in"),
                "average_booking_value": (
                    sum(float(booking.price) for booking in booking_data if booking.price) / 
                    len(booking_data) if booking_data else 0
                ),
                "occupancy_rate": (
                    (sum(1 for booking in booking_data if booking.status == "confirmed" or booking.status == "checked_in") / 
                     len(room_data) * 100) if room_data else 0
                )
            },
            
            # Performance Metrics
            "performance": {
                "revenue_comparison": {
                    "sales_revenue": sum(float(sale.price) * int(sale.quantity) 
                                        for sale in sales_data 
                                        if sale.price and sale.quantity),
                    "booking_revenue": sum(float(booking.price) 
                                          for booking in booking_data 
                                          if booking.price),
                    "total_revenue": (
                        sum(float(sale.price) * int(sale.quantity) for sale in sales_data if sale.price and sale.quantity) +
                        sum(float(booking.price) for booking in booking_data if booking.price)
                    )
                },
                "top_selling_products": sorted(
                    [
                        {
                            "name": sale.name,
                            "total_quantity": sum(int(s.quantity) for s in sales_data if s.name == sale.name),
                            "total_revenue": sum(float(s.price) * int(s.quantity) for s in sales_data if s.name == sale.name)
                        }
                        for sale in sales_data
                        if sale.name
                    ],
                    key=lambda x: x["total_revenue"],
                    reverse=True
                )[:5],  # Top 5 products
                
                "most_booked_rooms": sorted(
                    [
                        {
                            "room_id": booking.room_id,
                            "booking_count": sum(1 for b in booking_data if b.room_id == booking.room_id),
                            "total_revenue": sum(float(b.price) for b in booking_data if b.room_id == booking.room_id)
                        }
                        for booking in booking_data
                    ],
                    key=lambda x: x["booking_count"],
                    reverse=True
                )[:5]  # Top 5 rooms
            }
        }
        
        dashboard_data["generated_at"] = datetime.utcnow().isoformat()
        dashboard_data["admin_id"] = auth["admin_id"]
        
        return dashboard_data
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting dashboard data: {str(e)}"
        )   
        
        