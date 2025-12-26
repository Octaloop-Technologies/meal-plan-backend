"""
Admin API endpoints for meal management and Shopify data (MongoDB)
"""
from fastapi import APIRouter, Depends, HTTPException, Header, Request
from typing import List, Optional, Dict, Any
from beanie import PydanticObjectId
from beanie.operators import In
import asyncio
from database import Meal, MealType, User, Subscription, SubscriptionPlan, UserPreference, AIMealSuggestion
from schemas import MealCreate, MealUpdate, MealResponse, SuccessResponse
from auth import verify_admin_api_key
from shopify import shopify_client
from config import settings
from user_service import get_user_preferences
from openai_service import generate_meal_suggestions
from datetime import datetime

router = APIRouter()


@router.post("/admin/meals", response_model=MealResponse, status_code=201)
async def create_meal(
    meal_data: MealCreate,
    api_key: str = Depends(verify_admin_api_key)
):
    """Create a new meal"""
    # Convert Pydantic model to Meal document
    meal = Meal(
        title=meal_data.title,
        description=meal_data.description,
        meal_type=MealType(meal_data.meal_type),
        calories=meal_data.calories,
        protein_g=meal_data.protein_g,
        carbs_g=meal_data.carbs_g,
        fat_g=meal_data.fat_g,
        fiber_g=meal_data.fiber_g,
        ingredients=[ing.dict() for ing in meal_data.ingredients],
        instructions=meal_data.instructions,
        prep_time_minutes=meal_data.prep_time_minutes,
        cook_time_minutes=meal_data.cook_time_minutes,
        tags=meal_data.tags,
        image_url=meal_data.image_url,
        video_url=meal_data.video_url,
        is_active=meal_data.is_active
    )
    
    await meal.insert()
    
    return MealResponse(
        id=str(meal.id),
        title=meal.title,
        description=meal.description,
        meal_type=meal.meal_type.value,
        calories=meal.calories,
        protein_g=meal.protein_g,
        carbs_g=meal.carbs_g,
        fat_g=meal.fat_g,
        fiber_g=meal.fiber_g,
        ingredients=meal.ingredients,
        instructions=meal.instructions,
        prep_time_minutes=meal.prep_time_minutes,
        cook_time_minutes=meal.cook_time_minutes,
        tags=meal.tags,
        image_url=meal.image_url,
        video_url=meal.video_url,
        is_active=meal.is_active,
        created_at=meal.created_at,
        updated_at=meal.updated_at
    )


@router.get("/admin/meals", response_model=List[MealResponse])
async def list_meals(
    meal_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    skip: int = 0,
    limit: int = 100,
    api_key: str = Depends(verify_admin_api_key)
):
    """List all meals with optional filters"""
    query = {}
    
    if meal_type:
        try:
            query["meal_type"] = MealType(meal_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid meal_type: {meal_type}")
    
    if is_active is not None:
        query["is_active"] = is_active
    
    meals = await Meal.find(query).skip(skip).limit(limit).to_list()
    
    return [MealResponse(
        id=str(meal.id),
        title=meal.title,
        description=meal.description,
        meal_type=meal.meal_type.value,
        calories=meal.calories,
        protein_g=meal.protein_g,
        carbs_g=meal.carbs_g,
        fat_g=meal.fat_g,
        fiber_g=meal.fiber_g,
        ingredients=meal.ingredients,
        instructions=meal.instructions,
        prep_time_minutes=meal.prep_time_minutes,
        cook_time_minutes=meal.cook_time_minutes,
        tags=meal.tags,
        image_url=meal.image_url,
        video_url=meal.video_url,
        is_active=meal.is_active,
        created_at=meal.created_at,
        updated_at=meal.updated_at
    ) for meal in meals]


@router.get("/admin/meals/{meal_id}", response_model=MealResponse)
async def get_meal(
    meal_id: str,
    api_key: str = Depends(verify_admin_api_key)
):
    """Get a specific meal"""
    try:
        meal = await Meal.get(PydanticObjectId(meal_id))
    except Exception:
        raise HTTPException(status_code=404, detail="Meal not found")
    
    if not meal:
        raise HTTPException(status_code=404, detail="Meal not found")
    
    return MealResponse(
        id=str(meal.id),
        title=meal.title,
        description=meal.description,
        meal_type=meal.meal_type.value,
        calories=meal.calories,
        protein_g=meal.protein_g,
        carbs_g=meal.carbs_g,
        fat_g=meal.fat_g,
        fiber_g=meal.fiber_g,
        ingredients=meal.ingredients,
        instructions=meal.instructions,
        prep_time_minutes=meal.prep_time_minutes,
        cook_time_minutes=meal.cook_time_minutes,
        tags=meal.tags,
        image_url=meal.image_url,
        video_url=meal.video_url,
        is_active=meal.is_active,
        created_at=meal.created_at,
        updated_at=meal.updated_at
    )


@router.put("/admin/meals/{meal_id}", response_model=MealResponse)
async def update_meal(
    meal_id: str,
    meal_data: MealUpdate,
    api_key: str = Depends(verify_admin_api_key)
):
    """Update a meal"""
    try:
        meal = await Meal.get(PydanticObjectId(meal_id))
    except Exception:
        raise HTTPException(status_code=404, detail="Meal not found")
    
    if not meal:
        raise HTTPException(status_code=404, detail="Meal not found")
    
    # Update fields
    update_data = meal_data.dict(exclude_unset=True)
    
    if "meal_type" in update_data:
        update_data["meal_type"] = MealType(update_data["meal_type"])
    
    if "ingredients" in update_data:
        update_data["ingredients"] = [ing.dict() if hasattr(ing, 'dict') else ing for ing in update_data["ingredients"]]
    
    update_data["updated_at"] = datetime.utcnow()
    
    await meal.update({"$set": update_data})
    
    # Refresh meal
    meal = await Meal.get(PydanticObjectId(meal_id))
    
    return MealResponse(
        id=str(meal.id),
        title=meal.title,
        description=meal.description,
        meal_type=meal.meal_type.value,
        calories=meal.calories,
        protein_g=meal.protein_g,
        carbs_g=meal.carbs_g,
        fat_g=meal.fat_g,
        fiber_g=meal.fiber_g,
        ingredients=meal.ingredients,
        instructions=meal.instructions,
        prep_time_minutes=meal.prep_time_minutes,
        cook_time_minutes=meal.cook_time_minutes,
        tags=meal.tags,
        image_url=meal.image_url,
        video_url=meal.video_url,
        is_active=meal.is_active,
        created_at=meal.created_at,
        updated_at=meal.updated_at
    )


@router.delete("/admin/meals/{meal_id}", response_model=SuccessResponse)
async def delete_meal(
    meal_id: str,
    api_key: str = Depends(verify_admin_api_key)
):
    """Delete a meal (soft delete by setting is_active=False)"""
    try:
        meal = await Meal.get(PydanticObjectId(meal_id))
    except Exception:
        raise HTTPException(status_code=404, detail="Meal not found")
    
    if not meal:
        raise HTTPException(status_code=404, detail="Meal not found")
    
    meal.is_active = False
    meal.updated_at = datetime.utcnow()
    await meal.save()
    
    return {"success": True, "message": "Meal deactivated successfully"}


# Shopify Data Endpoints

@router.get("/admin/shopify/customers")
async def get_shopify_customers(
    limit: int = 50,
    api_key: str = Depends(verify_admin_api_key)
):
    """Get customers from Shopify store"""
    try:
        access_token = await shopify_client.get_access_token()
        if not access_token:
            raise HTTPException(
                status_code=400,
                detail="Shopify app not installed. Please install the app first via OAuth. Visit: /api/v1/auth/install?shop=YOUR_STORE.myshopify.com"
            )
        
        customers = await shopify_client.list_customers(limit=limit, access_token=access_token)
        return {"customers": customers, "count": len(customers)}
    except HTTPException:
        raise
    except ValueError as e:
        # Handle Shopify API errors
        error_msg = str(e)
        if "Invalid access token" in error_msg:
            raise HTTPException(
                status_code=401,
                detail=f"Access token invalid or expired. Please reinstall the app: {error_msg}"
            )
        raise HTTPException(status_code=500, detail=f"Shopify API error: {error_msg}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch customers: {str(e)}")


@router.get("/admin/shopify/orders")
async def get_shopify_orders(
    limit: int = 250,
    customer_id: Optional[int] = None,
    api_key: str = Depends(verify_admin_api_key)
):
    """Get orders from Shopify store"""
    try:
        access_token = await shopify_client.get_access_token()
        if not access_token:
            raise HTTPException(
                status_code=400,
                detail="Shopify app not installed. Please install the app first via OAuth."
            )
        
        print(f"Fetching orders with limit={limit}, customer_id={customer_id}")
        orders = await shopify_client.get_orders(
            customer_id=customer_id,
            limit=limit,
            access_token=access_token
        )
        print(f"Retrieved {len(orders)} orders from Shopify")
        return {"orders": orders, "count": len(orders)}
    except HTTPException:
        raise
    except ValueError as e:
        # Re-raise ValueError as HTTPException with proper status code
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to fetch orders: {str(e)}")


@router.get("/admin/shopify/products")
async def get_shopify_products(
    limit: int = 50,
    api_key: str = Depends(verify_admin_api_key)
):
    """Get products from Shopify store"""
    try:
        access_token = await shopify_client.get_access_token()
        if not access_token:
            raise HTTPException(
                status_code=400,
                detail="Shopify app not installed. Please install the app first via OAuth."
            )
        
        products = await shopify_client.list_products(limit=limit, access_token=access_token)
        return {"products": products, "count": len(products)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch products: {str(e)}")


@router.post("/admin/shopify/products")
async def create_shopify_product(
    product_data: Dict[str, Any],
    api_key: str = Depends(verify_admin_api_key)
):
    """Create a new product in Shopify store"""
    try:
        access_token = await shopify_client.get_access_token()
        if not access_token:
            raise HTTPException(
                status_code=400,
                detail="Shopify app not installed. Please install the app first via OAuth."
            )
        
        # Validate required fields
        if not product_data.get("title"):
            raise HTTPException(status_code=400, detail="Product title is required")
        
        # Ensure variants array exists
        if "variants" not in product_data or not product_data["variants"]:
            # Create default variant if none provided
            product_data["variants"] = [{
                "price": product_data.get("price", "0.00"),
                "inventory_management": "shopify" if product_data.get("track_inventory", False) else None,
                "inventory_quantity": product_data.get("inventory_quantity", 0) if product_data.get("track_inventory", False) else None
            }]
        
        # Create product
        product = await shopify_client.create_product(product_data, access_token=access_token)
        
        if not product:
            raise HTTPException(status_code=500, detail="Failed to create product")
        
        return {"product": product, "message": "Product created successfully"}
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create product: {str(e)}")


@router.get("/admin/shopify/shop")
async def get_shopify_shop_info(
    api_key: str = Depends(verify_admin_api_key)
):
    """Get shop information from Shopify"""
    try:
        access_token = await shopify_client.get_access_token()
        if not access_token:
            raise HTTPException(
                status_code=400,
                detail="Shopify app not installed. Please install the app first via OAuth."
            )
        
        shop_info = await shopify_client.get_shop_info(access_token=access_token)
        if not shop_info:
            raise HTTPException(status_code=404, detail="Shop information not found")
        
        return {"shop": shop_info}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch shop info: {str(e)}")


@router.get("/admin/shopify/stats")
async def get_shopify_stats(
    request: Request,
    api_key: bool = Depends(verify_admin_api_key)
):
    """Get combined stats from Shopify and local database"""
    access_token = await shopify_client.get_access_token()
    # print(F"access_token: {access_token}")
    try:
        
        
        stats = {
            "local_users": 0,
            "local_subscriptions": 0,
            "shopify_customers": 0,
            "shopify_orders": 0,
            "shopify_products": 0,
            "shop_installed": access_token is not None
        }
        
        # Get local database stats in parallel
        user_count_task = User.count()
        subscription_count_task = Subscription.count()
        
        # Get Shopify stats if app is installed (parallel calls for better performance)
        if access_token:
            customers_task = shopify_client.list_customers(limit=1, access_token=access_token)
            orders_task = shopify_client.get_orders(limit=1, access_token=access_token)
            products_task = shopify_client.list_products(limit=1, access_token=access_token)
            
            # Execute all queries in parallel
            user_count, subscription_count, customers, orders, products = await asyncio.gather(
                user_count_task,
                subscription_count_task,
                customers_task,
                orders_task,
                products_task,
                return_exceptions=True
            )
            
            stats["local_users"] = user_count if not isinstance(user_count, Exception) else 0
            stats["local_subscriptions"] = subscription_count if not isinstance(subscription_count, Exception) else 0
            
            # Note: These are just counts from first page, not total counts
            # For accurate counts, you'd need to paginate through all results
            stats["shopify_customers"] = len(customers) if not isinstance(customers, Exception) else 0
            stats["shopify_orders"] = len(orders) if not isinstance(orders, Exception) else 0
            stats["shopify_products"] = len(products) if not isinstance(products, Exception) else 0
        else:
            # Execute local database queries in parallel
            user_count, subscription_count = await asyncio.gather(
                user_count_task,
                subscription_count_task,
                return_exceptions=True
            )
            
            stats["local_users"] = user_count if not isinstance(user_count, Exception) else 0
            stats["local_subscriptions"] = subscription_count if not isinstance(subscription_count, Exception) else 0
        
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch stats: {str(e)}")


# Subscription Plan Management
@router.get("/admin/subscription-plans")
async def list_subscription_plans(
    api_key: str = Depends(verify_admin_api_key)
):
    """List all subscription plans"""
    plans = await SubscriptionPlan.find_all().sort("+display_order").to_list()
    return {
        "plans": [
            {
                "id": str(plan.id),
                "name": plan.name,
                "description": plan.description,
                "billing_frequency": plan.billing_frequency,
                "price": plan.price,
                "price_period": plan.price_period,
                "features": plan.features,
                "is_active": plan.is_active,
                "display_order": plan.display_order,
                "created_at": plan.created_at.isoformat(),
                "updated_at": plan.updated_at.isoformat()
            }
            for plan in plans
        ]
    }


@router.get("/admin/subscription-plans/{plan_id}")
async def get_subscription_plan(
    plan_id: str,
    api_key: str = Depends(verify_admin_api_key)
):
    """Get a specific subscription plan"""
    try:
        plan = await SubscriptionPlan.get(PydanticObjectId(plan_id))
    except Exception:
        raise HTTPException(status_code=404, detail="Subscription plan not found")
    
    return {
        "id": str(plan.id),
        "name": plan.name,
        "description": plan.description,
        "billing_frequency": plan.billing_frequency,
        "price": plan.price,
        "price_period": plan.price_period,
        "features": plan.features,
        "is_active": plan.is_active,
        "display_order": plan.display_order,
        "created_at": plan.created_at.isoformat(),
        "updated_at": plan.updated_at.isoformat()
    }


@router.post("/admin/subscription-plans", status_code=201)
async def create_subscription_plan(
    request: Request,
    api_key: str = Depends(verify_admin_api_key)
):
    """Create a new subscription plan"""
    body = await request.json()
    
    # Validate required fields
    required_fields = ["name", "billing_frequency", "price", "price_period"]
    for field in required_fields:
        if field not in body:
            raise HTTPException(status_code=400, detail=f"{field} is required")
    
    if body["billing_frequency"] not in ["daily", "weekly", "monthly"]:
        raise HTTPException(
            status_code=400,
            detail="billing_frequency must be 'daily', 'weekly', or 'monthly'"
        )
    
    # Check if plan with same billing_frequency already exists
    existing = await SubscriptionPlan.find_one(
        SubscriptionPlan.billing_frequency == body["billing_frequency"]
    )
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Plan with billing_frequency '{body['billing_frequency']}' already exists"
        )
    
    plan = SubscriptionPlan(
        name=body["name"],
        description=body.get("description"),
        billing_frequency=body["billing_frequency"],
        price=float(body["price"]),
        price_period=body["price_period"],
        features=body.get("features", []),
        is_active=body.get("is_active", True),
        display_order=body.get("display_order", 0)
    )
    
    await plan.insert()
    
    return {
        "id": str(plan.id),
        "name": plan.name,
        "description": plan.description,
        "billing_frequency": plan.billing_frequency,
        "price": plan.price,
        "price_period": plan.price_period,
        "features": plan.features,
        "is_active": plan.is_active,
        "display_order": plan.display_order,
        "message": "Subscription plan created successfully"
    }


@router.put("/admin/subscription-plans/{plan_id}")
async def update_subscription_plan(
    plan_id: str,
    request: Request,
    api_key: str = Depends(verify_admin_api_key)
):
    """Update a subscription plan"""
    try:
        plan = await SubscriptionPlan.get(PydanticObjectId(plan_id))
    except Exception:
        raise HTTPException(status_code=404, detail="Subscription plan not found")
    
    body = await request.json()
    
    # Update fields
    if "name" in body:
        plan.name = body["name"]
    if "description" in body:
        plan.description = body["description"]
    if "billing_frequency" in body:
        if body["billing_frequency"] not in ["daily", "weekly", "monthly"]:
            raise HTTPException(
                status_code=400,
                detail="billing_frequency must be 'daily', 'weekly', or 'monthly'"
            )
        # Check if another plan with this frequency exists
        existing = await SubscriptionPlan.find_one(
            SubscriptionPlan.billing_frequency == body["billing_frequency"],
            SubscriptionPlan.id != plan.id
        )
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Another plan with billing_frequency '{body['billing_frequency']}' already exists"
            )
        plan.billing_frequency = body["billing_frequency"]
    if "price" in body:
        plan.price = float(body["price"])
    if "price_period" in body:
        plan.price_period = body["price_period"]
    if "features" in body:
        plan.features = body["features"]
    if "is_active" in body:
        plan.is_active = bool(body["is_active"])
    if "display_order" in body:
        plan.display_order = int(body["display_order"])
    
    plan.updated_at = datetime.utcnow()
    await plan.save()
    
    return {
        "id": str(plan.id),
        "name": plan.name,
        "description": plan.description,
        "billing_frequency": plan.billing_frequency,
        "price": plan.price,
        "price_period": plan.price_period,
        "features": plan.features,
        "is_active": plan.is_active,
        "display_order": plan.display_order,
        "message": "Subscription plan updated successfully"
    }


@router.delete("/admin/subscription-plans/{plan_id}")
async def delete_subscription_plan(
    plan_id: str,
    api_key: str = Depends(verify_admin_api_key)
):
    """Delete a subscription plan"""
    try:
        plan = await SubscriptionPlan.get(PydanticObjectId(plan_id))
    except Exception:
        raise HTTPException(status_code=404, detail="Subscription plan not found")
    
    await plan.delete()
    
    return {
        "message": "Subscription plan deleted successfully",
        "id": str(plan.id)
    }


@router.get("/admin/users")
async def list_users(
    skip: int = 0,
    limit: int = 100,
    api_key: str = Depends(verify_admin_api_key)
):
    """List all users from MongoDB with their subscription information"""
    # Fetch users
    users = await User.find_all().skip(skip).limit(limit).to_list()
    
    if not users:
        return {
            "users": [],
            "total": 0,
            "skip": skip,
            "limit": limit
        }
    
    # Get all user IDs
    user_ids = [str(user.id) for user in users]
    
    # Batch fetch all subscriptions and preferences in parallel using $in operator
    subscriptions_query = Subscription.find(In(Subscription.user_id, user_ids))
    preferences_query = UserPreference.find(In(UserPreference.user_id, user_ids))
    
    subscriptions_list, preferences_list = await asyncio.gather(
        subscriptions_query.to_list(),
        preferences_query.to_list()
    )
    
    # Create lookup dictionaries for O(1) access
    subscriptions_map = {sub.user_id: sub for sub in subscriptions_list}
    preferences_map = {pref.user_id: pref for pref in preferences_list}
    
    # Build response with batch-loaded data
    users_with_subscriptions = []
    for user in users:
        user_id_str = str(user.id)
        subscription = subscriptions_map.get(user_id_str)
        preferences = preferences_map.get(user_id_str)
        
        user_data = {
            "id": user_id_str,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "phone": user.phone,
            "shopify_customer_id": user.shopify_customer_id,
            "is_active": user.is_active,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "updated_at": user.updated_at.isoformat() if user.updated_at else None,
            "subscription": None,
            "onboarding_completed": preferences.onboarding_completed if preferences and hasattr(preferences, 'onboarding_completed') else False,
        }
        
        if subscription:
            user_data["subscription"] = {
                "id": str(subscription.id),
                "status": subscription.status.value,
                "billing_frequency": subscription.billing_frequency,
                "next_charge_date": subscription.next_charge_date.isoformat() if subscription.next_charge_date else None,
                "last_charge_date": subscription.last_charge_date.isoformat() if subscription.last_charge_date else None,
                "started_at": subscription.started_at.isoformat() if subscription.started_at else None,
            }
        
        users_with_subscriptions.append(user_data)
    
    return {
        "users": users_with_subscriptions,
        "total": len(users_with_subscriptions),
        "skip": skip,
        "limit": limit
    }


@router.get("/admin/users/{user_id}/preferences")
async def get_user_preferences_admin(
    user_id: str,
    api_key: str = Depends(verify_admin_api_key)
):
    """Get user preferences for admin panel"""
    # Get user preferences
    preferences = await UserPreference.find_one(UserPreference.user_id == user_id)
    
    if not preferences:
        raise HTTPException(
            status_code=404,
            detail="User preferences not found. User may not have completed onboarding."
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


@router.post("/admin/users/{user_id}/generate-ai-meal-suggestions")
async def generate_ai_meal_suggestions_for_user(
    user_id: str,
    request: Request,
    plan_type: Optional[str] = None,
    api_key: str = Depends(verify_admin_api_key)
):
    """Generate AI meal suggestions for a specific user and save to database"""
    try:
        # Get user preferences
        preferences = await get_user_preferences(user_id)
        
        if not preferences:
            raise HTTPException(
                status_code=404,
                detail="User preferences not found. User must complete onboarding first."
            )
        
        # Get plan_type from query params (default to "daily")
        if not plan_type:
            plan_type = request.query_params.get("plan_type", "daily")
        
        if plan_type not in ["daily", "weekly"]:
            raise HTTPException(
                status_code=400,
                detail="plan_type must be 'daily' or 'weekly'"
            )
        
        # Generate meal suggestions using OpenAI
        meal_plan = await generate_meal_suggestions(preferences, plan_type)
        
        # Create snapshot of user preferences
        preferences_snapshot = {
            "goal": preferences.goal.value if preferences.goal else None,
            "activity_level": preferences.activity_level.value if preferences.activity_level else None,
            "daily_calorie_target": preferences.daily_calorie_target,
            "dietary_preferences": preferences.dietary_preferences or [],
            "allergies": preferences.allergies or [],
            "age": preferences.age,
            "height_cm": preferences.height_cm,
            "weight_kg": preferences.weight_kg,
        }
        
        # Save to database
        ai_suggestion = AIMealSuggestion(
            user_id=user_id,
            plan_type=plan_type,
            meal_plan=meal_plan,
            user_preferences_snapshot=preferences_snapshot
        )
        await ai_suggestion.insert()
        
        return {
            "success": True,
            "message": f"AI meal suggestions generated and saved successfully",
            "suggestion_id": str(ai_suggestion.id),
            "plan_type": plan_type,
            "user_id": user_id,
            "meal_plan": meal_plan,
            "created_at": ai_suggestion.created_at.isoformat()
        }
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate meal suggestions: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating AI meal suggestions: {str(e)}"
        )
