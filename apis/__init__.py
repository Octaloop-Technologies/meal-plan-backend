"""
API endpoints module
"""
from .user_api import router as user_router
from .admin_api import router as admin_router
from .dashboard_api import router as dashboard_router
from .onboarding_api import router as onboarding_router
from .meal_api import router as meal_router
from .plan_api import router as plan_router
from .product_api import router as product_router
from .shopping_list_api import router as shopping_list_router
from .subscription_api import router as subscription_router
from .webhook_api import router as webhook_router

__all__ = [
    "user_router",
    "admin_router",
    "dashboard_router",
    "onboarding_router",
    "meal_router",
    "plan_router",
    "product_router",
    "shopping_list_router",
    "subscription_router",
    "webhook_router",
]

