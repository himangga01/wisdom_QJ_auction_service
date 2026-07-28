from fastapi import APIRouter

from app.api.routes import (
    admin_users,
    analyses,
    apartments,
    auth,
    dashboard,
    exports,
    health,
    listings,
    notification_preferences,
    notifications,
    schedules,
)

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(admin_users.router)
api_router.include_router(analyses.router)
api_router.include_router(dashboard.router)
api_router.include_router(apartments.router)
api_router.include_router(listings.router)
api_router.include_router(notifications.router)
api_router.include_router(notification_preferences.router)
api_router.include_router(schedules.router)
api_router.include_router(exports.router)
