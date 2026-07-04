#!/bin/bash

echo "Activating virtual environment..."
source myenv/bin/activate

echo "Starting Redis..."
redis-server &

echo "Starting Celery Worker..."
celery -A app.celery_app:celery_app worker --loglevel=info &

echo "Starting Celery Beat..."
celery -A app.celery_app:celery_app beat --loglevel=info &

echo "Starting FastAPI..."
# fastapi dev ./app/main.py
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload