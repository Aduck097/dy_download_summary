from fastapi import APIRouter

from web_console_backend.app.api.routes import config, health, projects, runs


api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(config.router, prefix="/config", tags=["config"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(runs.router, prefix="/runs", tags=["runs"])
