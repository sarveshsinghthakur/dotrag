from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.config import settings
from app.api import documents_router, chat_router, search_router, health_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("[INFO] DotRAG API starting up...")
    yield
    # Shutdown
    print("[INFO] DotRAG API shutting down...")
    from app.services.mistral import get_mistral_service
    from app.services.vector_store import get_vector_store
    await get_mistral_service().close()


app = FastAPI(
    title="DotRAG API",
    description="Intelligent PDF research assistant with RAG and AI search",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(health_router)
app.include_router(documents_router)
app.include_router(chat_router)
app.include_router(search_router)


@app.get("/")
async def root():
    return {
        "name": "DotRAG API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
    }
