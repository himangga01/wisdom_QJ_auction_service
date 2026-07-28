from fastapi import APIRouter

from app.api.routes import (
    analyses,
    apartments,
    dashboard,
    exports,
    health,
    listings,
    schedules,
)

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(analyses.router)
api_router.include_router(dashboard.router)
api_router.include_router(apartments.router)
api_router.include_router(listings.router)
api_router.include_router(schedules.router)
api_router.include_router(exports.router)
