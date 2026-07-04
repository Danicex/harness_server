# CRUD staff
from fastapi import APIRouter, HTTPException, status, Header, UploadFile, File, Form
from fastapi import status as http_status
from typing import Optional
from datetime import datetime
from app.database import SessionDep
from app.model import Staff
from app.crud import create_data, update_data, delete_data, get_admin_data, get_single_data
from app.auth.authentication import isAuthorized,  hash_password, create_jwt_token
from app.services.upload import handle_file_upload
from sqlmodel import select


router = APIRouter(prefix="/staff")

@router.post('/create_staff')
async def create_staff(
    session: SessionDep,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    bio: Optional[str] = Form(None),
    role: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    cv: Optional[UploadFile] = File(None),
    authorization: str = Header(...)
):
    token = authorization.split(" ")[1]
    auth = isAuthorized(token)  
    if not auth:
        raise HTTPException(status_code=401, detail="Not authorized")
    if auth.get("role") != "admin":
        raise HTTPException(status_code=401, detail="Not authorized")
    
    try:
        hashed_password = hash_password(password)
        jwt_token = create_jwt_token(email, role)
        # Handle file uploads
        image_url = None
        if image:
            image_url = await handle_file_upload(image)

        cv_url = None
        if cv:
            cv_url = await handle_file_upload(cv )

        # Prepare data for database
        staff_dict = {
            "admin_id": auth.get("admin_id"),
            "name": name,
            "email": email,
            "password": hashed_password,
            "prev_password": password,
            "jwt_token": jwt_token,
            "bio": bio,
            "role": role,
            "image_url": image_url,
            "cv_url": cv_url,
            "created_at": datetime.utcnow()
        }

        success, staff = create_data("staff", staff_dict, session)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create staff"
            )

        return {"message": "Staff created successfully", "staff": staff}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating staff: {str(e)}"
        )


@router.get("/get_staff")
def read_staff(
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
        staff_list = get_admin_data(auth["admin_id"], "staff", session)

        if not staff_list:
            return {"message": "No staff found", "staff": []}

        return  staff_list
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving staff: {str(e)}"
        )


# @router.get("/{staff_id}")
# def get_single_staff(
#     session: SessionDep,
#     staff_id: int,
#     authorization: str = Header(...)
# ):
#     token = authorization.split(" ")[1]
#     auth = isAuthorized(token)
#     if not auth:
#         raise HTTPException(status_code=401, detail="Not authorized")
#     if auth.get("role") != "admin":
#         raise HTTPException(status_code=401, detail="Not authorized")

#     try:
#         staff = get_single_data(staff_id, "staff", session)

#         if not staff:
#             raise HTTPException(
#                 status_code=status.HTTP_404_NOT_FOUND,
#                 detail="Staff not found"
#             )

#         return {"message": "Staff retrieved successfully", "staff": staff}
#     except HTTPException:
#         raise
#     except Exception as e:
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"Error retrieving staff: {str(e)}"
#         )


@router.put('/update_staff/{staff_id}')
async def update_staff(
    session: SessionDep,
    staff_id: int,
    name: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    password: Optional[str] = Form(None),
    bio: Optional[str] = Form(None),
    role: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    cv: Optional[UploadFile] = File(None),
    authorization: str = Header(...)
):
    token = authorization.split(" ")[1]
    auth = isAuthorized(token)
    if not auth:
        raise HTTPException(status_code=401, detail="Not authorized")
    if auth.get("role") != "admin":
        raise HTTPException(status_code=401, detail="Not authorized")

    try:
        # Get existing staff
        existing_staff = get_single_data(staff_id, "staff", session)
        if not existing_staff:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Staff not found"
            )

        # Verify admin owns this staff
        if existing_staff.admin_id != auth.get("admin_id"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update this staff"
            )

        # Prepare update dict (only include fields that are provided)
        staff_dict = {}

        hashed_password = hash_password(password)
        
        # Generate JWT
        jwt_token = create_jwt_token(email, role)
        if name is not None:
            staff_dict["name"] = name
        if email is not None:
            staff_dict["email"] = email
        if password is not None:
            staff_dict["password"] = hashed_password
            staff_dict["prev_password"] = password
        if bio is not None:
            staff_dict["bio"] = bio
        if role is not None:
            staff_dict["role"] = role
            staff_dict["jwt_token"] = jwt_token

        # Handle file uploads if new files provided
        if image:
            image_url = await handle_file_upload(image)
            staff_dict["image_url"] = image_url

        if cv:
            cv_url = await handle_file_upload(cv)
            staff_dict["cv_url"] = cv_url

        # Update staff using CRUD function
        success, updated_staff = update_data("staff", staff_id, staff_dict, session)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to update staff"
            )

        return {"message": "Staff updated successfully", "staff": updated_staff}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating staff: {str(e)}"
        )


@router.delete('/delete_staff/{staff_id}')
def delete_staff(
    session: SessionDep,
    staff_id: int,
    authorization: str = Header(...)
):
    token = authorization.split(" ")[1]
    auth = isAuthorized(token)
    if not auth:
        raise HTTPException(status_code=401, detail="Not authorized")
    if auth.get("role") != "admin":
        raise HTTPException(status_code=401, detail="Not authorized")

    try:
        # Get existing staff
        existing_staff = get_single_data(staff_id, "staff", session)
        if not existing_staff:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Staff not found"
            )

        # Verify admin owns this staff
        if existing_staff.admin_id != auth.get("admin_id"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete this staff"
            )

        # Delete staff using CRUD function
        success = delete_data("staff", staff_id, session)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to delete staff"
            )

        return {"message": "Staff deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting staff: {str(e)}"
        )
        
@router.get('/profile')
def staff_profile(
    session: SessionDep,
    authorization: str = Header(...)
    
    ):
    
    token = authorization.split(" ")[1]
    auth = isAuthorized(token)
    if not auth:
        raise HTTPException(status_code=401, detail="Not authorized")
 
    try:
        result = get_single_data(auth["staff_id"], "staff", session)
        
        return result
    
    except Exception as e:
        print(f"Error getting profile: {e}")
        return False
        
        
        