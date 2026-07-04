import requests

def send_bulk_sms(message, phone_numbers, sender_id, user_name):
    url = "https://api.africastalking.com/version1/messaging/bulk"

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "apiKey": "YOUR_API_KEY",  # Replace with your API key
    }

    payload = {
        "username": user_name,  # Replace with your Africa's Talking username
        "message": message,
        "senderId": sender_id,
        "phoneNumbers": phone_numbers,
    }

    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()

    return response.json()