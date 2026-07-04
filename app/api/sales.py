# CRUD sales
from fastapi import APIRouter, HTTPException, Header, Form, status
from fastapi import status as http_status
from typing import Optional
from datetime import datetime
from app.database import SessionDep
from app.model import Sales
from app.crud import create_data, update_data, delete_data, get_admin_data, get_single_data, get_data_by_period
from app.auth.authentication import isAuthorized
import json

router = APIRouter(prefix="/sales")


@router.post('/create_sale')
def create_sale(
    session: SessionDep,
    staff_id: Optional[int] = Form(None),
    payment_method: Optional[str] = Form(None),
    customer_name: Optional[str] = Form(None),
    total_amount: Optional[int] = Form(None),
    product_data: Optional[str] = Form(None), 
    authorization: str = Header(...)
):
    token = authorization.split(" ")[1]
    auth = isAuthorized(token)
    if not auth:
        raise HTTPException(status_code=401, detail="Not authorized")
    
    try:
        # Parse product_data JSON
        products = json.loads(product_data) if product_data else []
        
        if not products:
            raise HTTPException(
                status_code=422, 
                detail="At least one product is required"
            )
        
        # Process each product and calculate total
        total_amount = 0
        products_info = []
        
        for product_item in products:
            product_id = product_item.get('product_id')
            quantity = int(product_item.get('quantity', 1))
            price = float(product_item.get('price', 0))
            
            # Get product from database
            existing_product = get_single_data(product_id, "product", session)
            if not existing_product:
                raise HTTPException(
                    status_code=422, 
                    detail=f"Product with ID {product_id} not found"
                )
            
            # Check stock availability
            current_quantity = int(existing_product.quantity)
            new_quantity = current_quantity - quantity
            
            if new_quantity < 0:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Insufficient stock for {existing_product.name}. Available: {current_quantity}, Requested: {quantity}"
                )
            

            update_data("product", product_id, {"quantity": new_quantity}, session)
            
            # Calculate total
            item_total = price * quantity
            total_amount += item_total
            
            # Store product info
            products_info.append({
                "product_id": product_id,
                "product_name": existing_product.name,
                "price": price,
                "quantity": quantity,
                "subtotal": item_total
            })
        
        # Create sale record
        sale_dict = {
            "admin_id": auth.get("admin_id"),
            "staff_id": staff_id if staff_id else auth.get("staff_id"),
            "customer_name": customer_name,  
            "payment_method": payment_method,
            "total_amount": total_amount,
            "products_data": products_info, 
            "created_at": datetime.utcnow()
        }
        
        # Create sale using helper function
        success, sale = create_data("sale", sale_dict, session)
        
        if not success:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="Failed to create sale"
            )
        
        return {
            "message": "Sale created successfully", 
            "sale": sale,
            "total_amount": total_amount,
            "products": products_info
        }
        
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=422,
            detail="Invalid product data format"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating sale: {str(e)}"
        )


@router.get("/get_sales")
def read_sales(
    session: SessionDep,
    authorization: str = Header(...)
):
    token = authorization.split(" ")[1]
    auth = isAuthorized(token)
    if not auth:
        raise HTTPException(status_code=401, detail="Not authorized")
    

    try:
        sales = get_admin_data(auth["admin_id"], "sale", session)

        if not sales:
            return {"message": "No sales found", "sales": []}

        return sales
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving sales: {str(e)}"
        )


@router.get("/{sale_id}")
def get_single_sale(
    session: SessionDep,
    sale_id: int,
    authorization: str = Header(...)
):
    token = authorization.split(" ")[1]
    auth = isAuthorized(token)
    if not auth:
        raise HTTPException(status_code=401, detail="Not authorized")
    

    try:
        sale = get_single_data(sale_id, "sale", session)

        if not sale:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Sale not found"
            )

        return {"message": "Sale retrieved successfully", "sale": sale}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving sale: {str(e)}"
        )


@router.put('/update_sale/{sale_id}')
def update_sale(
    session: SessionDep,
    sale_id: int,
    product_id: Optional[int] = Form(None),
    staff_id: Optional[int] = Form(None),
    price: Optional[str] = Form(None),
    quantity: Optional[str] = Form(None),
    name: Optional[str] = Form(None),
    payment_method: Optional[str] = Form(None),
    authorization: str = Header(...)
):
    token = authorization.split(" ")[1]
    auth = isAuthorized(token)
    if not auth:
        raise HTTPException(status_code=401, detail="Not authorized")
    

    try:
        # Get existing sale
        existing_sale = get_single_data(sale_id, "sale", session)
        if not existing_sale:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Sale not found"
            )

        # Verify admin owns this sale
        if existing_sale.admin_id != auth.get("admin_id"):
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update this sale"
            )

        # Prepare update dict (only include fields that are provided)
        sale_dict = {}

        if product_id is not None:
            sale_dict["product_id"] = product_id
        if staff_id is not None:
            sale_dict["staff_id"] = staff_id
        if price is not None:
            sale_dict["price"] = price
        if quantity is not None:
            sale_dict["quantity"] = quantity
        if name is not None:
            sale_dict["name"] = name
        if payment_method is not None:
            sale_dict["payment_method"] = payment_method

        # Update sale using CRUD function
        success, updated_sale = update_data("sale", sale_id, sale_dict, session)

        if not success:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="Failed to update sale"
            )

        return {"message": "Sale updated successfully", "sale": updated_sale}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating sale: {str(e)}"
        )

@router.get("/monthly/{month}", status_code=status.HTTP_200_OK)
@router.get("/period/{date}", status_code=status.HTTP_200_OK)
async def get_sales_period(
session: SessionDep,
   month: str = None,
   date: str = None,
   authorization: str = Header(...)
):
    token = authorization.split(" ")[1]
    auth = isAuthorized(token)
    if not auth:
        raise HTTPException(status_code=401, detail="Not authorized")
    
    
    if month: 
        result = get_data_by_period(
            auth["admin_id"],
            "sale",
            session=session,
            period=month,  
        )
    else:
        result = get_data_by_period(
            auth["admin_id"],
            "sale",
            session=session,
            date=date,    
        )
    
    return result


# @router.delete('/delete_sale/{sale_id}')
# def delete_sale(
#     session: SessionDep,
#     sale_id: int,
#     authorization: str = Header(...)
# ):
#     token = authorization.split(" ")[1]
#     auth = isAuthorized(token)
#     if not auth:
#         raise HTTPException(status_code=401, detail="Not authorized")
#     if auth.get("role") != "admin":
#         raise HTTPException(status_code=401, detail="Not authorized")

#     try:
#         # Get existing sale
#         existing_sale = get_single_data(sale_id, "sale", session)
#         if not existing_sale:
#             raise HTTPException(
#                 status_code=http_status.HTTP_404_NOT_FOUND,
#                 detail="Sale not found"
#             )

#         # Verify admin owns this sale
#         if existing_sale.admin_id != auth.get("admin_id"):
#             raise HTTPException(
#                 status_code=http_status.HTTP_403_FORBIDDEN,
#                 detail="Not authorized to delete this sale"
#             )

#         # Delete sale using CRUD function
#         success = delete_data("sale", sale_id, session)

#         if not success:
#             raise HTTPException(
#                 status_code=http_status.HTTP_400_BAD_REQUEST,
#                 detail="Failed to delete sale"
#             )

#         return {"message": "Sale deleted successfully"}

#     except HTTPException:
#         raise
#     except Exception as e:
#         raise HTTPException(
#             status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"Error deleting sale: {str(e)}"
#         )
        
        