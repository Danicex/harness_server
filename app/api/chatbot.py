# app/chat.py
import json
from datetime import datetime
from openai import AsyncOpenAI
from redis.asyncio import Redis
from sqlmodel import select
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
import os
from app.database import SessionDep, get_session
from app.model import Room, Product, HotelProfile, Dataset
from app.utils.toon import toon_encode
from contextlib import asynccontextmanager

api_key = os.getenv("OPENAI_API_KEY")
client = AsyncOpenAI(api_key=api_key)

redis = Redis(host="localhost", port=6379, decode_responses=True)

router = APIRouter(prefix="/chat")

CACHE_TTL = 3600  # 1 hour


def _dump(rows) -> list[dict]:
    return [r.model_dump(mode="json") for r in rows]


def _fetch_dataset_sync(session, admin_id: int) -> str:
    """Blocking DB reads — run this in a threadpool from async code."""
    rooms = session.exec(select(Room).where(Room.admin_id == admin_id)).all()
    products = session.exec(select(Product).where(Product.admin_id == admin_id)).all()
    intents = session.exec(select(Dataset).where(Dataset.admin_id == admin_id)).all()
    hotel_profile = session.exec(
        select(HotelProfile).where(HotelProfile.admin_id == admin_id)
    ).first()

    payload = {
        "hotel_profile": hotel_profile.model_dump(mode="json") if hotel_profile else {},
        "rooms": _dump(rooms),
        "products": _dump(products),
        "dataset": _dump(intents),
    }
    return toon_encode(payload)


async def get_dataset(admin_id: int) -> str:
    """Get dataset with proper session management."""
    cache_key = f"chat_dataset:{admin_id}"

    cached = await redis.get(cache_key)
    if cached is not None:
        return cached

    # Create a synchronous session for the threadpool
    from app.database import engine
    from sqlmodel import Session
    
    def _fetch_with_session():
        with Session(engine) as session:
            return _fetch_dataset_sync(session, admin_id)
    
    toon_result = await run_in_threadpool(_fetch_with_session)
    await redis.set(cache_key, toon_result, ex=CACHE_TTL)
    return toon_result


async def invalidate_dataset_cache(admin_id: int):
    await redis.delete(f"chat_dataset:{admin_id}")


@router.websocket("/ws/{admin_id}")
async def chat_ws(websocket: WebSocket, admin_id: int):
    await websocket.accept()
    
    try:
        # Get dataset (now without session dependency)
        dataset = await get_dataset(admin_id)
        nav_link = 'http://127.0.0.1:5500/hotel_template/'
        history = [
                {
            "role": "system",
            "content": (
                f"Answer only from this data. "
                f"For rooms or inventory, include image_url, name, price, and this link: {nav_link}.\n"
                f"{dataset}"
            ),
            }
        ]

        while True:
            user_prompt = await websocket.receive_text()
            history.append({"role": "user", "content": user_prompt})

            stream = await client.chat.completions.create(
                model="gpt-4o",
                messages=history,
                stream=True,
            )

            full_reply = ""
            async for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    full_reply += delta
                    await websocket.send_json({"type": "chunk", "content": delta})

            history.append({"role": "assistant", "content": full_reply})
            await websocket.send_json({"type": "done"})

    except WebSocketDisconnect:
        print(f"Client {admin_id} disconnected")
    except Exception as e:
        print(f"Error in WebSocket: {e}")
        await websocket.close(code=1011)  # Internal error