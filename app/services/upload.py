import os
import shutil
from pathlib import Path
from fastapi import UploadFile, HTTPException, status
from typing import Optional
import uuid
from datetime import datetime

# Configuration
BASE_URL = os.getenv("BASE_URL")
UPLOAD_FOLDER = './uploads'

# Allowed file types
IMG_FILETYPES = [".png", ".jpeg", ".jpg", ".gif", ".webp", ".bmp", ".svg"]
DOC_FILETYPES = [".pdf", ".doc", ".docx", ".txt", ".xls", ".xlsx"]
VID_FILETYPES = [".mp4"]
ALLOWED_FILETYPES = IMG_FILETYPES + DOC_FILETYPES + VID_FILETYPES

# Create upload directories if they don't exist
def create_upload_dirs():
    """Create necessary upload directories"""
    Path(f"{UPLOAD_FOLDER}/images").mkdir(parents=True, exist_ok=True)
    Path(f"{UPLOAD_FOLDER}/documents").mkdir(parents=True, exist_ok=True)
    Path(f"{UPLOAD_FOLDER}/others").mkdir(parents=True, exist_ok=True)

# Initialize directories on module load
create_upload_dirs()

def get_file_extension(filename: str) -> str:
    return os.path.splitext(filename)[1].lower()

def generate_unique_filename(original_filename: str) -> str:
    extension = get_file_extension(original_filename)
    unique_id = str(uuid.uuid4())[:8]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{timestamp}_{unique_id}{extension}"

async def handle_file_upload(file: UploadFile) -> dict:

    try:
        # Check if file is provided
        if not file or not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No file provided"
            )
        
        # Get file extension
        file_extension = get_file_extension(file.filename)
        
        # Validate file type
        if file_extension not in ALLOWED_FILETYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File type {file_extension} not allowed. Allowed types: {', '.join(ALLOWED_FILETYPES)}"
            )
        
        # Determine storage folder based on file type
        if file_extension in IMG_FILETYPES:
            storage_folder = f"{UPLOAD_FOLDER}/images"
            file_category = "images"
        elif file_extension in DOC_FILETYPES:
            storage_folder = f"{UPLOAD_FOLDER}/documents"
            file_category = "documents"
        else:
            storage_folder = f"{UPLOAD_FOLDER}/others"
            file_category = "others"
        
        # Generate unique filename
        unique_filename = generate_unique_filename(file.filename)
        file_path = os.path.join(storage_folder, unique_filename)
        
        # Save the file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Generate URL for the file
        file_url = f"{BASE_URL}/uploads/{file_category}/{unique_filename}"
        
        # Return file information
        return  file_url
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error uploading file: {str(e)}"
        )
    finally:
        # Close the file
        await file.close() if hasattr(file, 'close') else None
        
        
        