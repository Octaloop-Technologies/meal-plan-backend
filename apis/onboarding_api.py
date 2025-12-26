"""
Onboarding API endpoints (MongoDB)
"""
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from models.database import User, UserPreference
from models.schemas import OnboardingComplete, UserPreferenceResponse, SuccessResponse
from apis.user_api import verify_shopify_request, get_current_user_from_token
from config import settings
from services.user_service import get_or_create_user, save_onboarding_data, get_user_preferences
from datetime import datetime
from typing import Optional

router = APIRouter()
security = HTTPBearer(auto_error=False)


@router.post("/onboarding/complete", response_model=UserPreferenceResponse)
async def complete_onboarding(
    onboarding_data: OnboardingComplete,
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
):
    """
    Complete onboarding quiz and save user preferences
    Supports both JWT-authenticated users and Shopify users
    """
    try:
        user = None
        
        # Try to get user from JWT token first (for email/password users)
        if credentials:
            try:
                current_user_data = await get_current_user_from_token(credentials)
                user_id = current_user_data["user_id"]
                user = await User.get(user_id)
            except:
                pass  # No JWT token, try Shopify
        
        # If no JWT user, try Shopify authentication
        if not user:
            try:
                shopify_data = await verify_shopify_request(request)
                shopify_customer_id = shopify_data["shopify_customer_id"]
            except HTTPException as e:
                # In development, if verification fails, use test customer ID
                if settings.DEBUG:
                    print(f"[DEBUG] Shopify verification failed, using test customer ID: {e.detail}")
                    shopify_customer_id = request.query_params.get('customer_id', '123')
                    try:
                        shopify_customer_id = int(shopify_customer_id)
                    except ValueError:
                        shopify_customer_id = 123
                else:
                    raise HTTPException(status_code=401, detail="Authentication required. Please login or provide valid credentials.")
            
            # Get or create user
            user = await get_or_create_user(
                shopify_customer_id=shopify_customer_id,
                email=f"customer_{shopify_customer_id}@shopify.com",  # Placeholder - fetch from Shopify
                first_name=None  # First name can be set later if needed
            )
        
        # Save onboarding data
        preference = await save_onboarding_data(str(user.id), onboarding_data)
        
        # Return response
        return UserPreferenceResponse(
            id=str(preference.id),
            user_id=str(preference.user_id),
            age=preference.age,
            height_cm=preference.height_cm,
            weight_kg=preference.weight_kg,
            goal=preference.goal.value,
            activity_level=preference.activity_level.value,
            dietary_preferences=preference.dietary_preferences,
            allergies=preference.allergies,
            daily_calorie_target=preference.daily_calorie_target,
            protein_target_g=preference.protein_target_g,
            carb_target_g=preference.carb_target_g,
            fat_target_g=preference.fat_target_g,
            onboarding_completed=preference.onboarding_completed
        )
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        import traceback
        error_detail = str(e)
        traceback_str = traceback.format_exc()
        print(f"[ERROR] Onboarding error: {error_detail}")
        print(f"[ERROR] Traceback: {traceback_str}")
        # Return more detailed error in development
        if settings.DEBUG:
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to save onboarding data: {error_detail}. Traceback: {traceback_str[:500]}"
            )
        else:
            raise HTTPException(status_code=500, detail=f"Failed to save onboarding data: {error_detail}")


@router.get("/onboarding/status", response_model=UserPreferenceResponse)
async def get_onboarding_status(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
):
    """
    Check if user has completed onboarding
    Supports both JWT-authenticated users and Shopify users
    """
    user = None
    
    # Try to get user from JWT token first (for email/password users)
    if credentials:
        try:
            current_user_data = await get_current_user_from_token(credentials)
            user_id = current_user_data["user_id"]
            user = await User.get(user_id)
        except:
            pass  # No JWT token, try Shopify
    
    # If no JWT user, try Shopify authentication
    if not user:
        try:
            shopify_data = await verify_shopify_request(request)
            shopify_customer_id = shopify_data["shopify_customer_id"]
            user = await User.find_one(User.shopify_customer_id == shopify_customer_id)
        except HTTPException:
            raise HTTPException(status_code=401, detail="Authentication required")
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get preferences
    preference = await get_user_preferences(str(user.id))
    
    if not preference:
        # Return a response indicating onboarding is not completed (not an error)
        raise HTTPException(
            status_code=404, 
            detail="Onboarding not completed",
            headers={"X-Onboarding-Status": "not_completed"}
        )
    
    # Return response
    return UserPreferenceResponse(
        id=str(preference.id),
        user_id=str(preference.user_id),
        age=preference.age,
        height_cm=preference.height_cm,
        weight_kg=preference.weight_kg,
        goal=preference.goal.value,
        activity_level=preference.activity_level.value,
        dietary_preferences=preference.dietary_preferences,
        allergies=preference.allergies,
        daily_calorie_target=preference.daily_calorie_target,
        protein_target_g=preference.protein_target_g,
        carb_target_g=preference.carb_target_g,
        fat_target_g=preference.fat_target_g,
        onboarding_completed=preference.onboarding_completed
    )
