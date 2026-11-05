import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv

load_dotenv()

from app.database.repository import DatabaseRepository
from app.services.search import SearchService
from app.web.routes import router as web_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("auto_agent")

repo = DatabaseRepository()
search_service = SearchService(repo)
scheduler = BackgroundScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    hours = int(os.getenv("SEARCH_INTERVAL_HOURS", 24))
    scheduler.add_job(search_service.run_search_pipeline, "interval", hours=hours)
    scheduler.start()
    
    if os.getenv("RUN_ON_START", "true").lower() in ("true", "1"):
        search_service.run_search_pipeline()
    yield
    scheduler.shutdown()

app = FastAPI(title="Auto-Agent", lifespan=lifespan)
os.makedirs("app/web/static", exist_ok=True)
app.mount("/static", StaticFiles(directory="app/web/static"), name="static")
app.include_router(web_router)