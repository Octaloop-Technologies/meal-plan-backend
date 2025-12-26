"""
Meal Plans API endpoints
"""
from fastapi import APIRouter, HTTPException, Request, Query
from datetime import date, timedelta
from typing import Optional
# from database import get_db, User, UserPreference, DailyMealPlan  # TODO: Update to use Beanie
from schemas import DailyMealPlanResponse, WeeklyPlanResponse
from auth import verify_shopify_request
from meal_engine import generate_daily_plan, generate_weekly_plan
from user_service import get_user_preferences
import json

router = APIRouter()


def meal_to_response(meal) -> Optional[dict]:
    """Convert meal model to response dict"""
    if not meal:
        return None
    
    return {
        "id": meal.id,
        "title": meal.title,
        "description": meal.description,
        "meal_type": meal.meal_type.value,
        "calories": meal.calories,
        "protein_g": float(meal.protein_g),
        "carbs_g": float(meal.carbs_g),
        "fat_g": float(meal.fat_g),
        "fiber_g": float(meal.fiber_g),
        "ingredients": json.loads(meal.ingredients or "[]"),
        "instructions": meal.instructions,
        "prep_time_minutes": meal.prep_time_minutes,
        "cook_time_minutes": meal.cook_time_minutes,
        "tags": json.loads(meal.tags or "[]"),
        "image_url": meal.image_url,
        "is_active": meal.is_active,
        "created_at": meal.created_at,
        "updated_at": meal.updated_at
    }


@router.get("/plans/today", response_model=DailyMealPlanResponse)
async def get_today_plan(
    request: Request
):
    """
    Get today's meal plan for the authenticated user
    """
    shopify_data = await verify_shopify_request(request)
    shopify_customer_id = shopify_data["shopify_customer_id"]
    
    # Get user
    user = db.query(User).filter(User.shopify_customer_id == shopify_customer_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check onboarding
    preferences = get_user_preferences(db, user.id)
    if not preferences or not preferences.onboarding_completed:
        raise HTTPException(status_code=400, detail="Onboarding not completed")
    
    # Generate or get today's plan
    today = date.today()
    plan = generate_daily_plan(db, user.id, today, preferences)
    
    # Load meals
    breakfast = db.query(Meal).filter(Meal.id == plan.breakfast_meal_id).first() if plan.breakfast_meal_id else None
    lunch = db.query(Meal).filter(Meal.id == plan.lunch_meal_id).first() if plan.lunch_meal_id else None
    dinner = db.query(Meal).filter(Meal.id == plan.dinner_meal_id).first() if plan.dinner_meal_id else None
    snack = db.query(Meal).filter(Meal.id == plan.snack_meal_id).first() if plan.snack_meal_id else None
    
    from database import Meal
    
    return {
        "id": plan.id,
        "user_id": plan.user_id,
        "plan_date": plan.plan_date,
        "breakfast_meal": meal_to_response(breakfast),
        "lunch_meal": meal_to_response(lunch),
        "dinner_meal": meal_to_response(dinner),
        "snack_meal": meal_to_response(snack),
        "total_calories": plan.total_calories,
        "total_protein_g": float(plan.total_protein_g) if plan.total_protein_g else None,
        "total_carbs_g": float(plan.total_carbs_g) if plan.total_carbs_g else None,
        "total_fat_g": float(plan.total_fat_g) if plan.total_fat_g else None
    }


@router.get("/plans/date/{plan_date}", response_model=DailyMealPlanResponse)
async def get_plan_by_date(
    plan_date: date,
    request: Request
):
    """
    Get meal plan for a specific date
    """
    shopify_data = await verify_shopify_request(request)
    shopify_customer_id = shopify_data["shopify_customer_id"]
    
    # Get user
    user = db.query(User).filter(User.shopify_customer_id == shopify_customer_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check onboarding
    preferences = get_user_preferences(db, user.id)
    if not preferences or not preferences.onboarding_completed:
        raise HTTPException(status_code=400, detail="Onboarding not completed")
    
    # Generate or get plan
    plan = generate_daily_plan(db, user.id, plan_date, preferences)
    
    # Load meals
    from database import Meal
    breakfast = db.query(Meal).filter(Meal.id == plan.breakfast_meal_id).first() if plan.breakfast_meal_id else None
    lunch = db.query(Meal).filter(Meal.id == plan.lunch_meal_id).first() if plan.lunch_meal_id else None
    dinner = db.query(Meal).filter(Meal.id == plan.dinner_meal_id).first() if plan.dinner_meal_id else None
    snack = db.query(Meal).filter(Meal.id == plan.snack_meal_id).first() if plan.snack_meal_id else None
    
    return {
        "id": plan.id,
        "user_id": plan.user_id,
        "plan_date": plan.plan_date,
        "breakfast_meal": meal_to_response(breakfast),
        "lunch_meal": meal_to_response(lunch),
        "dinner_meal": meal_to_response(dinner),
        "snack_meal": meal_to_response(snack),
        "total_calories": plan.total_calories,
        "total_protein_g": float(plan.total_protein_g) if plan.total_protein_g else None,
        "total_carbs_g": float(plan.total_carbs_g) if plan.total_carbs_g else None,
        "total_fat_g": float(plan.total_fat_g) if plan.total_fat_g else None
    }


@router.get("/plans/week", response_model=WeeklyPlanResponse)
async def get_weekly_plan(
    week_start: Optional[date] = Query(None, description="Week start date (defaults to current week)"),
    request: Request = None
):
    """
    Get weekly meal plan
    """
    shopify_data = await verify_shopify_request(request)
    shopify_customer_id = shopify_data["shopify_customer_id"]
    
    # Get user
    user = db.query(User).filter(User.shopify_customer_id == shopify_customer_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check onboarding
    preferences = get_user_preferences(db, user.id)
    if not preferences or not preferences.onboarding_completed:
        raise HTTPException(status_code=400, detail="Onboarding not completed")
    
    # Calculate week dates
    if not week_start:
        today = date.today()
        # Get Monday of current week
        days_since_monday = today.weekday()
        week_start = today - timedelta(days=days_since_monday)
    
    week_end = week_start + timedelta(days=6)
    
    # Generate weekly plan
    daily_plans = generate_weekly_plan(db, user.id, week_start, preferences)
    
    # Convert to response format
    from database import Meal
    plan_responses = []
    for plan in daily_plans:
        breakfast = db.query(Meal).filter(Meal.id == plan.breakfast_meal_id).first() if plan.breakfast_meal_id else None
        lunch = db.query(Meal).filter(Meal.id == plan.lunch_meal_id).first() if plan.lunch_meal_id else None
        dinner = db.query(Meal).filter(Meal.id == plan.dinner_meal_id).first() if plan.dinner_meal_id else None
        snack = db.query(Meal).filter(Meal.id == plan.snack_meal_id).first() if plan.snack_meal_id else None
        
        plan_responses.append({
            "id": plan.id,
            "user_id": plan.user_id,
            "plan_date": plan.plan_date,
            "breakfast_meal": meal_to_response(breakfast),
            "lunch_meal": meal_to_response(lunch),
            "dinner_meal": meal_to_response(dinner),
            "snack_meal": meal_to_response(snack),
            "total_calories": plan.total_calories,
            "total_protein_g": float(plan.total_protein_g) if plan.total_protein_g else None,
            "total_carbs_g": float(plan.total_carbs_g) if plan.total_carbs_g else None,
            "total_fat_g": float(plan.total_fat_g) if plan.total_fat_g else None
        })
    
    return {
        "id": 0,  # Weekly plan ID if you create a WeeklyPlan record
        "user_id": user.id,
        "week_start_date": week_start,
        "week_end_date": week_end,
        "status": "active",
        "daily_plans": plan_responses
    }

