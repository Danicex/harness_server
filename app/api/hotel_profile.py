# CRUD hotel_profile
from fastapi import APIRouter, HTTPException, status, Header, UploadFile, File, Form
from typing import Optional
from datetime import datetime
from app.database import SessionDep
from app.model import HotelProfile
from app.crud import create_data, update_data, delete_data, get_admin_data, get_admin_data_single, get_single_data
from app.auth.authentication import isAuthorized
from app.services.upload import handle_file_upload

router = APIRouter(prefix="/hotel_profile")

@router.post('/create_hotel_profile')
async def create_hotel_profile(
    session: SessionDep,
    email: str = Form(...),
    name: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    hotel_name: Optional[str] = Form(None),
    website_url: Optional[str] = Form(None),
    agent_phone: Optional[str] = Form(None),
    social_links: Optional[str] = Form(None),
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
        # Handle image upload
        image_url = None
        if image:
            image_url = await handle_file_upload(image)
        
        hotel_profile_dict = {
            "admin_id": auth.get("admin_id"),
            "email": email,
            "name": name,
            "phone": phone,
            "address": address,
            "description": description,
            "hotel_name": hotel_name,
            "website_url": website_url,
            "social_links": social_links,
            "agent_phone": agent_phone,
            "image_url": image_url,
        }
        
        success, hotel_profile = create_data("hotel_profile", hotel_profile_dict, session)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create hotel profile"
            )
        
        return {"message": "Hotel profile created successfully", "hotel_profile": hotel_profile}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating hotel profile: {str(e)}"
        )


@router.get("/get_hotel_profile")
def read_hotel_profile(
    session: SessionDep,
    authorization: str = Header(...)
):
    token = authorization.split(" ")[1]
    auth = isAuthorized(token)
    if not auth:
        raise HTTPException(status_code=401, detail="Not authorized")
    
    try:
        hotel_profiles = get_admin_data_single(auth["admin_id"], "hotel_profile", session)
        
        if not hotel_profiles:
            return {"message": "No hotel profile found", "hotel_profile": None}
        
        # hotel_profile is a one-to-one relationship, return the first (and only) result
        profile = hotel_profiles[0] if isinstance(hotel_profiles, list) else hotel_profiles
        return profile
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving hotel profile: {str(e)}"
        )


@router.put('/update_hotel_profile')
async def update_hotel_profile(
    session: SessionDep,
    email: Optional[str] = Form(None),
    name: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    hotel_name: Optional[str] = Form(None),
    website_url: Optional[str] = Form(None),
    agent_phone: Optional[str] = Form(None),
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
        existing_profile = get_admin_data_single(auth["admin_id"], "hotel_profile", session)
        if not existing_profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Hotel profile not found"
            )
        
        if existing_profile.admin_id != auth.get("admin_id"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update this hotel profile"
            )
        
        hotel_profile_dict = {}
        
        if email is not None:
            hotel_profile_dict["email"] = email
        if name is not None:
            hotel_profile_dict["name"] = name
        if phone is not None:
            hotel_profile_dict["phone"] = phone
        if address is not None:
            hotel_profile_dict["address"] = address
        if description is not None:
            hotel_profile_dict["description"] = description
        if hotel_name is not None:
            hotel_profile_dict["hotel_name"] = hotel_name
        if website_url is not None:
            hotel_profile_dict["website_url"] = website_url
        if agent_phone is not None:
            hotel_profile_dict["agent_phone"] = agent_phone
        
        if image:
            profile_url = await handle_file_upload(image)
            hotel_profile_dict["image_url"] = profile_url
        
        success, updated_profile = update_data("hotel_profile", existing_profile.id, hotel_profile_dict, session)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to update hotel profile"
            )
        
        return {"message": "Hotel profile updated successfully", "hotel_profile": updated_profile}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating hotel profile: {str(e)}"
        )


# @router.delete('/delete_hotel_profile/{hotel_profile_id}')
# def delete_hotel_profile(
#     session: SessionDep,
#     hotel_profile_id: int,
#     authorization: str = Header(...)
# ):
#     token = authorization.split(" ")[1]
#     auth = isAuthorized(token)
#     if not auth:
#         raise HTTPException(status_code=401, detail="Not authorized")
#     if auth.get("role") != "admin":
#         raise HTTPException(status_code=401, detail="Not authorized")
    
#     try:
#         existing_profile = get_single_data(hotel_profile_id, "hotel_profile", session)
#         if not existing_profile:
#             raise HTTPException(
#                 status_code=status.HTTP_404_NOT_FOUND,
#                 detail="Hotel profile not found"
#             )
        
#         if existing_profile.admin_id != auth.get("admin_id"):
#             raise HTTPException(
#                 status_code=status.HTTP_403_FORBIDDEN,
#                 detail="Not authorized to delete this hotel profile"
#             )
        
#         success = delete_data("hotel_profile", hotel_profile_id, session)
        
#         if not success:
#             raise HTTPException(
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 detail="Failed to delete hotel profile"
#             )
        
#         return {"message": "Hotel profile deleted successfully"}
    
#     except HTTPException:
#         raise
#     except Exception as e:
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"Error deleting hotel profile: {str(e)}"
#         )
        
        
        