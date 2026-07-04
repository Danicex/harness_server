# CRUD room
from fastapi import APIRouter, HTTPException, status, Header, UploadFile, File, Form, Query
from typing import Optional
from datetime import datetime
from app.database import SessionDep
from app.model import Room
from app.crud import create_data, update_data, delete_data, get_admin_data, get_single_data
from app.auth.authentication import isAuthorized
from app.services.upload import handle_file_upload

router = APIRouter(prefix="/room")

@router.post('/create_room')
async def create_room(
    session: SessionDep,
    number: str = Form(...),
    price: str = Form(...),
    description: Optional[str] = Form(None),
    room_type: Optional[str] = Form(None),
    room_status: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    pictures: Optional[list[UploadFile]] = File(None),
    authorization: str = Header(...)
):
    token = authorization.split(" ")[1]
    auth = isAuthorized(token)
    if not auth:
        raise HTTPException(status_code=401, detail="Not authorized")
    if auth.get("role") != "admin":
        raise HTTPException(status_code=401, detail="Not authorized")
    
    try:
        # Handle main image upload
        image_url = None
        if image:
            image_url = await handle_file_upload(image)
        
        # Handle multiple pictures upload
        # pictures_urls = None
        # if pictures:
        #     pictures_urls = {}
        #     for idx, pic in enumerate(pictures):
        #         pic_url = handle_file_upload(pic, folder="rooms/pictures")
        #         pictures_urls[f"picture_{idx + 1}"] = pic_url

        # Prepare data for database
        room_dict = {
            "admin_id": auth.get("admin_id"),
            "number": number,
            "price": price,
            "room_type": room_type,
            "description": description,
            "status": room_status,
            "image_url": image_url,
            # "pictures": pictures_urls,
            "created_at": datetime.utcnow()
        }
        
        success, room = create_data("room", room_dict, session)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create room"
            )
        
        return {"message": "Room created successfully", "room": room}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating room: {str(e)}"
        )


@router.get("/get_rooms")
def read_rooms(
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
            
        rooms = get_admin_data(resolved_admin_id, "room", session)

        if not rooms:
            return {"message": "No rooms found", "rooms": []}
        
        return rooms
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving rooms: {str(e)}"
        )


@router.get("/{room_id}")
def get_single_room(
    session: SessionDep,
    room_id: int,
    authorization: str = Header(...)
):
    token = authorization.split(" ")[1]
    auth = isAuthorized(token)
    if not auth:
        raise HTTPException(status_code=401, detail="Not authorized")
    if auth.get("role") != "admin":
        raise HTTPException(status_code=401, detail="Not authorized")
    
    try:
        room = get_single_data(room_id, "room", session)
        
        if not room:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Room not found"
            )
        
        return {"message": "Room retrieved successfully", "room": room}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving room: {str(e)}"
        )


@router.put('/update_room/{room_id}')
async def update_room(
    session: SessionDep,
    room_id: int,
    number: Optional[str] = Form(None),
    price: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    room_status: Optional[str] = Form(None),
    room_type: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    pictures: Optional[list[UploadFile]] = File(None),
    authorization: str = Header(...)
):
    token = authorization.split(" ")[1]
    auth = isAuthorized(token)
    if not auth:
        raise HTTPException(status_code=401, detail="Not authorized")
    if auth.get("role") != "admin":
        raise HTTPException(status_code=401, detail="Not authorized")
    
    try:
        # Get existing room
        existing_room = get_single_data(room_id, "room", session)
        if not existing_room:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Room not found"
            )
        
        # Verify admin owns this room
        if existing_room.admin_id != auth.get("admin_id"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update this room"
            )
        
        # Prepare update dict (only include fields that are provided)
        room_dict = {}
        
        if number is not None:
            room_dict["number"] = number
        if price is not None:
            room_dict["price"] = price
        if description is not None:
            room_dict["description"] = description
        if room_status is not None:
            room_dict["status"] = room_status
        if room_type is not None:
            room_dict["room_type"] = room_type
        
        # Handle main image upload if new file provided
        if image:
            image_url = await handle_file_upload(image)
            room_dict["image_url"] = image_url
        
        # Handle multiple pictures upload if new files provided
        # if pictures:
        #     pictures_urls = {}
        #     for idx, pic in enumerate(pictures):
        #         pic_url = handle_file_upload(pic, folder="rooms/pictures")
        #         pictures_urls[f"picture_{idx + 1}"] = pic_url
        #     room_dict["pictures"] = pictures_urls
        
        # Update room using CRUD function
        success, updated_room = update_data("room", room_id, room_dict, session)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to update room"
            )
        
        return {"message": "Room updated successfully", "room": updated_room}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating room: {str(e)}"
        )


@router.delete('/delete_room/{room_id}')
def delete_room(
    session: SessionDep,
    room_id: int,
    authorization: str = Header(...)
):
    token = authorization.split(" ")[1]
    auth = isAuthorized(token)
    if not auth:
        raise HTTPException(status_code=401, detail="Not authorized")
    if auth.get("role") != "admin":
        raise HTTPException(status_code=401, detail="Not authorized")
    
    try:
        # Get existing room
        existing_room = get_single_data(room_id, "room", session)
        if not existing_room:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Room not found"
            )
        
        # Verify admin owns this room
        if existing_room.admin_id != auth.get("admin_id"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete this room"
            )
        
        # Delete room using CRUD function
        success = delete_data("room", room_id, session)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to delete room"
            )
        
        return {"message": "Room deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting room: {str(e)}"
        )