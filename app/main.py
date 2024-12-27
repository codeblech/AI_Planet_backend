from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import redis.asyncio as redis
from contextlib import asynccontextmanager
from fastapi_limiter import FastAPILimiter

from .config import CORS_ORIGINS
from .database import Base, engine
from .api.routes import upload, websocket
import os

@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.getenv("REDIS_URL"):
        redis_instance = redis.from_url(os.getenv("REDIS_URL"), encoding="utf-8", decode_responses=True)
    else:
        redis_instance = redis.from_url("redis://localhost:6379", encoding="utf-8", decode_responses=True)
    await FastAPILimiter.init(redis_instance)
    yield
    await redis_instance.close()

def create_app():
    app = FastAPI(lifespan=lifespan)
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Create database tables
    Base.metadata.create_all(bind=engine)
    
    # Include routers
    app.include_router(upload.router)
    app.include_router(websocket.router)
    
    return app

app = create_app() 