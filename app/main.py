from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.database import create_db_and_tables
from app.api import product, staff, blog, call_log, dataset, inbox, rooms, customer, sales, booking,  hotel_profile, analytics, task_api, chatbot
from app.auth import authentication
import os
from app.tasks import update_room_statuses
from app.api import task_api


UPLOAD_DIR = "uploads"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)
    
app = FastAPI()

origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5500",
    "http://localhost:8080",
]

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"Hello": "harness"}

@app.on_event("startup")
async def startup_event():
    create_db_and_tables()
    
@app.websocket("/test-ws")
async def test_ws(websocket: WebSocket):
    await websocket.accept()
    await websocket.send_text("hello")
    await websocket.close()  
    
app.include_router(chatbot.router)
app.include_router(product.router)
app.include_router(task_api.router)
app.include_router(sales.router)
app.include_router(booking.router)
app.include_router(rooms.router)
app.include_router(staff.router)
app.include_router(inbox.router)
app.include_router(dataset.router)
app.include_router(call_log.router)
app.include_router(customer.router)
app.include_router(hotel_profile.router)
app.include_router(blog.router)
app.include_router(analytics.router)
app.include_router(authentication.router)

@app.get("/run-task")
def run_task():
    update_room_statuses.delay()
    return {"message": "Task triggered"}

@app.get("/items/{item_id}")
def read_item(item_id: int, q: str | None = None):
    return {"item_id": item_id, "q": q}