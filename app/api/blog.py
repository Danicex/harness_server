# CRUD blog
from fastapi import APIRouter, HTTPException, status, Header, UploadFile, File, Form
from typing import Optional
from datetime import datetime
from app.database import SessionDep
from app.model import Blog
from app.crud import create_data, update_data, delete_data, get_admin_data, get_single_data
from app.auth.authentication import isAuthorized
from app.services.upload import handle_file_upload

router = APIRouter(prefix="/blog")

@router.post('/create_blog')
async def create_blog(
    session: SessionDep,
    title: str = Form(...),
    category: str = Form(default="public"),
    description: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    video: Optional[UploadFile] = File(None),
    authorization: str = Header(...)
):
    token = authorization.split(" ")[1]
    auth = isAuthorized(token)
    if not auth:
        raise HTTPException(status_code=401, detail="Not authorized")
    if auth.get("role") != "admin":
        raise HTTPException(status_code=401, detail="Not authorized")
    
    try:
        # Handle file uploads
        image_url = None
        if image:
            image_url = await handle_file_upload(image)
        
        video_url = None
        if video:
            video_url = await handle_file_upload(video)
        
        # Prepare data for database
        blog_dict = {
            "admin_id": auth.get("admin_id"),
            "title": title,
            "category": category,
            "description": description,
            "image_url": image_url,
            "video_url": video_url,
            "created_at": datetime.utcnow()
        }
        
        success, blog = create_data("blog", blog_dict, session)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create blog"
            )
        
        return {"message": "Blog created successfully", "blog": blog}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating blog: {str(e)}"
        )
        
@router.get("/get_blogs")        
def read_blog(
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
        blogs = get_admin_data(auth["admin_id"], "blog", session)
        
        if not blogs:
            return {"message": "No blogs found", "blogs": []}
        
        return blogs
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving blogs: {str(e)}"
        )

@router.get("/{blog_id}")
def get_single_blog(
    session: SessionDep,
    blog_id: int,
    authorization: str = Header(...)
):
    token = authorization.split(" ")[1]
    auth = isAuthorized(token)
    if not auth:
        raise HTTPException(status_code=401, detail="Not authorized")
    if auth.get("role") != "admin":
        raise HTTPException(status_code=401, detail="Not authorized")
    
    try:
        blog = get_single_data(blog_id, "blog", session)
        
        if not blog:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Blog not found"
            )
        
        return {"message": "Blog retrieved successfully", "blog": blog}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving blog: {str(e)}"
        )

@router.put('/update_blog/{blog_id}')    
def update_blog(
    session: SessionDep,
    blog_id: int,
    title: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    video: Optional[UploadFile] = File(None),
    authorization: str = Header(...)
):
    token = authorization.split(" ")[1]
    auth = isAuthorized(token)
    if not auth:
        raise HTTPException(status_code=401, detail="Not authorized")
    if auth.get("role") != "admin":
        raise HTTPException(status_code=401, detail="Not authorized")
    
    try:
        # Get existing blog
        existing_blog = get_single_data(blog_id, "blog", session)
        if not existing_blog:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Blog not found"
            )
        
        # Verify admin owns this blog
        if existing_blog.admin_id != auth.get("admin_id"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update this blog"
            )
        
        # Prepare update dict (only include fields that are provided)
        blog_dict = {}
        
        if title is not None:
            blog_dict["title"] = title
        if category is not None:
            blog_dict["category"] = category
        if description is not None:
            blog_dict["description"] = description
        
        # Handle file uploads if new files provided
        if image:
            image_url = handle_file_upload(image, folder="blogs")
            blog_dict["image_url"] = image_url
        
        if video:
            video_url = handle_file_upload(video, folder="blogs/videos")
            blog_dict["video_url"] = video_url
        
        # Update blog using CRUD function
        success, updated_blog = update_data("blog", blog_id, blog_dict, session)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to update blog"
            )
        
        return {"message": "Blog updated successfully", "blog": updated_blog}    
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating blog: {str(e)}"
        )
        
@router.delete('/delete_blog/{blog_id}')        
def delete_blog(
    session: SessionDep,
    blog_id: int,
    authorization: str = Header(...)
):
    token = authorization.split(" ")[1]
    auth = isAuthorized(token)
    if not auth:
        raise HTTPException(status_code=401, detail="Not authorized")
    if auth.get("role") != "admin":
        raise HTTPException(status_code=401, detail="Not authorized")
    
    try:
        # Get existing blog
        existing_blog = get_single_data(blog_id, "blog", session)
        if not existing_blog:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Blog not found"
            )
        
        # Verify admin owns this blog
        if existing_blog.admin_id != auth.get("admin_id"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete this blog"
            )
        
        # Delete blog using CRUD function
        success = delete_data("blog", blog_id, session)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to delete blog"
            )
        
        return {"message": "Blog deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting blog: {str(e)}"
        )