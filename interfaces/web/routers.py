"""Every router the player web app serves, including the admin dashboard under ``/admin``."""

from __future__ import annotations

from interfaces.admin import router as admin_router
from interfaces.web.auth_routes import router as auth_router
from interfaces.web.routes import router
from interfaces.web.routes_feedback import router as feedback_router
from interfaces.web.routes_library import router as library_router
from interfaces.web.routes_poster import router as poster_router

ROUTERS = (auth_router, router, library_router, feedback_router, poster_router, admin_router)
