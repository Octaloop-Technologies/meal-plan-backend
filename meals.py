"""
Meal APIs - Protected by subscription access control
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from datetime import date, timedelta
from typing import Optional, List
from database import (
    User, UserPreference, Meal, DailyMealPlan, MealRotationLog, MealType
)
from schemas import DailyMealPlanResponse, MealResponse
from subscription import require_active_subscription, get_current_user
from meal_engine import generate_daily_plan, generate_weekly_plan
from meal_plan_pdf import generate_meal_plan_pdf
from beanie import PydanticObjectId
import os

router = APIRouter()


async def get_meal_by_id(meal_id: str) -> Optional[Meal]:
    """Get meal by ID, handling errors gracefully"""
    if not meal_id:
        return None
    try:
        return await Meal.get(PydanticObjectId(meal_id))
    except Exception:
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


@router.get("/meals/today", response_model=DailyMealPlanResponse)
async def get_today_meals(
    request: Request,
    user: User = Depends(require_active_subscription)
):
    """
    Get today's meal plan for the authenticated user
    Requires active subscription
    """
    # Get user preferences
    preferences = await UserPreference.find_one(UserPreference.user_id == str(user.id))
    if not preferences or not preferences.onboarding_completed:
        raise HTTPException(status_code=400, detail="Onboarding not completed")
    
    # Get or generate today's plan
    today = date.today()
    try:
        daily_plan = await generate_daily_plan(str(user.id), today, preferences)
    except ValueError as e:
        # No meals available in database
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        # Log the error for debugging
        import traceback
        print(f"[ERROR] Failed to generate daily plan: {str(e)}")
        print(f"[ERROR] Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to generate meal plan: {str(e)}")
    
    # Load meals
    breakfast = await get_meal_by_id(daily_plan.breakfast_meal_id)
    lunch = await get_meal_by_id(daily_plan.lunch_meal_id)
    dinner = await get_meal_by_id(daily_plan.dinner_meal_id)
    snack = await get_meal_by_id(daily_plan.snack_meal_id)
    
    return {
        "id": str(daily_plan.id),
        "user_id": str(daily_plan.user_id),
        "plan_date": daily_plan.plan_date,
        "breakfast_meal": meal_to_response(breakfast),
        "lunch_meal": meal_to_response(lunch),
        "dinner_meal": meal_to_response(dinner),
        "snack_meal": meal_to_response(snack),
        "total_calories": daily_plan.total_calories,
        "total_protein_g": float(daily_plan.total_protein_g) if daily_plan.total_protein_g else None,
        "total_carbs_g": float(daily_plan.total_carbs_g) if daily_plan.total_carbs_g else None,
        "total_fat_g": float(daily_plan.total_fat_g) if daily_plan.total_fat_g else None
    }


@router.get("/meals/weekly", response_model=List[DailyMealPlanResponse])
async def get_weekly_meals(
    request: Request,
    week_start: Optional[date] = None,
    user: User = Depends(require_active_subscription)
):
    """
    Get weekly meal plan (7 days)
    Requires active subscription
    """
    # Get user preferences
    preferences = await UserPreference.find_one(UserPreference.user_id == str(user.id))
    if not preferences or not preferences.onboarding_completed:
        raise HTTPException(status_code=400, detail="Onboarding not completed")
    
    # Calculate week dates
    if not week_start:
        today = date.today()
        days_since_monday = today.weekday()
        week_start = today - timedelta(days=days_since_monday)
    
    # Generate weekly plan
    try:
        daily_plans = await generate_weekly_plan(str(user.id), week_start, preferences)
    except ValueError as e:
        # No meals available in database
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        # Log the error for debugging
        import traceback
        print(f"[ERROR] Failed to generate weekly plan: {str(e)}")
        print(f"[ERROR] Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to generate meal plan: {str(e)}")
    
    # Convert to response format
    plan_responses = []
    try:
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
    except Exception as e:
        # Log the error for debugging
        import traceback
        print(f"[ERROR] Failed to convert weekly plan to response: {str(e)}")
        print(f"[ERROR] Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to process meal plan: {str(e)}")
    
    return plan_responses


@router.get("/meals/today/pdf/download")
async def download_today_meal_plan_pdf(
    request: Request,
    user: User = Depends(require_active_subscription)
):
    """
    Download today's meal plan as PDF
    """
    try:
        # Get user preferences
        preferences = await UserPreference.find_one(UserPreference.user_id == str(user.id))
        if not preferences or not preferences.onboarding_completed:
            raise HTTPException(status_code=400, detail="Onboarding not completed")
        
        # Get today's plan
        today = date.today()
        try:
            daily_plan = await generate_daily_plan(str(user.id), today, preferences)
        except ValueError as e:
            raise HTTPException(status_code=503, detail=str(e))
        except Exception as e:
            import traceback
            print(f"[ERROR] Failed to generate daily plan for PDF: {str(e)}")
            print(f"[ERROR] Traceback: {traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=f"Failed to generate meal plan: {str(e)}")
        
        # Load meals
        breakfast = await get_meal_by_id(daily_plan.breakfast_meal_id)
        lunch = await get_meal_by_id(daily_plan.lunch_meal_id)
        dinner = await get_meal_by_id(daily_plan.dinner_meal_id)
        snack = await get_meal_by_id(daily_plan.snack_meal_id)
        
        # Prepare plan data
        plan_data = {
            "id": str(daily_plan.id),
            "plan_date": daily_plan.plan_date.isoformat(),
            "breakfast_meal": meal_to_response(breakfast),
            "lunch_meal": meal_to_response(lunch),
            "dinner_meal": meal_to_response(dinner),
            "snack_meal": meal_to_response(snack),
            "total_calories": daily_plan.total_calories,
            "total_protein_g": float(daily_plan.total_protein_g) if daily_plan.total_protein_g else None,
            "total_carbs_g": float(daily_plan.total_carbs_g) if daily_plan.total_carbs_g else None,
            "total_fat_g": float(daily_plan.total_fat_g) if daily_plan.total_fat_g else None
        }
        
        # Generate PDF
        user_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email.split('@')[0]
        pdf_path = generate_meal_plan_pdf(
            [plan_data],
            plan_type='today',
            user_name=user_name
        )
        
        if not os.path.exists(pdf_path):
            raise HTTPException(status_code=500, detail="Failed to generate PDF")
        
        return FileResponse(
            pdf_path,
            media_type='application/pdf',
            filename=f"meal_plan_today_{today.isoformat()}.pdf"
        )
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"[ERROR] PDF download error: {str(e)}")
        print(f"[ERROR] Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {str(e)}")


@router.get("/meals/week/pdf/download")
async def download_weekly_meal_plan_pdf(
    request: Request,
    week_start: Optional[date] = None,
    user: User = Depends(require_active_subscription)
):
    """
    Download weekly meal plan as PDF
    """
    try:
        # Get user preferences
        preferences = await UserPreference.find_one(UserPreference.user_id == str(user.id))
        if not preferences or not preferences.onboarding_completed:
            raise HTTPException(status_code=400, detail="Onboarding not completed")
        
        # Calculate week dates
        if not week_start:
            today = date.today()
            days_since_monday = today.weekday()
            week_start = today - timedelta(days=days_since_monday)
        
        # Generate weekly plan
        try:
            daily_plans = await generate_weekly_plan(str(user.id), week_start, preferences)
        except ValueError as e:
            raise HTTPException(status_code=503, detail=str(e))
        except Exception as e:
            import traceback
            print(f"[ERROR] Failed to generate weekly plan for PDF: {str(e)}")
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
                "plan_date": plan.plan_date.isoformat(),
                "breakfast_meal": meal_to_response(breakfast),
                "lunch_meal": meal_to_response(lunch),
                "dinner_meal": meal_to_response(dinner),
                "snack_meal": meal_to_response(snack),
                "total_calories": plan.total_calories,
                "total_protein_g": float(plan.total_protein_g) if plan.total_protein_g else None,
                "total_carbs_g": float(plan.total_carbs_g) if plan.total_carbs_g else None,
                "total_fat_g": float(plan.total_fat_g) if plan.total_fat_g else None
            })
        
        # Generate PDF
        user_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email.split('@')[0]
        pdf_path = generate_meal_plan_pdf(
            plan_responses,
            plan_type='week',
            user_name=user_name
        )
        
        if not os.path.exists(pdf_path):
            raise HTTPException(status_code=500, detail="Failed to generate PDF")
        
        return FileResponse(
            pdf_path,
            media_type='application/pdf',
            filename=f"meal_plan_week_{week_start.isoformat()}.pdf"
        )
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"[ERROR] PDF download error: {str(e)}")
        print(f"[ERROR] Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {str(e)}")

