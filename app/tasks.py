from app.celery_app import celery_app
from app.model import Room,  Booking, HotelProfile
from datetime import date
from sqlmodel import Session, select
from app.database import engine
from app.crud import update_data
import resend
import os
from typing import Union, List
import redis
import base64
import os
from twilio.rest import Client


account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
default_number = os.environ.get("TWILIO_PHONE_NUMBER")

REDIS_PORT = os.getenv("REDIS_PORT")
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
resend.api_key = RESEND_API_KEY

redis_client = redis.Redis(
    host='localhost',
    port=REDIS_PORT,
    db=int(0),
    decode_responses=True
)

def get_hotel(admin_id):
    with Session(engine) as session:
        return session.exec(
            select(HotelProfile).where(HotelProfile.admin_id == admin_id)
            ).first()

def generate_booking_email_html(hotel, booking, event_type):
    """
    Generate HTML email template for booking notifications
    
    event_type: 'check_in' or 'check_out'
    """
    if event_type == 'check_in':
        title = "🏨 Check-In Confirmation"
        message = "Your room is now ready and waiting for you!"
        status_color = "#4CAF50"  # Green
        action_text = "View Your Booking"
    else:  # check_out
        title = "🔄 Check-Out Confirmation"
        message = "Thank you for staying with us! Your room is now available for other guests."
        status_color = "#FF9800"  # Orange
        action_text = "Book Again"
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{title}</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f4f4f4;
            }}
            .container {{
                background-color: #ffffff;
                border-radius: 10px;
                padding: 30px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            .header {{
                text-align: center;
                border-bottom: 3px solid {status_color};
                padding-bottom: 20px;
                margin-bottom: 25px;
            }}
            .hotel-logo {{
                max-width: 150px;
                height: auto;
                border-radius: 8px;
                margin-bottom: 10px;
            }}
            .hotel-name {{
                font-size: 28px;
                color: #2c3e50;
                margin: 10px 0 5px 0;
            }}
            .hotel-address {{
                color: #7f8c8d;
                font-size: 14px;
            }}
            .status-badge {{
                display: inline-block;
                background-color: {status_color};
                color: white;
                padding: 8px 20px;
                border-radius: 20px;
                font-weight: bold;
                font-size: 16px;
                margin: 15px 0;
            }}
            .booking-details {{
                background-color: #f8f9fa;
                border-radius: 8px;
                padding: 20px;
                margin: 20px 0;
            }}
            .booking-details table {{
                width: 100%;
                border-collapse: collapse;
            }}
            .booking-details td {{
                padding: 10px 5px;
                border-bottom: 1px solid #e9ecef;
            }}
            .booking-details td:first-child {{
                font-weight: bold;
                color: #495057;
                width: 40%;
            }}
            .booking-details td:last-child {{
                color: #212529;
            }}
            .message {{
                font-size: 16px;
                color: #495057;
                text-align: center;
                margin: 20px 0;
                padding: 15px;
                background-color: #f8f9fa;
                border-radius: 8px;
                border-left: 4px solid {status_color};
            }}
            .button {{
                display: inline-block;
                background-color: {status_color};
                color: white !important;
                text-decoration: none;
                padding: 12px 30px;
                border-radius: 25px;
                font-weight: bold;
                margin: 20px 0;
                transition: background-color 0.3s;
                text-align: center;
            }}
            .button:hover {{
                opacity: 0.9;
            }}
            .footer {{
                margin-top: 30px;
                padding-top: 20px;
                border-top: 1px solid #e9ecef;
                text-align: center;
                font-size: 12px;
                color: #6c757d;
            }}
            .footer a {{
                color: {status_color};
                text-decoration: none;
            }}
            .social-links {{
                margin: 10px 0;
            }}
            .social-links a {{
                margin: 0 10px;
                color: #6c757d;
                text-decoration: none;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                {f'<img src="{hotel.image_url}" alt="{hotel.hotel_name}" class="hotel-logo">' if hotel.image_url else ''}
                <h1 class="hotel-name">{hotel.hotel_name}</h1>
                <p class="hotel-address">📍 {hotel.address}</p>
                <div class="status-badge">{title}</div>
            </div>
            
            <div class="message">
                {message}
            </div>
            
            <div class="booking-details">
                <h3 style="text-align: center; color: #2c3e50; margin-bottom: 15px;">Booking Details</h3>
                <table>
                    <tr>
                        <td>Booking ID</td>
                        <td>#{booking.id}</td>
                    </tr>
                    <tr>
                        <td>Room Number</td>
                        <td>{booking.room_id}</td>
                    </tr>
                    <tr>
                        <td>Check-in Date</td>
                        <td>{booking.check_in}</td>
                    </tr>
                    <tr>
                        <td>Check-out Date</td>
                        <td>{booking.check_out}</td>
                    </tr>
                    <tr>
                        <td>Status</td>
                        <td><span style="color: {status_color}; font-weight: bold;">{'Checked In' if event_type == 'check_in' else 'Checked Out'}</span></td>
                    </tr>
                </table>
            </div>
            
            <div style="text-align: center;">
                <a href="https://your-hotel-booking.com/booking/{booking.id}" class="button">{action_text}</a>
            </div>
            
            <div class="footer">
                <p style="font-size: 14px; color: #495057;">
                    Thank you for choosing <strong>{hotel.hotel_name}</strong>!
                </p>
                <p style="font-size: 12px; color: #6c757d;">
                    Need help? Contact us at <a href="mailto:{hotel.email or 'support@hotel.com'}">{hotel.email or 'support@hotel.com'}</a>
                </p>
                <div class="social-links">
                    <a href="#">Facebook</a>
                    <a href="#">Instagram</a>
                    <a href="#">Twitter</a>
                </div>
                <p style="margin-top: 15px; font-size: 11px; color: #adb5bd;">
                    This is an automated message. Please do not reply to this email.
                </p>
            </div>
        </div>
    </body>
    </html>
    """
    return html

@celery_app.task
def update_room_statuses():
   
    with Session(engine) as session:
        today = date.today().isoformat()
        booking_list =  session.exec(
                select(Booking).where(
                    (Booking.check_in == today) | (Booking.check_out == today)
                )
            ).all()
        updated = 0

        for booking in booking_list:
            hotel = get_hotel(booking.admin_id)
            if not hotel:
                print(f"Hotel not found for admin_id: {booking.admin_id}")
                continue

            if booking.check_in == today:
                html = generate_booking_email_html(hotel, booking, "check_in")
                send_mail.delay(
                    booking.customer_email,
                    f"Check-In Confirmation - {hotel.hotel_name}",
                    html
                )
                update_data("room", booking.room_id, {"status": "occupied"}, session)
                updated += 1                        

            if booking.check_out == today:
                html = generate_booking_email_html(hotel, booking, "check_out")
                send_mail.delay(
                    booking.customer_email,
                    f"Check-Out Confirmation - {hotel.hotel_name}",
                    html
                )
                update_data("room", booking.room_id, {"status": "available"}, session)
                updated += 1
        session.commit()
        return f"Successfully updated {updated} bookings and sent notifications"
  
@celery_app.task(bind=True)
def send_mail(
    self,
    to: Union[str, List[str]],
    subject: str,
    html: str,
    from_email: str = "Acme <noreply@encheiron.com>"
) -> bool:
    """Simple function to send email via Resend"""
    task_id = self.request.id
    redis_client.hset(task_id, mapping={
        "status": "processing",
        "progress": 0
    })
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
            redis_client.hset(task_id, mapping={
                "status": "completed",
                "progress": 100
            })        
            return True
        return task_id
    except Exception as e:
        redis_client.hset(task_id, mapping={
            "status": "failed",
            "error": str(e)
        })
        raise
    
@celery_app.task(bind=True)
def send_mail_with_attachment(
    self,
    filename,
    content_type,
    file_content,
    to: Union[str, List[str]],
    subject: str,
    html: str,
    from_email: str = "Acme <noreply@encheiron.com>"
) -> bool:
   
    """Send email with PDF attachment via Resend"""
    task_id = self.request.id
    redis_client.hset(task_id, mapping={
        "status": "processing",
        "progress": 0
    })
    try:
        # Convert single email to list
        if isinstance(to, str):
            to = [to]
       
        decoded = base64.b64decode(file_content)
        
        # Prepare email parameters with attachment
        params = {
            "from": from_email,
            "to": to,
            "subject": subject,
            "html": html,
            "attachments": [
            {
                "filename": filename,
                "content": base64.b64encode(decoded).decode(),
                "content_type": content_type,
            }
        ],

        }
        
        # Send email via Resend
        response = resend.Emails.send(params)
        
        # Check if email was sent successfully
        if response and 'id' in response:
            redis_client.hset(task_id, mapping={
                "status": "completed",
                "progress": 0
            })
            return True
        else: return False

        
    except Exception as e:
        task_id = self.request.id
        redis_client.hset(task_id, mapping={
            "status": "failed",
            "progress": 100
        })
        raise

# The task
@celery_app.task(bind=True)
def send_sms(self, to, body, sender):
    task_id = self.request.id
    
    if isinstance(to, str):
        to = [to]
    
    total = len(to)
    
    if not sender:
        sender = default_number
    redis_client.hset(task_id, mapping={
        "status": "processing",
        "progress": 0,
        "total": total,
        "sent": 0,
        "failed": 0
    })
    
    client = Client(account_sid, auth_token)
    sent = 0
    failed = 0
    
    for index, number in enumerate(to):
        try:
            message = client.messages.create(
                body=body,
                from_=sender,
                to=number.strip()
            )
            if message.sid:
                sent += 1
        except Exception as e:
            failed += 1
        
        progress = int((index + 1) / total * 100)
        redis_client.hset(task_id, mapping={
            "status": "processing",
            "progress": progress,
            "sent": sent,
            "failed": failed,
            "total": total
        })
    
    status = "success" if failed == 0 else "partial" if sent > 0 else "failed"
    redis_client.hset(task_id, mapping={
        "status": status,
        "progress": 100,
        "sent": sent,
        "failed": failed,
        "total": total
    })
    


    
