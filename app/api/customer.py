# CRUD customer
from fastapi import APIRouter, HTTPException, status, Header, Form, UploadFile, File
from typing import Optional
from datetime import datetime
from app.database import SessionDep
from app.model import Customer
from app.crud import create_data, update_data, delete_data, get_admin_data, get_single_data
from app.auth.authentication import isAuthorized
import csv
import io

router = APIRouter(prefix="/customer")

@router.post('/create_customer')
def create_customer(
    session: SessionDep,
    customer_name: str = Form(...),
    email: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    authorization: str = Header(...)
):
    token = authorization.split(" ")[1]
    auth = isAuthorized(token)
    if not auth:
        raise HTTPException(status_code=401, detail="Not authorized")
    if auth.get("role") != "admin":
        raise HTTPException(status_code=401, detail="Not authorized")

    try:
        customer_dict = {
            "admin_id": auth.get("admin_id"),
            "customer_name": customer_name,
            "email": email,
            "phone": phone,
        }

        success, customer = create_data("customer", customer_dict, session)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create customer"
            )

        return {"message": "Customer created successfully", "customer": customer}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating customer: {str(e)}"
        )


@router.get("/get_customers")
def read_customers(
    session: SessionDep,
    authorization: str = Header(...)
):
    token = authorization.split(" ")[1]
    auth = isAuthorized(token)
    if not auth:
        raise HTTPException(status_code=401, detail="Not authorized")
    if auth.get("role") != "admin":
        raise HTTPException(status_code=401, detail="Not authorized")

    try:
        customers = get_admin_data(auth["admin_id"], "customer", session)

        if not customers:
            return {"message": "No customers found", "customers": []}

        return customers
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving customers: {str(e)}"
        )


@router.get("/{customer_id}")
def get_single_customer(
    session: SessionDep,
    customer_id: int,
    authorization: str = Header(...)
):
    token = authorization.split(" ")[1]
    auth = isAuthorized(token)
    if not auth:
        raise HTTPException(status_code=401, detail="Not authorized")
    if auth.get("role") != "admin":
        raise HTTPException(status_code=401, detail="Not authorized")

    try:
        customer = get_single_data(customer_id, "customer", session)

        if not customer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer not found"
            )

        return {"message": "Customer retrieved successfully", "customer": customer}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving customer: {str(e)}"
        )


@router.put('/update_customer/{customer_id}')
def update_customer(
    session: SessionDep,
    customer_id: int,
    customer_name: str = Form(...),
    email: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    authorization: str = Header(...)
):
    token = authorization.split(" ")[1]
    auth = isAuthorized(token)
    if not auth:
        raise HTTPException(status_code=401, detail="Not authorized")
    if auth.get("role") != "admin":
        raise HTTPException(status_code=401, detail="Not authorized")

    try:
        # Get existing customer
        existing_customer = get_single_data(customer_id, "customer", session)
        if not existing_customer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer not found"
            )

        # Verify admin owns this customer
        if existing_customer.admin_id != auth.get("admin_id"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update this customer"
            )

        # Prepare update dict (only include fields that are provided)
        customer_dict = {}

        if customer_name is not None:
            customer_dict["customer_name"] = customer_name
        if email is not None:
            customer_dict["email"] = email
        if phone is not None:
            customer_dict["phone"] = phone
     

        customer_dict["updated_at"] = datetime.utcnow()

        # Update customer using CRUD function
        success, updated_customer = update_data("customer", customer_id, customer_dict, session)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to update customer"
            )

        return {"message": "Customer updated successfully", "customer": updated_customer}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating customer: {str(e)}"
        )
        
@router.post('/bulk_upload_customers')
async def bulk_upload_customers(
    session: SessionDep,
    file: UploadFile = File(...),
    # authorization: str = Header(...)
):
    # token = authorization.split(" ")[1]
    # auth = isAuthorized(token)
    # if not auth:
    #     raise HTTPException(status_code=401, detail="Not authorized")
    # if auth.get("role") != "admin":
    #     raise HTTPException(status_code=401, detail="Not authorized")
    auth = {
        "admin_id": 2
    }
    try:
        # Read CSV file
        contents = await file.read()
        decoded = contents.decode('utf-8')
        csv_reader = csv.DictReader(io.StringIO(decoded))
        
        created_customers = []
        failed_customers = []
        
        for row in csv_reader:
            try:
                customer_dict = {
                    "admin_id": auth.get("admin_id"),
                    "customer_name": row.get('customer_name'),
                    "email": row.get('email'),
                    "phone": row.get('phone'),
                }
                
                # Validate required fields
                if not customer_dict['customer_name']:
                    failed_customers.append({"row": row, "reason": "customer_name is required"})
                    continue
                
                success, customer = create_data("customer", customer_dict, session)
                
                if success:
                    created_customers.append(customer)
                else:
                    failed_customers.append({"row": row, "reason": "Database error"})
                    
            except Exception as e:
                failed_customers.append({"row": row, "reason": str(e)})
        
        return {
            "message": f"Successfully created {len(created_customers)} customers",
            "total_created": len(created_customers),
            "total_failed": len(failed_customers),
            "failed_customers": failed_customers if failed_customers else None
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing bulk upload: {str(e)}"
        )

@router.delete('/delete_customer/{customer_id}')
def delete_customer(
    session: SessionDep,
    customer_id: int,
    authorization: str = Header(...)
):
    token = authorization.split(" ")[1]
    auth = isAuthorized(token)
    if not auth:
        raise HTTPException(status_code=401, detail="Not authorized")
    if auth.get("role") != "admin":
        raise HTTPException(status_code=401, detail="Not authorized")

    try:
        # Get existing customer
        existing_customer = get_single_data(customer_id, "customer", session)
        if not existing_customer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer not found"
            )

        # Verify admin owns this customer
        if existing_customer.admin_id != auth.get("admin_id"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete this customer"
            )

        # Delete customer using CRUD function
        success = delete_data("customer", customer_id, session)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to delete customer"
            )

        return {"message": "Customer deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting customer: {str(e)}"
        )