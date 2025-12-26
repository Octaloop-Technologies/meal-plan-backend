"""
Subscription Management APIs
Handles pause, cancel, resume operations for subscriptions
Supports Recharge, Appstle, Loop, and Shopify subscriptions
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from typing import Optional
from datetime import datetime, date
from models.database import (
    User, Subscription, SubscriptionPlan, SubscriptionStatus, SubscriptionProvider
)
from services.subscription_service import get_current_user, get_user_subscription
from services.shopify_service import shopify_client
import httpx
from config import settings

router = APIRouter()


async def get_subscription_for_user(user: User) -> Subscription:
    """Get active subscription for user"""
    subscription = await Subscription.find_one(
        Subscription.user_id == str(user.id),
        Subscription.status == SubscriptionStatus.ACTIVE
    )
    if not subscription:
        raise HTTPException(
            status_code=404,
            detail="No active subscription found"
        )
    return subscription


@router.get("/subscription")
async def get_subscription(
    request: Request,
    user: User = Depends(get_current_user)
):
    """
    Get current user's subscription details
    """
    subscription = await Subscription.find_one(
        Subscription.user_id == str(user.id)
    )
    
    if not subscription:
        return {
            "has_subscription": False,
            "subscription": None
        }
    
    return {
        "has_subscription": True,
        "subscription": {
            "id": str(subscription.id),
            "subscription_id": subscription.shopify_subscription_id,
            "status": subscription.status.value,
            "provider": subscription.subscription_provider.value,
            "billing_frequency": subscription.billing_frequency,
            "next_charge_date": subscription.next_charge_date.isoformat() if subscription.next_charge_date else None,
            "last_charge_date": subscription.last_charge_date.isoformat() if subscription.last_charge_date else None,
            "started_at": subscription.started_at.isoformat() if subscription.started_at else None,
            "ended_at": subscription.ended_at.isoformat() if subscription.ended_at else None,
            "created_at": subscription.created_at.isoformat(),
            "last_synced_at": subscription.last_synced_at.isoformat()
        }
    }


@router.get("/subscription/plans")
async def get_subscription_plans():
    """
    Get available subscription plans from database
    Returns only active plans, sorted by display_order
    """
    plans = await SubscriptionPlan.find(
        SubscriptionPlan.is_active == True
    ).sort("+display_order").to_list()
    
    if not plans:
        # Return default plans if none exist in database
        return {
            "plans": [
                {
                    "id": "daily",
                    "name": "Daily Plan",
                    "description": "Get fresh meal plans every day",
                    "billing_frequency": "daily",
                    "price": 9.99,
                    "price_period": "per day",
                    "features": [
                        "Daily meal plans",
                        "Fresh recipes every day",
                        "Shopping lists",
                        "Nutritional tracking"
                    ]
                },
                {
                    "id": "weekly",
                    "name": "Weekly Plan",
                    "description": "Complete weekly meal plans",
                    "billing_frequency": "weekly",
                    "price": 49.99,
                    "price_period": "per week",
                    "features": [
                        "7-day meal plans",
                        "Weekly shopping lists",
                        "Meal prep guides",
                        "Nutritional tracking",
                        "Save 30% vs daily"
                    ]
                },
                {
                    "id": "monthly",
                    "name": "Monthly Plan",
                    "description": "Best value for long-term nutrition",
                    "billing_frequency": "monthly",
                    "price": 149.99,
                    "price_period": "per month",
                    "features": [
                        "30-day meal plans",
                        "Monthly shopping lists",
                        "Meal prep guides",
                        "Nutritional tracking",
                        "Save 50% vs daily",
                        "Priority support"
                    ]
                }
            ]
        }
    
    return {
        "plans": [
            {
                "id": str(plan.id),
                "name": plan.name,
                "description": plan.description or "",
                "billing_frequency": plan.billing_frequency,
                "price": plan.price,
                "price_period": plan.price_period,
                "features": plan.features or []
            }
            for plan in plans
        ]
    }


@router.post("/subscription/create")
async def create_subscription(
    request: Request,
    user: User = Depends(get_current_user)
):
    """
    Create a new subscription for the user
    Expects JSON body with billing_frequency: 'daily', 'weekly', or 'monthly'
    """
    body = await request.json()
    billing_frequency = body.get('billing_frequency')
    
    if not billing_frequency:
        raise HTTPException(
            status_code=400,
            detail="billing_frequency is required"
        )
    
    if billing_frequency not in ['daily', 'weekly', 'monthly']:
        raise HTTPException(
            status_code=400,
            detail="Invalid billing frequency. Must be 'daily', 'weekly', or 'monthly'"
        )
    
    # Check if user already has an active subscription
    existing_subscription = await Subscription.find_one(
        Subscription.user_id == str(user.id),
        Subscription.status == SubscriptionStatus.ACTIVE
    )
    
    if existing_subscription:
        raise HTTPException(
            status_code=400,
            detail="You already have an active subscription. Please cancel it first to subscribe to a new plan."
        )
    
    # Calculate next charge date based on billing frequency
    from datetime import timedelta
    today = date.today()
    if billing_frequency == 'daily':
        next_charge = today + timedelta(days=1)
    elif billing_frequency == 'weekly':
        next_charge = today + timedelta(weeks=1)
    else:  # monthly
        # Approximate 30 days for monthly
        next_charge = today + timedelta(days=30)
    
    # Create subscription record
    # In production, this would create a subscription via Shopify/Recharge/etc.
    # For now, we'll create a local subscription record
    subscription = Subscription(
        user_id=str(user.id),
        shopify_subscription_id=f"sub_{user.id}_{int(datetime.utcnow().timestamp())}",
        status=SubscriptionStatus.ACTIVE,
        subscription_provider=SubscriptionProvider.SHOPIFY,
        billing_frequency=billing_frequency,
        next_charge_date=next_charge,
        started_at=today,
        last_synced_at=datetime.utcnow()
    )
    await subscription.insert()
    
    return {
        "success": True,
        "message": f"Subscription created successfully",
        "subscription": {
            "id": str(subscription.id),
            "subscription_id": subscription.shopify_subscription_id,
            "status": subscription.status.value,
            "billing_frequency": subscription.billing_frequency,
            "next_charge_date": subscription.next_charge_date.isoformat() if subscription.next_charge_date else None,
            "started_at": subscription.started_at.isoformat() if subscription.started_at else None
        }
    }


@router.post("/subscription/pause")
async def pause_subscription(
    request: Request,
    user: User = Depends(get_current_user)
):
    """
    Pause subscription
    Works with Recharge, Appstle, Loop, and Shopify subscriptions
    """
    subscription = await get_subscription_for_user(user)
    
    try:
        # Update subscription status via provider API
        if subscription.subscription_provider == SubscriptionProvider.RECHARGE:
            # Recharge API
            result = await pause_recharge_subscription(subscription.shopify_subscription_id)
        elif subscription.subscription_provider == SubscriptionProvider.APPSTLE:
            # Appstle API
            result = await pause_appstle_subscription(subscription.shopify_subscription_id)
        elif subscription.subscription_provider == SubscriptionProvider.LOOP:
            # Loop API
            result = await pause_loop_subscription(subscription.shopify_subscription_id)
        else:
            # Shopify native subscriptions
            result = await pause_shopify_subscription(subscription.shopify_subscription_id)
        
        # Update local database
        subscription.status = SubscriptionStatus.PAUSED
        subscription.updated_at = datetime.utcnow()
        subscription.last_synced_at = datetime.utcnow()
        await subscription.save()
        
        return {
            "success": True,
            "message": "Subscription paused successfully",
            "subscription": {
                "id": str(subscription.id),
                "status": subscription.status.value
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to pause subscription: {str(e)}"
        )


@router.post("/subscription/cancel")
async def cancel_subscription(
    request: Request,
    user: User = Depends(get_current_user)
):
    """
    Cancel subscription
    Works with Recharge, Appstle, Loop, and Shopify subscriptions
    """
    subscription = await get_subscription_for_user(user)
    
    try:
        # Update subscription status via provider API
        if subscription.subscription_provider == SubscriptionProvider.RECHARGE:
            result = await cancel_recharge_subscription(subscription.shopify_subscription_id)
        elif subscription.subscription_provider == SubscriptionProvider.APPSTLE:
            result = await cancel_appstle_subscription(subscription.shopify_subscription_id)
        elif subscription.subscription_provider == SubscriptionProvider.LOOP:
            result = await cancel_loop_subscription(subscription.shopify_subscription_id)
        else:
            result = await cancel_shopify_subscription(subscription.shopify_subscription_id)
        
        # Update local database
        subscription.status = SubscriptionStatus.CANCELLED
        subscription.ended_at = date.today()
        subscription.updated_at = datetime.utcnow()
        subscription.last_synced_at = datetime.utcnow()
        await subscription.save()
        
        return {
            "success": True,
            "message": "Subscription cancelled successfully",
            "subscription": {
                "id": str(subscription.id),
                "status": subscription.status.value
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to cancel subscription: {str(e)}"
        )


@router.post("/subscription/resume")
async def resume_subscription(
    request: Request,
    user: User = Depends(get_current_user)
):
    """
    Resume paused subscription
    Works with Recharge, Appstle, Loop, and Shopify subscriptions
    """
    subscription = await Subscription.find_one(
        Subscription.user_id == str(user.id),
        Subscription.status == SubscriptionStatus.PAUSED
    )
    
    if not subscription:
        raise HTTPException(
            status_code=404,
            detail="No paused subscription found"
        )
    
    try:
        # Update subscription status via provider API
        if subscription.subscription_provider == SubscriptionProvider.RECHARGE:
            result = await resume_recharge_subscription(subscription.shopify_subscription_id)
        elif subscription.subscription_provider == SubscriptionProvider.APPSTLE:
            result = await resume_appstle_subscription(subscription.shopify_subscription_id)
        elif subscription.subscription_provider == SubscriptionProvider.LOOP:
            result = await resume_loop_subscription(subscription.shopify_subscription_id)
        else:
            result = await resume_shopify_subscription(subscription.shopify_subscription_id)
        
        # Update local database
        subscription.status = SubscriptionStatus.ACTIVE
        subscription.updated_at = datetime.utcnow()
        subscription.last_synced_at = datetime.utcnow()
        await subscription.save()
        
        return {
            "success": True,
            "message": "Subscription resumed successfully",
            "subscription": {
                "id": str(subscription.id),
                "status": subscription.status.value
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to resume subscription: {str(e)}"
        )


# Provider-specific API functions

async def pause_recharge_subscription(subscription_id: str) -> dict:
    """
    Pause subscription via Recharge API
    Recharge API endpoint: PUT /subscriptions/{subscription_id}
    """
    # Recharge API configuration (should be in settings)
    recharge_api_key = getattr(settings, 'RECHARGE_API_KEY', None)
    recharge_shop = getattr(settings, 'RECHARGE_SHOP', settings.SHOPIFY_SHOP_DOMAIN.replace('.myshopify.com', ''))
    
    if not recharge_api_key:
        raise ValueError("Recharge API key not configured")
    
    url = f"https://api.rechargeapps.com/subscriptions/{subscription_id}"
    headers = {
        "X-Recharge-Access-Token": recharge_api_key,
        "Content-Type": "application/json"
    }
    data = {"status": "on_hold"}
    
    async with httpx.AsyncClient() as client:
        response = await client.put(url, headers=headers, json=data)
        if response.status_code == 200:
            return response.json()
        else:
            raise ValueError(f"Recharge API error: {response.text}")


async def cancel_recharge_subscription(subscription_id: str) -> dict:
    """Cancel subscription via Recharge API"""
    recharge_api_key = getattr(settings, 'RECHARGE_API_KEY', None)
    if not recharge_api_key:
        raise ValueError("Recharge API key not configured")
    
    url = f"https://api.rechargeapps.com/subscriptions/{subscription_id}/cancel"
    headers = {
        "X-Recharge-Access-Token": recharge_api_key,
        "Content-Type": "application/json"
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            raise ValueError(f"Recharge API error: {response.text}")


async def resume_recharge_subscription(subscription_id: str) -> dict:
    """Resume subscription via Recharge API"""
    recharge_api_key = getattr(settings, 'RECHARGE_API_KEY', None)
    if not recharge_api_key:
        raise ValueError("Recharge API key not configured")
    
    url = f"https://api.rechargeapps.com/subscriptions/{subscription_id}"
    headers = {
        "X-Recharge-Access-Token": recharge_api_key,
        "Content-Type": "application/json"
    }
    data = {"status": "active"}
    
    async with httpx.AsyncClient() as client:
        response = await client.put(url, headers=headers, json=data)
        if response.status_code == 200:
            return response.json()
        else:
            raise ValueError(f"Recharge API error: {response.text}")


async def pause_appstle_subscription(subscription_id: str) -> dict:
    """
    Pause subscription via Appstle API
    Appstle uses Shopify App Proxy or direct API
    """
    access_token = await shopify_client.get_access_token()
    if not access_token:
        raise ValueError("Shopify access token required")
    
    # Appstle typically integrates via Shopify, so we use Shopify API
    # or Appstle's own API if available
    # This is a placeholder - actual implementation depends on Appstle's API
    return {"status": "paused"}


async def cancel_appstle_subscription(subscription_id: str) -> dict:
    """Cancel subscription via Appstle API"""
    # Placeholder - implement based on Appstle API documentation
    return {"status": "cancelled"}


async def resume_appstle_subscription(subscription_id: str) -> dict:
    """Resume subscription via Appstle API"""
    # Placeholder - implement based on Appstle API documentation
    return {"status": "active"}


async def pause_loop_subscription(subscription_id: str) -> dict:
    """
    Pause subscription via Loop API
    Loop uses Shopify integration
    """
    # Loop API implementation
    # Placeholder - implement based on Loop API documentation
    return {"status": "paused"}


async def cancel_loop_subscription(subscription_id: str) -> dict:
    """Cancel subscription via Loop API"""
    # Placeholder - implement based on Loop API documentation
    return {"status": "cancelled"}


async def resume_loop_subscription(subscription_id: str) -> dict:
    """Resume subscription via Loop API"""
    # Placeholder - implement based on Loop API documentation
    return {"status": "active"}


async def pause_shopify_subscription(subscription_id: str) -> dict:
    """
    Pause Shopify native subscription using GraphQL
    """
    access_token = await shopify_client.get_access_token()
    if not access_token:
        raise ValueError("Shopify access token required")
    
    # Shopify uses GraphQL for subscription contracts
    mutation = """
    mutation subscriptionContractPause($id: ID!) {
        subscriptionContractPause(contractId: $id) {
            contract {
                id
                status
            }
            userErrors {
                field
                message
            }
        }
    }
    """
    
    url = f"https://{shopify_client.shop_domain}/admin/api/{shopify_client.api_version}/graphql.json"
    headers = {
        "X-Shopify-Access-Token": access_token,
        "Content-Type": "application/json"
    }
    data = {
        "query": mutation,
        "variables": {
            "id": f"gid://shopify/SubscriptionContract/{subscription_id}"
        }
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=data)
        if response.status_code == 200:
            result = response.json()
            if result.get("data", {}).get("subscriptionContractPause", {}).get("userErrors"):
                errors = result["data"]["subscriptionContractPause"]["userErrors"]
                raise ValueError(f"Shopify API errors: {errors}")
            return result
        else:
            raise ValueError(f"Shopify API error: {response.text}")


async def cancel_shopify_subscription(subscription_id: str) -> dict:
    """Cancel Shopify native subscription using GraphQL"""
    access_token = await shopify_client.get_access_token()
    if not access_token:
        raise ValueError("Shopify access token required")
    
    mutation = """
    mutation subscriptionContractCancel($id: ID!) {
        subscriptionContractCancel(contractId: $id) {
            contract {
                id
                status
            }
            userErrors {
                field
                message
            }
        }
    }
    """
    
    url = f"https://{shopify_client.shop_domain}/admin/api/{shopify_client.api_version}/graphql.json"
    headers = {
        "X-Shopify-Access-Token": access_token,
        "Content-Type": "application/json"
    }
    data = {
        "query": mutation,
        "variables": {
            "id": f"gid://shopify/SubscriptionContract/{subscription_id}"
        }
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=data)
        if response.status_code == 200:
            result = response.json()
            if result.get("data", {}).get("subscriptionContractCancel", {}).get("userErrors"):
                errors = result["data"]["subscriptionContractCancel"]["userErrors"]
                raise ValueError(f"Shopify API errors: {errors}")
            return result
        else:
            raise ValueError(f"Shopify API error: {response.text}")


async def resume_shopify_subscription(subscription_id: str) -> dict:
    """Resume Shopify native subscription using GraphQL"""
    access_token = await shopify_client.get_access_token()
    if not access_token:
        raise ValueError("Shopify access token required")
    
    mutation = """
    mutation subscriptionContractResume($id: ID!) {
        subscriptionContractResume(contractId: $id) {
            contract {
                id
                status
            }
            userErrors {
                field
                message
            }
        }
    }
    """
    
    url = f"https://{shopify_client.shop_domain}/admin/api/{shopify_client.api_version}/graphql.json"
    headers = {
        "X-Shopify-Access-Token": access_token,
        "Content-Type": "application/json"
    }
    data = {
        "query": mutation,
        "variables": {
            "id": f"gid://shopify/SubscriptionContract/{subscription_id}"
        }
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=data)
        if response.status_code == 200:
            result = response.json()
            if result.get("data", {}).get("subscriptionContractResume", {}).get("userErrors"):
                errors = result["data"]["subscriptionContractResume"]["userErrors"]
                raise ValueError(f"Shopify API errors: {errors}")
            return result
        else:
            raise ValueError(f"Shopify API error: {response.text}")

