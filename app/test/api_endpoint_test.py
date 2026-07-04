import requests
import json
from typing import Optional

intents= [
            {
                "tag": "greeting",
                "patterns": ["hello", "hi"],
                "responses": ["Welcome to Royal Hotel"]
            },
            {
                "tag": "booking",
                "patterns": ["book room", "reservation"],
                "responses": ["What type of room would you like?"]
            }
        ]
intents_json_string = json.dumps(intents)
dummy_data = {
   
    "product": {
        "admin_id": 1,
        "name": "Chicken Burger",
        "description": "Spicy grilled chicken burger",
        "price": "4500",
        "category": "Food",
        "quantity": "50",
        "image_url": "https://example.com/burger.jpg"
    },

    "room": {
        "admin_id": 1,
        "number": "101",
        "description": "Deluxe ocean view room",
        "price": "35000",
        "status": "available",
        "image_url": "https://example.com/room.jpg",
        # "pictures": {
        #     "bedroom": "https://example.com/bedroom.jpg",
        #     "bathroom": "https://example.com/bathroom.jpg"
        # }
    },

    "customer": {
        "customer_name": "John Doe",
        "address": "Lekki Phase 1, Lagos",
        "contact": "+2348012345678",
        "team_a": "Team Eagles",
        "team_b": "Team Tigers",
        "admin_id": 1
    },

    "staff": {
        "admin_id": 1,
        "name": "Grace Williams",
        "bio": "Experienced hotel manager",
        "role": "Manager",
        "cv_url": "https://example.com/cv.pdf",
        "image_url": "https://example.com/staff.jpg",
        "email": "grace@royalhotel.com",
        "password": "hashed_staff_password",
        "token": "staff_token_123"
    },

    "sales": {
        "admin_id": 1,
        "product_id": 1,
        "staff_id": 1,
        "price": "9000",
        "quantity": "2",
        "name": "Chicken Burger",
        "payment_method": "card"
    },

    "booking": {
        "admin_id": 1,
        "room_id": 1,
        "staff_id": 1,
        "price": "70000",
        "status": "confirmed",
        "duration": "2 days",
        "customer_email": "john@example.com",
        "customer_name": "John Doe",
        "customer_phone": "+2348012345678",
        "payment_method": "transfer",
        "check_in": "2026-06-01",
        "check_out": "2026-06-03"
    },

    "hotelProfile": {
        "admin_id": 1,
        "email": "contact@royalhotel.com",
        "name": "Royal Hotel Admin",
        "phone": "+2348000000000",
        "address": "Victoria Island, Lagos",
        "description": "Luxury hotel in Lagos",
        "hotel_name": "Royal Grand Hotel",
        "website_url": "https://royalhotel.com",
        "agent_phone": "+2348111111111",
        "social_links": {
            "facebook": "https://facebook.com/royalhotel",
            "instagram": "https://instagram.com/royalhotel"
        },
        "image_url": {
            "logo": "https://example.com/logo.jpg",
            "banner": "https://example.com/banner.jpg"
        }
    },

    "inbox": {
        "admin_id": 1,
        "email": "guest@example.com",
        "body": "I would like to reserve a room for two nights."
    },

    "blog": {
        "admin_id": 1,
        "title": "Top 5 Luxury Experiences in Lagos",
        "category": "travel",
        "description": "Explore the best luxury destinations in Lagos.",
        "image_url": "https://example.com/blog.jpg",
        "video_url": "https://youtube.com/example"
    },


    "dataset": {
        "title": "Hotel Support Dataset",
        "description": "Customer support training data",
        "intents": intents_json_string,
        "status": "active",
        "admin_id": 1
    },

    "call_log": {
        "title": "Customer Booking Inquiry",
        "status": "completed",
        "duration": "12 mins",
        "sentiment": "positive",
        "admin_id": 1
    }
}


def handle_create_req(
    model: str,
    token: str,
    api_endpoint: str,
):
    # Use request to handle post request
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    response = requests.post(
        f"{api_endpoint}",
        headers=headers,
        data=dummy_data[f"{model}"]
    )
    
    print(response.status_code)
    print(response.json() if response.ok else response.text)
    return response

def handle_read_req(
    token: str,
    api_endpoint: str,
    item_id: Optional[int] = None
):
    # Use request to handle get request
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    url = f"{api_endpoint}"
    if item_id:
        url = f"{api_endpoint}/{item_id}"
    
    response = requests.get(
        url,
        headers=headers
    )
    
    print(response.status_code)
    print(response.json() if response.ok else response.text)
    return response

def handle_update_req(
    model: str,
    token: str,
    api_endpoint: str,
    item_id: int,
):
    # Use request to handle put request
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    response = requests.put(
        f"{api_endpoint}/{item_id}",
        headers=headers,
        json=dummy_data[f"{model}"]
    )
    
    print(response.status_code)
    print(response.json() if response.ok else response.text)
    return response

def handle_delete_req(
    token: str,
    api_endpoint: str,
    item_id: int
):
    # Use request to handle delete request
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    response = requests.delete(
        f"{api_endpoint}/{item_id}",
        headers=headers
    )
    
    print(response.status_code)
    print(response.json() if response.ok else response.text)
    return response

model_list = [
    # "staff",
            #   "product", "room",
            #   "blog",
            #   "customer",
            #   "sales", "booking", 
            #   "hotelProfile", 
            #   "inbox", 
              "dataset", 
              "call_log"
              ]

token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkYW50ZWdhZWZlQGdtYWlsLmNvbSIsImV4cCI6MTc4MjQ3ODA0OSwicm9sZSI6ImFkbWluIn0.xLwvUyG2pzDAtSj2AxBHKdGrzkVP8zQsB4bHTctkAB4"

for i in model_list:
    api_endpoint = f"http://localhost:8000/{i}/create_{i}"
    handle_create_req(i, token, api_endpoint)