# CRUD product
from fastapi import APIRouter, HTTPException, status, Header, UploadFile, File, Form, Query
from typing import Optional
from datetime import datetime
from app.database import SessionDep
from app.model import Product
from app.crud import create_data, update_data, delete_data, get_admin_data, get_single_data
from app.auth.authentication import isAuthorized
from app.services.upload import handle_file_upload

router = APIRouter(prefix="/product")

@router.post('/create_product')
async def create_product(
    session: SessionDep,
    name: str = Form(...),
    price: str = Form(...),
    description: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    quantity: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    authorization: str = Header(...)
):
    token = authorization.split(" ")[1]
    auth = isAuthorized(token)
    if not auth:
        raise HTTPException(status_code=401, detail="Not authorized")
    if auth.get("role") != "admin":
        raise HTTPException(status_code=401, detail="Not authorized")
    
    try:
        # Handle file upload
        image_url = None
        if image:
            image_url = await handle_file_upload(image)
        
        # Prepare data for database
        product_dict = {
            "admin_id": auth.get("admin_id"),
            "name": name,
            "price": price,
            "description": description,
            "category": category,
            "quantity": quantity,
            "image_url": image_url,
            "created_at": datetime.utcnow()
        }
        
        success, product = create_data("product", product_dict, session)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create product"
            )
        
        return {"message": "Product created successfully", "product": product}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating product: {str(e)}"
        )


@router.get("/get_products")
def read_products(
    session: SessionDep,
    admin_id: Optional[int] = Query(None),
    authorization: Optional[str] = Header(None)
):
    resolved_admin_id = admin_id

    if authorization:
        token = authorization.split(" ")[1]
        auth = isAuthorized(token)
        if not auth:
            raise HTTPException(status_code=401, detail="Not authorized")
        resolved_admin_id = auth["admin_id"]  # token wins over query param

    if not resolved_admin_id:
        raise HTTPException(status_code=400, detail="admin_id is required")
    
   
    try:
        products = get_admin_data(resolved_admin_id, "product", session)
        
        if not products:
            return {"message": "No products found", "products": []}
        
        return products
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving products: {str(e)}"
        )


@router.get("/{product_id}")
def get_single_product(
    session: SessionDep,
    product_id: int,
    authorization: str = Header(...)
):
    token = authorization.split(" ")[1]
    auth = isAuthorized(token)
    if not auth:
        raise HTTPException(status_code=401, detail="Not authorized")
    if auth.get("role") != "admin":
        raise HTTPException(status_code=401, detail="Not authorized")
    
    try:
        product = get_single_data(product_id, "product", session)
        
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found"
            )
        
        return {"message": "Product retrieved successfully", "product": product}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving product: {str(e)}"
        )


@router.put('/update_product/{product_id}')
async def update_product(
    session: SessionDep,
    product_id: int,
    name: Optional[str] = Form(None),
    price: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    quantity: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    authorization: str = Header(...)
):
    token = authorization.split(" ")[1]
    auth = isAuthorized(token)
    if not auth:
        raise HTTPException(status_code=401, detail="Not authorized")
    if auth.get("role") != "admin":
        raise HTTPException(status_code=401, detail="Not authorized")
    
    try:
        # Get existing product
        existing_product = get_single_data(product_id, "product", session)
        if not existing_product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found"
            )
        
        # Verify admin owns this product
        if existing_product.admin_id != auth.get("admin_id"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update this product"
            )
        
        # Prepare update dict (only include fields that are provided)
        product_dict = {}
        
        if name is not None:
            product_dict["name"] = name
        if price is not None:
            product_dict["price"] = price
        if description is not None:
            product_dict["description"] = description
        if category is not None:
            product_dict["category"] = category
        if quantity is not None:
            product_dict["quantity"] = quantity
        
        # Handle file upload if new file provided
        if image:
            image_url = await handle_file_upload(image)
            product_dict["image_url"] = image_url
        
        # Update product using CRUD function
        success, updated_product = update_data("product", product_id, product_dict, session)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to update product"
            )
        
        return {"message": "Product updated successfully", "product": updated_product}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating product: {str(e)}"
        )


@router.delete('/delete_product/{product_id}')
def delete_product(
    session: SessionDep,
    product_id: int,
    authorization: str = Header(...)
):
    token = authorization.split(" ")[1]
    auth = isAuthorized(token)
    if not auth:
        raise HTTPException(status_code=401, detail="Not authorized")
    if auth.get("role") != "admin":
        raise HTTPException(status_code=401, detail="Not authorized")
    
    try:
        # Get existing product
        existing_product = get_single_data(product_id, "product", session)
        if not existing_product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found"
            )
        
        # Verify admin owns this product
        if existing_product.admin_id != auth.get("admin_id"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete this product"
            )
        
        # Delete product using CRUD function
        success = delete_data("product", product_id, session)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to delete product"
            )
        
        return {"message": "Product deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting product: {str(e)}"
        )