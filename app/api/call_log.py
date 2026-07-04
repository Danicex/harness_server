# CRUD call_log
from fastapi import APIRouter, HTTPException, status, Header, Form
from typing import Optional
from datetime import datetime
from app.database import SessionDep
from app.model import CallLog
from app.crud import create_data, update_data, delete_data, get_admin_data, get_single_data
from app.auth.authentication import isAuthorized

router = APIRouter(prefix="/call_log")

@router.post('/create_call_log')
def create_call_log(
    session: SessionDep,
    title: str = Form(...),
    duration: str = Form(...),
    sentiment: str = Form(...),
    status: str = Form(default="active"),
    authorization: str = Header(...)
):
    token = authorization.split(" ")[1]
    auth = isAuthorized(token)
    if not auth:
        raise HTTPException(status_code=401, detail="Not authorized")
    if auth.get("role") != "admin":
        raise HTTPException(status_code=401, detail="Not authorized")

    try:
        call_log_dict = {
            "admin_id": auth.get("admin_id"),
            "title": title,
            "duration": duration,
            "sentiment": sentiment,
            "status": status,
            "created_at": datetime.utcnow()
        }

        success, call_log = create_data("call_log", call_log_dict, session)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create call log"
            )

        return {"message": "Call log created successfully", "call_log": call_log}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating call log: {str(e)}"
        )


@router.get("/get_call_logs")
def read_call_logs(
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
        call_logs = get_admin_data(auth["admin_id"], "call_log", session)

        if not call_logs:
            return {"message": "No call logs found", "call_logs": []}

        return {"message": "Call logs retrieved successfully", "call_logs": call_logs}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving call logs: {str(e)}"
        )


@router.get("/{call_log_id}")
def get_single_call_log(
    session: SessionDep,
    call_log_id: int,
    authorization: str = Header(...)
):
    token = authorization.split(" ")[1]
    auth = isAuthorized(token)
    if not auth:
        raise HTTPException(status_code=401, detail="Not authorized")
    if auth.get("role") != "admin":
        raise HTTPException(status_code=401, detail="Not authorized")

    try:
        call_log = get_single_data(call_log_id, "call_log", session)

        if not call_log:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Call log not found"
            )

        return {"message": "Call log retrieved successfully", "call_log": call_log}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving call log: {str(e)}"
        )


@router.put('/update_call_log/{call_log_id}')
def update_call_log(
    session: SessionDep,
    call_log_id: int,
    title: Optional[str] = Form(None),
    duration: Optional[str] = Form(None),
    sentiment: Optional[str] = Form(None),
    status: Optional[str] = Form(None),
    authorization: str = Header(...)
):
    token = authorization.split(" ")[1]
    auth = isAuthorized(token)
    if not auth:
        raise HTTPException(status_code=401, detail="Not authorized")
    if auth.get("role") != "admin":
        raise HTTPException(status_code=401, detail="Not authorized")

    try:
        # Get existing call log
        existing_call_log = get_single_data(call_log_id, "call_log", session)
        if not existing_call_log:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Call log not found"
            )

        # Verify admin owns this call log
        if existing_call_log.admin_id != auth.get("admin_id"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update this call log"
            )

        # Prepare update dict (only include fields that are provided)
        call_log_dict = {}

        if title is not None:
            call_log_dict["title"] = title
        if duration is not None:
            call_log_dict["duration"] = duration
        if sentiment is not None:
            call_log_dict["sentiment"] = sentiment
        if status is not None:
            call_log_dict["status"] = status

        # Update call log using CRUD function
        success, updated_call_log = update_data("call_log", call_log_id, call_log_dict, session)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to update call log"
            )

        return {"message": "Call log updated successfully", "call_log": updated_call_log}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating call log: {str(e)}"
        )


@router.delete('/delete_call_log/{call_log_id}')
def delete_call_log(
    session: SessionDep,
    call_log_id: int,
    authorization: str = Header(...)
):
    token = authorization.split(" ")[1]
    auth = isAuthorized(token)
    if not auth:
        raise HTTPException(status_code=401, detail="Not authorized")
    if auth.get("role") != "admin":
        raise HTTPException(status_code=401, detail="Not authorized")

    try:
        # Get existing call log
        existing_call_log = get_single_data(call_log_id, "call_log", session)
        if not existing_call_log:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Call log not found"
            )

        # Verify admin owns this call log
        if existing_call_log.admin_id != auth.get("admin_id"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete this call log"
            )

        # Delete call log using CRUD function
        success = delete_data("call_log", call_log_id, session)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to delete call log"
            )

        return {"message": "Call log deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting call log: {str(e)}"
        )