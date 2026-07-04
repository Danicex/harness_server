from fastapi import APIRouter, HTTPException, Form, Header, status
from typing import Optional, List, Dict, Any
from datetime import datetime
import json
import http_status
from app.models import Sales
from app.database import SessionDep
from app.auth.authentication import isAuthorized
from app.crud import get_single_data, create_data, update_data

router = APIRouter()


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
        # Get all sales for this admin using helper function
        from app.crud import get_all_data
        sales = get_all_data("sale", session, filters={"admin_id": auth.get("admin_id")})
        
        if not sales:
            return {"message": "No sales found", "sales": []}
        
        return {
            "message": "Sales retrieved successfully",
            "sales": sales,
            "count": len(sales)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving sales: {str(e)}"
        )


@router.get("/get_sale/{sale_id}")
def get_single_sale(
    sale_id: int,
    session: SessionDep,
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
                detail="Not authorized to view this sale"
            )
        
        return {
            "message": "Sale retrieved successfully",
            "sale": existing_sale
        }
        
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
    staff_id: Optional[int] = Form(None),
    payment_method: Optional[str] = Form(None),
    product_data: Optional[str] = Form(None),  # JSON string of updated products
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
        
        # Prepare update dict
        sale_dict = {}
        
        # If updating products, handle stock adjustments
        if product_data:
            products = json.loads(product_data)
            
            # First, restore stock from old products
            if existing_sale.products_data:
                for old_product in existing_sale.products_data:
                    old_product_id = old_product.get("product_id")
                    old_quantity = old_product.get("quantity", 0)
                    
                    # Restore stock
                    product = get_single_data(old_product_id, "product", session)
                    if product:
                        restored_quantity = int(product.quantity) + old_quantity
                        update_data("product", old_product_id, {"quantity": restored_quantity}, session)
            
            # Then process new products and deduct stock
            new_total = 0
            new_products_info = []
            
            for product_item in products:
                product_id = product_item.get('product_id')
                quantity = int(product_item.get('quantity', 1))
                price = float(product_item.get('price', 0))
                
                # Get product from database
                product = get_single_data(product_id, "product", session)
                if not product:
                    raise HTTPException(
                        status_code=422, 
                        detail=f"Product with ID {product_id} not found"
                    )
                
                # Check stock
                current_quantity = int(product.quantity)
                new_quantity = current_quantity - quantity
                
                if new_quantity < 0:
                    raise HTTPException(
                        status_code=400, 
                        detail=f"Insufficient stock for {product.name}"
                    )
                
                # Update product quantity
                update_data("product", product_id, {"quantity": new_quantity}, session)
                
                # Calculate total
                item_total = price * quantity
                new_total += item_total
                
                new_products_info.append({
                    "product_id": product_id,
                    "product_name": product.name,
                    "price": price,
                    "quantity": quantity,
                    "subtotal": item_total
                })
            
            # Update sale with new product data
            sale_dict["products_data"] = new_products_info
            sale_dict["total_amount"] = new_total
        
        # Update other fields
        if staff_id is not None:
            sale_dict["staff_id"] = staff_id
        if payment_method is not None:
            sale_dict["payment_method"] = payment_method
        
        # Only update if there are changes
        if sale_dict:
            sale_dict["updated_at"] = datetime.utcnow()
            success, updated_sale = update_data("sale", sale_id, sale_dict, session)
            
            if not success:
                raise HTTPException(
                    status_code=http_status.HTTP_400_BAD_REQUEST,
                    detail="Failed to update sale"
                )
            
            return {"message": "Sale updated successfully", "sale": updated_sale}
        else:
            return {"message": "No changes made", "sale": existing_sale}
        
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=422,
            detail="Invalid product data format"
        )
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating sale: {str(e)}"
        )


@router.delete('/delete_sale/{sale_id}')
def delete_sale(
    sale_id: int,
    session: SessionDep,
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
                detail="Not authorized to delete this sale"
            )
        
        # Restore product quantities before deleting
        if existing_sale.products_data:
            for product_info in existing_sale.products_data:
                product_id = product_info.get("product_id")
                quantity = product_info.get("quantity", 0)
                
                product = get_single_data(product_id, "product", session)
                if product:
                    restored_quantity = int(product.quantity) + quantity
                    update_data("product", product_id, {"quantity": restored_quantity}, session)
        
        # Delete sale using helper function
        from app.crud import delete_data
        success = delete_data("sale", sale_id, session)
        
        if not success:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="Failed to delete sale"
            )
        
        return {
            "message": "Sale deleted successfully",
            "sale_id": sale_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting sale: {str(e)}"
        )