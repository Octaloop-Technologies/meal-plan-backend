"""
API Routes - Consolidated router
All route modules combined into single router
"""
from fastapi import APIRouter
from auth import router as auth_router
from admin import router as admin_router
from dashboard import router as dashboard_router
from meals import router as meals_router
from onboarding import router as onboarding_router
from plans import router as plans_router
from products import router as products_router
from shopping_list import router as shopping_list_router
from subscriptions import router as subscriptions_router
from webhooks import router as webhooks_router

api_router = APIRouter()

api_router.include_router(auth_router, tags=["authentication"])
api_router.include_router(onboarding_router, tags=["onboarding"])
api_router.include_router(meals_router, tags=["meals"])
api_router.include_router(shopping_list_router, tags=["shopping-list"])
api_router.include_router(dashboard_router, tags=["dashboard"])
api_router.include_router(subscriptions_router, tags=["subscriptions"])
api_router.include_router(products_router, tags=["products"])
api_router.include_router(admin_router, tags=["admin"])
api_router.include_router(webhooks_router, tags=["webhooks"])
