"""
Shopping List API - Protected by subscription access control
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from datetime import date, timedelta
from typing import Optional
from database import (
    User, DailyMealPlan, Meal, ShoppingList
)
from subscription import require_active_subscription
from meal_engine import generate_weekly_plan
from pdf_service import (
    aggregate_ingredients, generate_shopping_list_pdf, get_pdf_url
)
from user_service import get_user_preferences
from config import settings
import os

router = APIRouter()


@router.get("/shopping-list/pdf")
async def get_shopping_list_pdf(
    request: Request,
    week_start: Optional[date] = None,
    user: User = Depends(require_active_subscription)
):
    """
    Generate and return shopping list PDF for weekly meals
    Requires active subscription
    """
    try:
        # Get user preferences
        preferences = await get_user_preferences(str(user.id))
        if not preferences or not preferences.onboarding_completed:
            raise HTTPException(status_code=400, detail="Onboarding not completed")
        
        # Calculate week dates
        if not week_start:
            today = date.today()
            days_since_monday = today.weekday()
            week_start = today - timedelta(days=days_since_monday)
        
        week_end = week_start + timedelta(days=6)
        
        # Check if shopping list already exists
        existing_list = await ShoppingList.find_one(
            ShoppingList.user_id == str(user.id),
            ShoppingList.week_start_date == week_start,
            ShoppingList.week_end_date == week_end
        )
        
        if existing_list and existing_list.pdf_url:
            # Return existing PDF URL
            return {
                "pdf_url": existing_list.pdf_url,
                "week_start": week_start.isoformat() if isinstance(week_start, date) else str(week_start),
                "week_end": week_end.isoformat() if isinstance(week_end, date) else str(week_end),
                "ingredients": existing_list.ingredients or []
            }
        
        # Generate weekly plan if not exists
        try:
            daily_plans = await generate_weekly_plan(str(user.id), week_start, preferences)
        except ValueError as e:
            raise HTTPException(status_code=503, detail=str(e))
        except Exception as e:
            import traceback
            print(f"[ERROR] Failed to generate weekly plan: {str(e)}")
            print(f"[ERROR] Traceback: {traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=f"Failed to generate meal plan: {str(e)}")
        
        # Collect all ingredients from all meals
        # aggregate_ingredients expects a list of lists (one list per meal)
        all_ingredients_lists = []
        from beanie import PydanticObjectId
        
        async def get_meal_by_id(meal_id: str):
            if not meal_id:
                return None
            try:
                return await Meal.get(PydanticObjectId(meal_id))
            except Exception:
                return None
        
        for plan in daily_plans:
            meal_ids = [
                plan.breakfast_meal_id,
                plan.lunch_meal_id,
                plan.dinner_meal_id,
                plan.snack_meal_id
            ]
            
            for meal_id in meal_ids:
                if meal_id:
                    meal = await get_meal_by_id(meal_id)
                    if meal and meal.ingredients:
                        # Each meal's ingredients is a list, so append the whole list
                        # aggregate_ingredients expects List[List[Dict]]
                        all_ingredients_lists.append(meal.ingredients)
        
        # Aggregate ingredients (expects list of lists)
        try:
            aggregated = aggregate_ingredients(all_ingredients_lists)
        except Exception as e:
            import traceback
            print(f"[ERROR] Failed to aggregate ingredients: {str(e)}")
            print(f"[ERROR] Traceback: {traceback.format_exc()}")
            print(f"[ERROR] all_ingredients_lists type: {type(all_ingredients_lists)}")
            print(f"[ERROR] all_ingredients_lists length: {len(all_ingredients_lists) if all_ingredients_lists else 0}")
            if all_ingredients_lists:
                print(f"[ERROR] First item type: {type(all_ingredients_lists[0])}")
                print(f"[ERROR] First item: {all_ingredients_lists[0]}")
            raise HTTPException(status_code=500, detail=f"Failed to aggregate ingredients: {str(e)}")
        
        # Generate PDF
        try:
            user_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email
            pdf_path = generate_shopping_list_pdf(
                aggregated,
                week_start,
                week_end,
                user_name
            )
        except Exception as e:
            import traceback
            print(f"[ERROR] Failed to generate PDF: {str(e)}")
            print(f"[ERROR] Traceback: {traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {str(e)}")
        
        # Generate PDF URL
        pdf_url = get_pdf_url(pdf_path)
        
        # Save shopping list record
        shopping_list = ShoppingList(
            user_id=str(user.id),
            week_start_date=week_start,
            week_end_date=week_end,
            ingredients=[{"name": ing.name, "total_quantity": ing.total_quantity, "unit": ing.unit} for ing in aggregated],
            pdf_url=pdf_url
        )
        await shopping_list.insert()
        
        return {
            "pdf_url": pdf_url,
            "week_start": week_start.isoformat() if isinstance(week_start, date) else str(week_start),
            "week_end": week_end.isoformat() if isinstance(week_end, date) else str(week_end),
            "ingredients": [{"name": ing.name, "total_quantity": ing.total_quantity, "unit": ing.unit} for ing in aggregated]
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"[ERROR] Shopping list error: {str(e)}")
        print(f"[ERROR] Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to generate shopping list: {str(e)}")


@router.get("/shopping-list/pdf/download")
async def download_shopping_list_pdf(
    request: Request,
    week_start: Optional[date] = None,
    user: User = Depends(require_active_subscription)
):
    """
    Download shopping list PDF directly
    Requires active subscription
    """
    # Get user preferences
    preferences = await get_user_preferences(str(user.id))
    if not preferences or not preferences.onboarding_completed:
        raise HTTPException(status_code=400, detail="Onboarding not completed")
    
    # Calculate week dates
    if not week_start:
        today = date.today()
        days_since_monday = today.weekday()
        week_start = today - timedelta(days=days_since_monday)
    
    week_end = week_start + timedelta(days=6)
    
    # Check if shopping list exists
    existing_list = await ShoppingList.find_one(
        ShoppingList.user_id == str(user.id),
        ShoppingList.week_start_date == week_start,
        ShoppingList.week_end_date == week_end
    )
    
    pdf_path = None
    if existing_list and existing_list.pdf_url:
        # Extract file path from URL
        filename = existing_list.pdf_url.split('/')[-1]
        pdf_path = os.path.join(settings.PDF_STORAGE_PATH, filename)
    
    if not pdf_path or not os.path.exists(pdf_path):
        # Generate new PDF
        result = await get_shopping_list_pdf(request, week_start, user)
        filename = result["pdf_url"].split('/')[-1]
        pdf_path = os.path.join(settings.PDF_STORAGE_PATH, filename)
    
    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="PDF not found")
    
    # Return file
    from fastapi.responses import FileResponse
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=f"shopping_list_{week_start}_{week_end}.pdf"
    )
