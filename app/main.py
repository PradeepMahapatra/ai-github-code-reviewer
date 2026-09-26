from fastapi import FastAPI

from app.routers.health import router as health_router

app = FastAPI(title="AI GitHub Code Reviewer")
app.include_router(health_router)
