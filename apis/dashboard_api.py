"""
Customer Dashboard APIs - Protected by subscription access control
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from datetime import date, timedelta
from typing import Optional, Dict, Any
from models.database import (
    User, UserPreference, Subscription, SubscriptionStatus, DailyMealPlan, Meal, AIMealSuggestion
)
from services.subscription_service import require_active_subscription, get_current_user, get_user_subscription
from services.meal_service import generate_daily_plan
from services.user_service import get_user_preferences
from services.openai_service import generate_meal_suggestions

router = APIRouter()


@router.get("/dashboard")
async def get_dashboard(
    request: Request,
    user: User = Depends(require_active_subscription)
):
    """
    Get customer dashboard data
    Requires active subscription
    Returns: today's meals, weekly plan preview, subscription status
    """
    # Get user preferences
    preferences = await get_user_preferences(str(user.id))
    
    # Get today's plan
    today = date.today()
    daily_plan = await generate_daily_plan(str(user.id), today, preferences)
    
    # Load meals
    from beanie import PydanticObjectId
    
    async def get_meal_by_id(meal_id: str):
        if not meal_id:
            return None
        try:
            return await Meal.get(PydanticObjectId(meal_id))
        except Exception:
            return None
    
    breakfast = await get_meal_by_id(daily_plan.breakfast_meal_id)
    lunch = await get_meal_by_id(daily_plan.lunch_meal_id)
    dinner = await get_meal_by_id(daily_plan.dinner_meal_id)
    snack = await get_meal_by_id(daily_plan.snack_meal_id)
    
    # Get subscription
    subscription = await get_user_subscription(user)
    
    # Get weekly preview (next 3 days)
    week_preview = []
    for i in range(1, 4):
        preview_date = today + timedelta(days=i)
        preview_plan = await DailyMealPlan.find_one(
            DailyMealPlan.user_id == str(user.id),
            DailyMealPlan.plan_date == preview_date
        )
        if preview_plan:
            week_preview.append({
                "date": preview_date,
                "has_plan": True
            })
        else:
            week_preview.append({
                "date": preview_date,
                "has_plan": False
            })
    
    return {
        "user": {
            "id": str(user.id),
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name
        },
        "today": {
            "date": today,
            "breakfast": {
                "id": str(breakfast.id),
                "title": breakfast.title,
                "image_url": breakfast.image_url
            } if breakfast else None,
            "lunch": {
                "id": str(lunch.id),
                "title": lunch.title,
                "image_url": lunch.image_url
            } if lunch else None,
            "dinner": {
                "id": str(dinner.id),
                "title": dinner.title,
                "image_url": dinner.image_url
            } if dinner else None,
            "snack": {
                "id": str(snack.id),
                "title": snack.title,
                "image_url": snack.image_url
            } if snack else None,
            "total_calories": daily_plan.total_calories,
            "total_protein_g": daily_plan.total_protein_g,
            "total_carbs_g": daily_plan.total_carbs_g,
            "total_fat_g": daily_plan.total_fat_g
        },
        "week_preview": week_preview,
        "subscription": {
            "status": subscription.status.value if subscription else None,
            "next_charge_date": subscription.next_charge_date if subscription else None
        }
    }


@router.get("/account")
async def get_account(
    request: Request,
    user: User = Depends(get_current_user)
):
    """
    Get customer account information
    """
    preferences = await get_user_preferences(str(user.id))
    subscription = await Subscription.find_one(Subscription.user_id == str(user.id))
    
    return {
        "user": {
            "id": str(user.id),
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "phone": user.phone,
            "shopify_customer_id": user.shopify_customer_id
        },
        "preferences": {
            "age": preferences.age if preferences else None,
            "height_cm": preferences.height_cm if preferences else None,
            "weight_kg": preferences.weight_kg if preferences else None,
            "goal": preferences.goal.value if preferences else None,
            "activity_level": preferences.activity_level.value if preferences else None,
            "dietary_preferences": preferences.dietary_preferences if preferences else [],
            "allergies": preferences.allergies if preferences else [],
            "onboarding_completed": preferences.onboarding_completed if preferences else False
        },
        "subscription": {
            "status": subscription.status.value if subscription else None,
            "subscription_provider": subscription.subscription_provider.value if subscription else None,
            "next_charge_date": subscription.next_charge_date if subscription else None,
            "created_at": subscription.created_at if subscription else None
        } if subscription else None
    }


@router.get("/preferences")
async def get_preferences(
    request: Request,
    user: User = Depends(get_current_user)
):
    """
    Get user preferences from user_preferences collection
    """
    preferences = await get_user_preferences(str(user.id))
    
    if not preferences:
        raise HTTPException(
            status_code=404,
            detail="Preferences not found. Please complete onboarding first."
        )
    
    return {
        "id": str(preferences.id),
        "user_id": str(preferences.user_id),
        "age": preferences.age,
        "height_cm": preferences.height_cm,
        "weight_kg": preferences.weight_kg,
        "goal": preferences.goal.value if preferences.goal else None,
        "activity_level": preferences.activity_level.value if preferences.activity_level else None,
        "dietary_preferences": preferences.dietary_preferences or [],
        "allergies": preferences.allergies or [],
        "daily_calorie_target": preferences.daily_calorie_target,
        "protein_target_g": preferences.protein_target_g,
        "carb_target_g": preferences.carb_target_g,
        "fat_target_g": preferences.fat_target_g,
        "onboarding_completed": preferences.onboarding_completed,
        "created_at": preferences.created_at.isoformat() if preferences.created_at else None,
        "updated_at": preferences.updated_at.isoformat() if preferences.updated_at else None
    }


@router.post("/account/update")
async def update_account(
    request: Request,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    phone: Optional[str] = None,
    user: User = Depends(get_current_user)
):
    """
    Update customer account information
    """
    if first_name is not None:
        user.first_name = first_name
    if last_name is not None:
        user.last_name = last_name
    if phone is not None:
        user.phone = phone
    
    await user.save()
    
    return {
        "success": True,
        "message": "Account updated",
        "user": {
            "id": str(user.id),
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "phone": user.phone
        }
    }


@router.get("/subscription/status")
async def get_subscription_status(
    request: Request,
    user: User = Depends(get_current_user)
):
    """
    Get subscription status (legacy endpoint - use /subscription instead)
    """
    subscription = await Subscription.find_one(Subscription.user_id == str(user.id))
    
    if not subscription:
        return {
            "has_subscription": False,
            "status": None,
            "message": "No subscription found"
        }
    
    return {
        "has_subscription": True,
        "status": subscription.status.value,
        "subscription_provider": subscription.subscription_provider.value,
        "next_charge_date": subscription.next_charge_date.isoformat() if subscription.next_charge_date else None,
        "is_active": subscription.status == SubscriptionStatus.ACTIVE,
        "created_at": subscription.created_at.isoformat(),
        "last_synced_at": subscription.last_synced_at.isoformat()
    }


@router.post("/ai/meal-suggestions")
async def get_ai_meal_suggestions(
    request: Request,
    plan_type: Optional[str] = None,  # "daily" or "weekly"
    user: User = Depends(get_current_user)
):
    """
    Get AI-powered meal suggestions based on user preferences
    Fetches user preferences from database and sends to OpenAI
    
    Args:
        plan_type: "daily" or "weekly"
    
    Returns:
        AI-generated meal plan with breakfast, lunch, dinner, and snack
    """
    # Get user preferences
    preferences = await get_user_preferences(str(user.id))
    
    if not preferences:
        raise HTTPException(
            status_code=404,
            detail="Preferences not found. Please complete onboarding first."
        )
    
    # Get plan_type from query params or default to "daily"
    if not plan_type:
        # Try to get from query params
        plan_type = request.query_params.get("plan_type", "daily")
    
    # Validate plan_type
    if plan_type not in ["daily", "weekly"]:
        raise HTTPException(
            status_code=400,
            detail="plan_type must be 'daily' or 'weekly'"
        )
    
    try:
        # Generate meal suggestions using OpenAI
        meal_plan = await generate_meal_suggestions(preferences, plan_type)
        
        return {
            "success": True,
            "plan_type": plan_type,
            "user_preferences": {
                "goal": preferences.goal.value if preferences.goal else None,
                "daily_calorie_target": preferences.daily_calorie_target,
                "dietary_preferences": preferences.dietary_preferences or [],
                "allergies": preferences.allergies or []
            },
            "meal_plan": meal_plan
        }
    except ValueError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate meal suggestions: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"OpenAI service error: {str(e)}"
        )


@router.get("/ai/meal-suggestions/saved")
async def get_saved_ai_meal_suggestions(
    request: Request,
    plan_type: Optional[str] = None,
    user: User = Depends(get_current_user)
):
    """
    Get saved AI meal suggestions for the logged-in user
    Returns the most recent AI-generated meal suggestions from database
    """
    try:
        user_id_str = str(user.id)
        print(f"[DEBUG] ===== Fetching AI suggestions =====")
        print(f"[DEBUG] User object ID type: {type(user.id)}, value: {user.id}")
        print(f"[DEBUG] User ID string: {user_id_str}")
        print(f"[DEBUG] Plan type requested: {plan_type}")
        
        # Try to find all suggestions for this user (for debugging)
        all_suggestions = await AIMealSuggestion.find_all().to_list()
        print(f"[DEBUG] Total suggestions in collection: {len(all_suggestions)}")
        if all_suggestions:
            sample_user_ids = [str(s.user_id) for s in all_suggestions[:10]]
            print(f"[DEBUG] Sample user_ids in collection: {sample_user_ids}")
            # Check if any match our user_id (exact match)
            exact_matches = [s for s in all_suggestions if str(s.user_id) == user_id_str]
            print(f"[DEBUG] Exact matches for user_id '{user_id_str}': {len(exact_matches)}")
            if exact_matches:
                for match in exact_matches[:3]:
                    print(f"[DEBUG]   - Match: plan_type={match.plan_type}, id={match.id}, created_at={match.created_at}")
            else:
                # Try to find similar user_ids (maybe format difference)
                similar = [s for s in all_suggestions if user_id_str in str(s.user_id) or str(s.user_id) in user_id_str]
                if similar:
                    print(f"[DEBUG] Found {len(similar)} similar user_ids (partial match)")
                    for s in similar[:3]:
                        print(f"[DEBUG]   - Similar: user_id={s.user_id} (type: {type(s.user_id)})")
        
        # Check total count of suggestions for this user - use dict query
        total_count = await AIMealSuggestion.find({"user_id": user_id_str}).count()
        print(f"[DEBUG] Total AI suggestions found for user_id '{user_id_str}': {total_count}")
        
        # Also try with ObjectId if user.id is ObjectId
        from beanie import PydanticObjectId
        try:
            if isinstance(user.id, PydanticObjectId):
                total_count_objid = await AIMealSuggestion.find({"user_id": str(user.id)}).count()
                print(f"[DEBUG] Total with ObjectId string: {total_count_objid}")
        except:
            pass
        
        # Get the most recent suggestion(s)
        if plan_type:
            # Get most recent for specific plan type - try both methods
            suggestion = None
            try:
                suggestion = await AIMealSuggestion.find(
                    AIMealSuggestion.user_id == user_id_str,
                    AIMealSuggestion.plan_type == plan_type
                ).sort("-created_at").first()
            except:
                try:
                    suggestion = await AIMealSuggestion.find({
                        "user_id": user_id_str,
                        "plan_type": plan_type
                    }).sort("-created_at").first()
                except Exception as e:
                    print(f"[DEBUG] Error querying with plan_type: {e}")
            
            print(f"[DEBUG] Found {plan_type} suggestion: {suggestion is not None}")
            
            if not suggestion:
                return {
                    "success": False,
                    "message": f"No {plan_type} AI meal suggestions found for this user",
                    "suggestions": None,
                    "user_id": user_id_str,
                    "total_count": total_count,
                    "all_user_ids_in_db": [str(s.user_id) for s in all_suggestions[:10]] if all_suggestions else []
                }
            
            return {
                "success": True,
                "plan_type": suggestion.plan_type,
                "suggestion_id": str(suggestion.id),
                "created_at": suggestion.created_at.isoformat(),
                "user_preferences": suggestion.user_preferences_snapshot,
                "meal_plan": suggestion.meal_plan
            }
        else:
            # Get most recent daily and weekly - use dict query (most reliable)
            daily_suggestion = None
            weekly_suggestion = None
            
            # Use dict query - most reliable for MongoDB/Beanie
            try:
                # Query for daily
                daily_query = {"user_id": user_id_str, "plan_type": "daily"}
                daily_suggestion = await AIMealSuggestion.find(daily_query).sort("-created_at").first()
                print(f"[DEBUG] Daily query: {daily_query}")
                print(f"[DEBUG] Daily suggestion found: {daily_suggestion is not None}")
                if daily_suggestion:
                    print(f"[DEBUG] Daily suggestion ID: {daily_suggestion.id}, user_id: {daily_suggestion.user_id}")
                
                # Query for weekly
                weekly_query = {"user_id": user_id_str, "plan_type": "weekly"}
                weekly_suggestion = await AIMealSuggestion.find(weekly_query).sort("-created_at").first()
                print(f"[DEBUG] Weekly query: {weekly_query}")
                print(f"[DEBUG] Weekly suggestion found: {weekly_suggestion is not None}")
                if weekly_suggestion:
                    print(f"[DEBUG] Weekly suggestion ID: {weekly_suggestion.id}, user_id: {weekly_suggestion.user_id}")
                    
            except Exception as e:
                import traceback
                print(f"[DEBUG] Error querying AI suggestions: {e}")
                print(traceback.format_exc())
            
            print(f"[DEBUG] Daily suggestion found: {daily_suggestion is not None}")
            print(f"[DEBUG] Weekly suggestion found: {weekly_suggestion is not None}")
            
            if daily_suggestion:
                print(f"[DEBUG] Daily suggestion user_id: {daily_suggestion.user_id}, type: {type(daily_suggestion.user_id)}")
            if weekly_suggestion:
                print(f"[DEBUG] Weekly suggestion user_id: {weekly_suggestion.user_id}, type: {type(weekly_suggestion.user_id)}")
            
            result = {
                "success": True,
                "daily": None,
                "weekly": None,
                "user_id": user_id_str,
                "total_count": total_count
            }
            
            if daily_suggestion:
                result["daily"] = {
                    "suggestion_id": str(daily_suggestion.id),
                    "created_at": daily_suggestion.created_at.isoformat(),
                    "user_preferences": daily_suggestion.user_preferences_snapshot,
                    "meal_plan": daily_suggestion.meal_plan
                }
            
            if weekly_suggestion:
                result["weekly"] = {
                    "suggestion_id": str(weekly_suggestion.id),
                    "created_at": weekly_suggestion.created_at.isoformat(),
                    "user_preferences": weekly_suggestion.user_preferences_snapshot,
                    "meal_plan": weekly_suggestion.meal_plan
                }
            
            if not result["daily"] and not result["weekly"]:
                return {
                    "success": False,
                    "message": "No AI meal suggestions found for this user",
                    "daily": None,
                    "weekly": None,
                    "user_id": user_id_str,
                    "total_count": total_count,
                    "all_user_ids_in_db": [str(s.user_id) for s in all_suggestions[:10]] if all_suggestions else []
                }
            
            return result
            
    except Exception as e:
        import traceback
        print(f"[ERROR] Error fetching AI meal suggestions: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching AI meal suggestions: {str(e)}"
        )

