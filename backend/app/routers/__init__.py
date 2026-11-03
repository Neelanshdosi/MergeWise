from .auth import router as auth_router
from .recommendations import router as recommendations_router

__all__ = ["auth_router", "recommendations_router"]
