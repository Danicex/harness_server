from fastapi import APIRouter, Form, UploadFile, File, HTTPException
from celery.result import AsyncResult
from app.celery_app import celery_app
from app.tasks import send_mail, send_mail_with_attachment, send_sms, update_room_statuses
from typing import List, Optional
import base64
import logging

router = APIRouter(prefix="/task")
logger = logging.getLogger(__name__)

@router.get("/get_task_status/{task_id}")
async def task_status(task_id: str):
    task = AsyncResult(task_id, app=celery_app)

    redis_info = {}
    try:
        from app.tasks import redis_client
        redis_info = redis_client.hgetall(task_id)  # sync call, no await
    except Exception as e:
        logger.warning(f"Could not fetch Redis info: {e}")

    return {
        "task_id": task.id,
        "state": task.state,
        "result": str(task.result) if task.result else None,
        "info": redis_info or {}
    }

@router.post("/send_sms")
def task_send_sms(
    to: List[str] = Form(..., description="List of phone numbers"),
    body: str = Form(..., description="SMS message body"),
    sender: Optional[str] = Form(None)
    
):
    """
    Send SMS messages to one or more recipients
    """
    try:
        # Clean phone numbers (remove whitespace)
        cleaned_numbers = [num.strip() for num in to if num.strip()]
        
        if not cleaned_numbers:
            raise HTTPException(status_code=400, detail="No valid phone numbers provided")
        
        # Trigger the Celery task
        task = send_sms.delay(
            to=cleaned_numbers,
            body=body,
            sender=sender
        )
        
        return {
            "task_id": task.id,
            "status": "queued",
            "message": f"SMS task queued for {len(cleaned_numbers)} recipients",
            "recipients": cleaned_numbers
        }
    
    except Exception as e:
        logger.error(f"Error sending SMS: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/send_mail")
def task_send_mail(
    to: str= Form(..., description="Email recipient(s) - comma separated for multiple"),
    subject: str = Form(..., description="Email subject"),
    html: str = Form(..., description="HTML content of the email"),
    from_email: Optional[str] = Form(None, description="Sender email (default: Acme <noreply@encheiron.com>)")
):
    
    try:
        # Parse comma-separated emails into list
        recipients = [email.strip() for email in to.split(',') if email.strip()]
        
        if not recipients:
            raise HTTPException(status_code=400, detail="No valid email addresses provided")
        
        # Use default sender if not provided
        if not from_email:
            from_email = "Acme <noreply@encheiron.com>"
        
        # Trigger the Celery task
        task = send_mail.delay(
            to=recipients if len(recipients) > 1 else recipients[0],
            subject=subject,
            html=html,
            from_email=from_email
        )
        
        return {
            "task_id": task.id,
            "status": "queued",
            "message": f"Email task queued for {len(recipients)} recipients",
            "recipients": recipients
        }
    
    except Exception as e:
        logger.error(f"Error sending email: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/send_attachment_mail")
async def send_attachment_mail(
    to: str = Form(..., description="Email recipient(s) - comma separated for multiple"),
    subject: str = Form(..., description="Email subject"),
    html: str = Form(..., description="HTML content of the email"),
    file: UploadFile = File(..., description="File to attach (PDF recommended)"),
    filename: Optional[str] = Form(None, description="Custom filename (default: original filename)"),
    from_email: Optional[str] = Form(None, description="Sender email (default: Acme <noreply@encheiron.com>)")
):
    """
    Send an email with a file attachment
    """
    try:
        # Parse comma-separated emails into list
        recipients = [email.strip() for email in to.split(',') if email.strip()]
        
        if not recipients:
            raise HTTPException(status_code=400, detail="No valid email addresses provided")
        
        # Read file content
        file_content = await file.read()
        
        if not file_content:
            raise HTTPException(status_code=400, detail="Empty file provided")
        
        # Encode file content to base64 for Celery task
        encoded_content = base64.b64encode(file_content).decode('utf-8')
        
        # Use custom filename or original
        attachment_filename = filename or file.filename
        
        # Determine content type
        content_type = file.content_type or "application/pdf"
        
        # Use default sender if not provided
        if not from_email:
            from_email = "Acme <noreply@encheiron.com>"
        
        # Trigger the Celery task
        task = send_mail_with_attachment.delay(
            filename=attachment_filename,
            content_type=content_type,
            file_content=encoded_content,
            to=recipients if len(recipients) > 1 else recipients[0],
            subject=subject,
            html=html,
            from_email=from_email
        )
        
        return {
            "task_id": task.id,
            "status": "queued",
            "message": f"Email with attachment task queued for {len(recipients)} recipients",
            "recipients": recipients,
            "attachment": attachment_filename,
            "file_size": len(file_content)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending email with attachment: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/update_room_statuses")
def trigger_room_status_update():
    """
    Trigger the room status update task
    """
    try:
        task = update_room_statuses.delay()
        return {
            "task_id": task.id,
            "status": "queued",
            "message": "Room status update task queued"
        }
    
    except Exception as e:
        logger.error(f"Error triggering room status update: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/cancel_task/{task_id}")
async def cancel_task(task_id: str):
    """
    Cancel a running Celery task
    """
    try:
        task = AsyncResult(task_id, app=celery_app)
        
        if task.state in ['PENDING', 'STARTED']:
            task.revoke(terminate=True)
            return {
                "task_id": task_id,
                "status": "cancelled",
                "message": "Task cancellation requested"
            }
        else:
            return {
                "task_id": task_id,
                "status": task.state,
                "message": f"Task cannot be cancelled (current state: {task.state})"
            }
    
    except Exception as e:
        logger.error(f"Error cancelling task: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/bulk_send_sms")
def bulk_send_sms(
    recipients: List[str] = Form(..., description="List of phone numbers"),
    message: str = Form(..., description="SMS message body"),
    sender: str = Form(..., description="Sender ID or phone number")
):
    """
    Send bulk SMS to multiple recipients
    """
    return task_send_sms(to=recipients, body=message, sender=sender)

@router.get("/task_result/{task_id}")
async def get_task_result(task_id: str):
    """
    Get the result of a completed task
    """
    task = AsyncResult(task_id, app=celery_app)
    
    if task.state == 'PENDING':
        return {"task_id": task_id, "state": "pending", "message": "Task is still pending"}
    elif task.state == 'STARTED':
        return {"task_id": task_id, "state": "started", "message": "Task is currently running"}
    elif task.state == 'SUCCESS':
        return {
            "task_id": task_id,
            "state": "success",
            "result": task.result,
            "message": "Task completed successfully"
        }
    elif task.state == 'FAILURE':
        return {
            "task_id": task_id,
            "state": "failed",
            "error": str(task.result),
            "message": "Task failed"
        }
    else:
        return {
            "task_id": task_id,
            "state": task.state,
            "message": f"Task state: {task.state}"
        }