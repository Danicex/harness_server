# run mails
from fastapi import UploadFile
import resend
import os
from typing import Union, List
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
resend.api_key = RESEND_API_KEY
   
async def send_mail(
    to: Union[str, List[str]],
    subject: str,
    html: str,
    from_email: str = "Acme <noreply@encheiron.com>"
) -> bool:
    """Simple function to send email via Resend"""
    try:
        # Convert single email to list
        if isinstance(to, str):
            to = [to]
        
        # Prepare email parameters
        params = {
            "from": from_email,
            "to": to,
            "subject": subject,
            "html": html,
        }
        
        # Send email via Resend
        response = resend.Emails.send(params)
        
        # Check if email was sent successfully
        if response and 'id' in response:
            return True
        return False
        
    except Exception as e:
        print(f"Error sending email: {e}")
        return False
 