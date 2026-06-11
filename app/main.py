import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.services.scheduler import start_scheduler, stop_scheduler
from app.routers import webhooks, admin, health, auth
from app.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    start_scheduler()
    yield
    # Shutdown
    stop_scheduler()

app = FastAPI(
    title="AI Email Assistant",
    description="...",
    version="1.0.0",
    lifespan=lifespan
)
app.include_router(auth.router)
app.include_router(webhooks.router)


@app.get("/test")
async def test_router():
    return {"message": "Server is working and routes are registered!"}


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(webhooks.router)
app.include_router(admin.router)
app.include_router(auth.router)