"""
Subscription access control middleware
Enforces subscription status checks for protected endpoints
Supports both JWT authentication and Shopify authentication
"""
from fastapi import HTTPException, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from models.database import User, Subscription, SubscriptionStatus
from apis.user_api import verify_shopify_request, get_current_user_from_token

security = HTTPBearer(auto_error=False)


async def get_current_user(request: Request, credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> User:
    """
    Get current user from JWT token or Shopify request
    Tries JWT first, then falls back to Shopify
    """
    # Try JWT authentication first
    if credentials:
        try:
            current_user_data = await get_current_user_from_token(credentials)
            user_id = current_user_data["user_id"]
            user = await User.get(user_id)
            if user:
                return user
        except:
            pass  # JWT failed, try Shopify
    
    # Fall back to Shopify authentication
    try:
        shopify_data = await verify_shopify_request(request)
        shopify_customer_id = shopify_data["shopify_customer_id"]
        
        user = await User.find_one(User.shopify_customer_id == shopify_customer_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return user
    except HTTPException:
        raise HTTPException(status_code=401, detail="Authentication required. Please login or provide valid credentials.")


async def get_user_subscription(user: User = Depends(get_current_user)) -> Optional[Subscription]:
    """
    Get active subscription for current user
    """
    subscription = await Subscription.find_one(
        Subscription.user_id == str(user.id),
        Subscription.status == SubscriptionStatus.ACTIVE
    )
    return subscription


async def require_active_subscription(
    user: User = Depends(get_current_user),
    subscription: Optional[Subscription] = Depends(get_user_subscription)
) -> User:
    """
    Dependency that requires an active subscription
    Blocks access if subscription is not ACTIVE
    For now, allows authenticated users even without subscription (can be made strict later)
    """
    # For now, allow authenticated users to access meals
    # Subscription requirement can be enforced later when OpenAI integration is added
    return user
    
    # Uncomment below to enforce strict subscription requirement:
    # if not subscription:
    #     # Check if user has any subscription (even if not active)
    #     any_subscription = await Subscription.find_one(
    #         Subscription.user_id == str(user.id)
    #     )
    #     
    #     if any_subscription:
    #         status = any_subscription.status.value
    #         raise HTTPException(
    #             status_code=403,
    #             detail=f"Subscription access required. Current status: {status}"
    #         )
    #     else:
    #         raise HTTPException(
    #             status_code=403,
    #             detail="Active subscription required to access this resource"
    #         )
    # 
    # return user

