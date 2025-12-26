"""
Meal Plans API endpoints
"""
from fastapi import APIRouter, HTTPException, Request, Query
from datetime import date, timedelta
from typing import Optional
from models.schemas import DailyMealPlanResponse, WeeklyPlanResponse
from apis.user_api import verify_shopify_request
from services.meal_service import generate_daily_plan, generate_weekly_plan
from services.user_service import get_user_preferences
from models.database import User, UserPreference, Meal, DailyMealPlan
from beanie import PydanticObjectId

router = APIRouter()


async def get_meal_by_id(meal_id: Optional[str]) -> Optional[Meal]:
    """Get meal by ID"""
    if not meal_id:
        return None
    try:
        return await Meal.get(PydanticObjectId(meal_id))
    except:
        return None


def meal_to_response(meal: Optional[Meal]) -> Optional[dict]:
    """Convert meal model to response dict"""
    if not meal:
        return None
    
    return {
        "id": str(meal.id),
        "title": meal.title,
        "description": meal.description,
        "meal_type": meal.meal_type.value,
        "calories": meal.calories,
        "protein_g": float(meal.protein_g),
        "carbs_g": float(meal.carbs_g),
        "fat_g": float(meal.fat_g),
        "fiber_g": float(meal.fiber_g),
        "ingredients": meal.ingredients,
        "instructions": meal.instructions,
        "prep_time_minutes": meal.prep_time_minutes,
        "cook_time_minutes": meal.cook_time_minutes,
        "tags": meal.tags,
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
    user = await User.find_one(User.shopify_customer_id == shopify_customer_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check onboarding
    preferences = await UserPreference.find_one(UserPreference.user_id == str(user.id))
    if not preferences or not preferences.onboarding_completed:
        raise HTTPException(status_code=400, detail="Onboarding not completed")
    
    # Generate or get today's plan
    today = date.today()
    try:
        plan = await generate_daily_plan(str(user.id), today, preferences)
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        import traceback
        print(f"[ERROR] Failed to generate daily plan: {str(e)}")
        print(f"[ERROR] Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to generate meal plan: {str(e)}")
    
    # Load meals
    breakfast = await get_meal_by_id(plan.breakfast_meal_id)
    lunch = await get_meal_by_id(plan.lunch_meal_id)
    dinner = await get_meal_by_id(plan.dinner_meal_id)
    snack = await get_meal_by_id(plan.snack_meal_id)
    
    return {
        "id": str(plan.id),
        "user_id": str(plan.user_id),
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
    user = await User.find_one(User.shopify_customer_id == shopify_customer_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check onboarding
    preferences = await UserPreference.find_one(UserPreference.user_id == str(user.id))
    if not preferences or not preferences.onboarding_completed:
        raise HTTPException(status_code=400, detail="Onboarding not completed")
    
    # Generate or get plan
    try:
        plan = await generate_daily_plan(str(user.id), plan_date, preferences)
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        import traceback
        print(f"[ERROR] Failed to generate daily plan: {str(e)}")
        print(f"[ERROR] Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to generate meal plan: {str(e)}")
    
    # Load meals
    breakfast = await get_meal_by_id(plan.breakfast_meal_id)
    lunch = await get_meal_by_id(plan.lunch_meal_id)
    dinner = await get_meal_by_id(plan.dinner_meal_id)
    snack = await get_meal_by_id(plan.snack_meal_id)
    
    return {
        "id": str(plan.id),
        "user_id": str(plan.user_id),
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
    user = await User.find_one(User.shopify_customer_id == shopify_customer_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check onboarding
    preferences = await UserPreference.find_one(UserPreference.user_id == str(user.id))
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
    try:
        daily_plans = await generate_weekly_plan(str(user.id), week_start, preferences)
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        import traceback
        print(f"[ERROR] Failed to generate weekly plan: {str(e)}")
        print(f"[ERROR] Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to generate meal plan: {str(e)}")
    
    # Convert to response format
    plan_responses = []
    for plan in daily_plans:
        breakfast = await get_meal_by_id(plan.breakfast_meal_id)
        lunch = await get_meal_by_id(plan.lunch_meal_id)
        dinner = await get_meal_by_id(plan.dinner_meal_id)
        snack = await get_meal_by_id(plan.snack_meal_id)
        
        plan_responses.append({
            "id": str(plan.id),
            "user_id": str(plan.user_id),
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
        "user_id": str(user.id),
        "week_start_date": week_start,
        "week_end_date": week_end,
        "status": "active",
        "daily_plans": plan_responses
    }
