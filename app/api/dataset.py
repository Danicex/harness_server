# CRUD dataset
from fastapi import APIRouter, HTTPException, status, Header, Form
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.database import SessionDep
from app.model import Dataset
from app.crud import create_data, update_data, delete_data, get_admin_data, get_admin_data_single, get_single_data
from app.auth.authentication import isAuthorized
import json
router = APIRouter(prefix="/dataset")

@router.post('/create_dataset')
async def create_dataset(
    session: SessionDep,
    title: str = Form(...),  
    description: Optional[str] = Form(None),  
    intent: Optional[str] = Form(None),
    authorization: str = Header(...)
):
    token = authorization.split(" ")[1]
    auth = isAuthorized(token)
    if not auth:
        raise HTTPException(status_code=401, detail="Not authorized")
    if auth.get("role") != "admin":
        raise HTTPException(status_code=401, detail="Not authorized")
    
    try:
        intent_data = json.loads(intent) if intent else []
        dataset_dict = {
            "admin_id": auth.get("admin_id"),
            "title": title,
            "description": description,
            "intent": intent_data
        }
        
        success, dataset = create_data("dataset", dataset_dict, session)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create dataset"
            )
        
        return {"message": "Dataset created successfully", "dataset": dataset}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating dataset: {str(e)}"
        )


@router.get("/get_dataset")
def read_dataset(
    session: SessionDep,
    authorization: str = Header(...)
):
    token = authorization.split(" ")[1]
    auth = isAuthorized(token)
    if not auth:
        raise HTTPException(status_code=401, detail="Not authorized")
    
    try:
        dataset = get_admin_data_single(auth["admin_id"], "dataset", session)
        
        if not dataset:
            return {"message": "No dataset found", "dataset": None}
        
        # Dataset is a one-to-one relationship, return the first (and only) result
        result = dataset
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving dataset: {str(e)}"
        )


@router.put('/update_dataset')
async def update_dataset(
    session: SessionDep,
    title: Optional[str] = None,
    description: Optional[str] = None,
    intent: Optional[List[Dict[str, Any]]] = None,
    authorization: str = Header(...)
):
    token = authorization.split(" ")[1]
    auth = isAuthorized(token)
    if not auth:
        raise HTTPException(status_code=401, detail="Not authorized")
    if auth.get("role") != "admin":
        raise HTTPException(status_code=401, detail="Not authorized")
    
    try:
        existing_dataset = get_admin_data_single(auth["admin_id"], "dataset", session)
        if not existing_dataset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Dataset not found"
            )
        
        # Handle both list and single object responses
        dataset_obj = existing_dataset[0] if isinstance(existing_dataset, list) else existing_dataset
        
        if dataset_obj.admin_id != auth.get("admin_id"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update this dataset"
            )
        
        dataset_dict = {}
        
        if title is not None:
            dataset_dict["title"] = title
        if description is not None:
            dataset_dict["description"] = description
        if intent is not None:
            dataset_dict["intent"] = intent
        
        success, updated_dataset = update_data("dataset", dataset_obj.id, dataset_dict, session)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to update dataset"
            )
        
        return {"message": "Dataset updated successfully", "dataset": updated_dataset}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating dataset: {str(e)}"
        )


@router.delete('/delete_dataset')
def delete_dataset(
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
        existing_dataset = get_admin_data_single(auth["admin_id"], "dataset", session)
        if not existing_dataset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Dataset not found"
            )
        
        dataset_obj = existing_dataset[0] if isinstance(existing_dataset, list) else existing_dataset
        
        if dataset_obj.admin_id != auth.get("admin_id"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete this dataset"
            )
        
        success = delete_data("dataset", dataset_obj.id, session)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to delete dataset"
            )
        
        return {"message": "Dataset deleted successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting dataset: {str(e)}"
        )