import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router
from app.api.discovery import router as discovery_router
from app.api.ats import router as ats_router
from app.core.database import init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI Job Application Copilot API",
    description="Backend API powering RAG resume optimization and hiring automation workflows",
    version="1.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Resume-Pages", "X-Resume-Omitted"],
)

@app.on_event("startup")
def on_startup():
    logger.info("Initializing database...")
    init_db()
    logger.info("Database initialized successfully.")

app.include_router(router)
app.include_router(discovery_router)
app.include_router(ats_router)

@app.get("/")
def read_root():
    return {"message": "AI Job Application Copilot API is live"}
