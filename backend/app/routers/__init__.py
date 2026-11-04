from .auth import router as auth_router
from .recommendations import router as recommendations_router
from .plan import router as plan_router

__all__ = ["auth_router", "recommendations_router", "plan_router"]
