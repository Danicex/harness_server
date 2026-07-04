# CRUD inbox
from fastapi import APIRouter, HTTPException, status, Header, Form
from typing import Optional
from datetime import datetime
from app.database import SessionDep
from app.model import Inbox
from app.crud import create_data, update_data, delete_data, get_admin_data, get_single_data
from app.auth.authentication import isAuthorized

router = APIRouter(prefix="/inbox")

@router.post('/create_inbox/{admin_id}')
def create_inbox(
    session: SessionDep,
    admin_id: int,
    email: Optional[str] = Form(None),
    body: Optional[str] = Form(None),
):
    
    try:
        inbox_dict = {
            "admin_id": admin_id,
            "email": email,
            "body": body,
            "created_at": datetime.utcnow()
        }
        
        success, inbox = create_data("inbox", inbox_dict, session)
        customer_dict = {
            "admin_id": admin_id,
            "email": email
        }
        create_customer = create_data ("customer", customer_dict, session)
        if not success and create_customer:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create inbox"
            )
        
        return {"message": "Inbox created successfully", "inbox": inbox}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating inbox: {str(e)}"
        )


@router.get("/get_inboxes")
def read_inboxes(
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
        inboxes = get_admin_data(auth["admin_id"], "inbox", session)
        
        if not inboxes:
            return {"message": "No inboxes found", "inboxes": []}
        
        return inboxes
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving inboxes: {str(e)}"
        )



@router.delete('/delete_inbox/{inbox_id}')
def delete_inbox(
    session: SessionDep,
    inbox_id: int,
    authorization: str = Header(...)
):
    token = authorization.split(" ")[1]
    auth = isAuthorized(token)
    if not auth:
        raise HTTPException(status_code=401, detail="Not authorized")
    if auth.get("role") != "admin":
        raise HTTPException(status_code=401, detail="Not authorized")
    
    try:
        # Get existing inbox
        existing_inbox = get_single_data(inbox_id, "inbox", session)
        if not existing_inbox:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Inbox not found"
            )
        
        # Verify admin owns this inbox
        if existing_inbox.admin_id != auth.get("admin_id"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete this inbox"
            )
        
        # Delete inbox using CRUD function
        success = delete_data("inbox", inbox_id, session)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to delete inbox"
            )
        
        return {"message": "Inbox deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting inbox: {str(e)}"
        )