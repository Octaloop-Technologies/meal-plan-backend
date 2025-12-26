"""
Shopify Webhooks Handler (MongoDB)
Handles customer and subscription events from Shopify
"""
from fastapi import APIRouter, Request, HTTPException, Header
from beanie import PydanticObjectId
from models.database import User, Subscription, SubscriptionStatus, SubscriptionProvider
from config import settings
import hmac
import hashlib
from datetime import datetime

router = APIRouter()


def verify_webhook_signature(
    data: bytes,
    signature: str,
    secret: str
) -> bool:
    """
    Verify Shopify webhook signature
    """
    expected_signature = hmac.new(
        secret.encode('utf-8'),
        data,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(signature, expected_signature)


@router.post("/webhooks/customer/create")
async def handle_customer_create(
    request: Request,
    x_shopify_shop_domain: str = Header(None, alias="X-Shopify-Shop-Domain"),
    x_shopify_hmac_sha256: str = Header(None, alias="X-Shopify-Hmac-Sha256")
):
    """
    Handle customer creation webhook
    Creates user record in database when customer is created in Shopify
    """
    # Verify webhook signature
    body = await request.body()
    
    if not verify_webhook_signature(
        body,
        x_shopify_hmac_sha256 or "",
        settings.SHOPIFY_API_SECRET
    ):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    
    # Parse webhook data
    data = await request.json()
    customer = data.get("customer", {})
    
    customer_id = customer.get("id")
    email = customer.get("email")
    first_name = customer.get("first_name")
    last_name = customer.get("last_name")
    phone = customer.get("phone")
    
    if not customer_id or not email:
        raise HTTPException(status_code=400, detail="Invalid customer data")
    
    # Check if user already exists
    existing_user = await User.find_one(
        User.shopify_customer_id == customer_id
    )
    
    if not existing_user:
        # Create new user
        user = User(
            shopify_customer_id=customer_id,
            email=email,
            first_name=first_name,
            last_name=last_name,
            phone=phone
        )
        await user.insert()
        return {"status": "success", "message": "User created", "user_id": str(user.id)}
    
    return {"status": "success", "message": "User already exists", "user_id": str(existing_user.id)}


@router.post("/webhooks/customer/update")
async def handle_customer_update(
    request: Request,
    x_shopify_hmac_sha256: str = Header(None, alias="X-Shopify-Hmac-Sha256")
):
    """
    Handle customer update webhook
    Updates user record when customer data changes in Shopify
    """
    body = await request.body()
    
    if not verify_webhook_signature(
        body,
        x_shopify_hmac_sha256 or "",
        settings.SHOPIFY_API_SECRET
    ):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    
    data = await request.json()
    customer = data.get("customer", {})
    
    customer_id = customer.get("id")
    
    if not customer_id:
        raise HTTPException(status_code=400, detail="Invalid customer data")
    
    # Update user
    user = await User.find_one(
        User.shopify_customer_id == customer_id
    )
    
    if user:
        user.email = customer.get("email", user.email)
        user.first_name = customer.get("first_name", user.first_name)
        user.last_name = customer.get("last_name", user.last_name)
        user.phone = customer.get("phone", user.phone)
        user.updated_at = datetime.utcnow()
        await user.save()
        return {"status": "success", "message": "User updated"}
    
    return {"status": "success", "message": "User not found"}


@router.post("/webhooks/subscription/updated")
async def handle_subscription_updated(
    request: Request,
    x_shopify_hmac_sha256: str = Header(None, alias="X-Shopify-Hmac-Sha256")
):
    """
    Handle subscription update webhook
    Syncs subscription status from Shopify/Recharge/Appstle/Loop
    """
    body = await request.body()
    
    if not verify_webhook_signature(
        body,
        x_shopify_hmac_sha256 or "",
        settings.SHOPIFY_API_SECRET
    ):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    
    data = await request.json()
    
    # Extract subscription data (format depends on provider)
    subscription_id = data.get("subscription_id") or data.get("id")
    customer_id = data.get("customer_id")
    status = data.get("status", "active")
    next_charge_date = data.get("next_charge_scheduled_at") or data.get("next_charge_date")
    provider = data.get("provider", "shopify")
    
    if not subscription_id or not customer_id:
        raise HTTPException(status_code=400, detail="Invalid subscription data")
    
    # Get user
    user = await User.find_one(
        User.shopify_customer_id == customer_id
    )
    
    if not user:
        return {"status": "user_not_found"}
    
    # Convert status to enum
    try:
        subscription_status = SubscriptionStatus(status.lower())
    except ValueError:
        subscription_status = SubscriptionStatus.ACTIVE
    
    # Convert provider to enum
    try:
        subscription_provider = SubscriptionProvider(provider.lower())
    except ValueError:
        subscription_provider = SubscriptionProvider.SHOPIFY
    
    # Parse dates
    next_charge = None
    last_charge = None
    started = None
    ended = None
    billing_frequency = data.get("billing_frequency") or data.get("frequency")  # weekly or monthly
    
    if next_charge_date:
        try:
            if isinstance(next_charge_date, str):
                next_charge = datetime.fromisoformat(
                    next_charge_date.replace('Z', '+00:00')
                ).date()
            else:
                next_charge = next_charge_date
        except Exception:
            pass
    
    last_charge_date = data.get("last_charge_date") or data.get("last_charge_scheduled_at")
    if last_charge_date:
        try:
            if isinstance(last_charge_date, str):
                last_charge = datetime.fromisoformat(
                    last_charge_date.replace('Z', '+00:00')
                ).date()
            else:
                last_charge = last_charge_date
        except Exception:
            pass
    
    started_at = data.get("started_at") or data.get("created_at")
    if started_at:
        try:
            if isinstance(started_at, str):
                started = datetime.fromisoformat(
                    started_at.replace('Z', '+00:00')
                ).date()
            else:
                started = started_at
        except Exception:
            pass
    
    ended_at = data.get("ended_at") or data.get("cancelled_at")
    if ended_at:
        try:
            if isinstance(ended_at, str):
                ended = datetime.fromisoformat(
                    ended_at.replace('Z', '+00:00')
                ).date()
            else:
                ended = ended_at
        except Exception:
            pass
    
    # Update or create subscription
    subscription = await Subscription.find_one(
        Subscription.shopify_subscription_id == str(subscription_id)
    )
    
    if subscription:
        subscription.status = subscription_status
        if next_charge:
            subscription.next_charge_date = next_charge
        if last_charge:
            subscription.last_charge_date = last_charge
        if started:
            subscription.started_at = started
        if ended:
            subscription.ended_at = ended
        if billing_frequency:
            subscription.billing_frequency = billing_frequency.lower()
        subscription.updated_at = datetime.utcnow()
        subscription.last_synced_at = datetime.utcnow()
        await subscription.save()
    else:
        subscription = Subscription(
            user_id=str(user.id),
            shopify_subscription_id=str(subscription_id),
            status=subscription_status,
            subscription_provider=subscription_provider,
            billing_frequency=billing_frequency.lower() if billing_frequency else None,
            next_charge_date=next_charge,
            last_charge_date=last_charge,
            started_at=started,
            ended_at=ended
        )
        await subscription.insert()
    
    return {"status": "success", "message": "Subscription updated"}


@router.post("/webhooks/subscription/created")
async def handle_subscription_created(
    request: Request,
    x_shopify_hmac_sha256: str = Header(None, alias="X-Shopify-Hmac-Sha256")
):
    """
    Handle subscription creation webhook
    Creates subscription record when subscription is created in Shopify/Recharge/Appstle/Loop
    """
    body = await request.body()
    
    if not verify_webhook_signature(
        body,
        x_shopify_hmac_sha256 or "",
        settings.SHOPIFY_API_SECRET
    ):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    
    data = await request.json()
    
    # Extract subscription data (format depends on provider)
    subscription_id = data.get("subscription_id") or data.get("id")
    customer_id = data.get("customer_id")
    status = data.get("status", "active")
    next_charge_date = data.get("next_charge_scheduled_at") or data.get("next_charge_date")
    provider = data.get("provider", "shopify")
    
    if not subscription_id or not customer_id:
        raise HTTPException(status_code=400, detail="Invalid subscription data")
    
    # Get user
    user = await User.find_one(
        User.shopify_customer_id == customer_id
    )
    
    if not user:
        return {"status": "user_not_found"}
    
    # Convert status to enum
    try:
        subscription_status = SubscriptionStatus(status.lower())
    except ValueError:
        subscription_status = SubscriptionStatus.ACTIVE
    
    # Convert provider to enum
    try:
        subscription_provider = SubscriptionProvider(provider.lower())
    except ValueError:
        subscription_provider = SubscriptionProvider.SHOPIFY
    
    # Parse dates and billing frequency
    billing_frequency = data.get("billing_frequency") or data.get("frequency")
    next_charge = None
    last_charge = None
    started = None
    
    if next_charge_date:
        try:
            if isinstance(next_charge_date, str):
                next_charge = datetime.fromisoformat(
                    next_charge_date.replace('Z', '+00:00')
                ).date()
            else:
                next_charge = next_charge_date
        except Exception:
            pass
    
    last_charge_date = data.get("last_charge_date")
    if last_charge_date:
        try:
            if isinstance(last_charge_date, str):
                last_charge = datetime.fromisoformat(
                    last_charge_date.replace('Z', '+00:00')
                ).date()
            else:
                last_charge = last_charge_date
        except Exception:
            pass
    
    started_at = data.get("started_at") or data.get("created_at")
    if started_at:
        try:
            if isinstance(started_at, str):
                started = datetime.fromisoformat(
                    started_at.replace('Z', '+00:00')
                ).date()
            else:
                started = started_at
        except Exception:
            pass
    
    # Create subscription
    subscription = await Subscription.find_one(
        Subscription.shopify_subscription_id == str(subscription_id)
    )
    
    if not subscription:
        subscription = Subscription(
            user_id=str(user.id),
            shopify_subscription_id=str(subscription_id),
            status=subscription_status,
            subscription_provider=subscription_provider,
            billing_frequency=billing_frequency.lower() if billing_frequency else None,
            next_charge_date=next_charge,
            last_charge_date=last_charge,
            started_at=started
        )
        await subscription.insert()
    else:
        subscription.status = subscription_status
        if next_charge:
            subscription.next_charge_date = next_charge
        if last_charge:
            subscription.last_charge_date = last_charge
        if started:
            subscription.started_at = started
        if billing_frequency:
            subscription.billing_frequency = billing_frequency.lower()
        subscription.last_synced_at = datetime.utcnow()
        await subscription.save()
    
    return {"status": "success", "message": "Subscription created"}


@router.post("/webhooks/subscription/activated")
async def handle_subscription_activated(
    request: Request,
    x_shopify_hmac_sha256: str = Header(None, alias="X-Shopify-Hmac-Sha256")
):
    """
    Handle subscription activation webhook
    Updates subscription status to ACTIVE
    """
    body = await request.body()
    
    if not verify_webhook_signature(
        body,
        x_shopify_hmac_sha256 or "",
        settings.SHOPIFY_API_SECRET
    ):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    
    data = await request.json()
    subscription_id = data.get("subscription_id") or data.get("id")
    
    if not subscription_id:
        raise HTTPException(status_code=400, detail="Invalid subscription data")
    
    # Update subscription status
    subscription = await Subscription.find_one(
        Subscription.shopify_subscription_id == str(subscription_id)
    )
    
    if subscription:
        subscription.status = SubscriptionStatus.ACTIVE
        subscription.last_synced_at = datetime.utcnow()
        subscription.updated_at = datetime.utcnow()
        # Set started_at if not already set
        if not subscription.started_at:
            from datetime import date
            subscription.started_at = date.today()
        await subscription.save()
        return {"status": "success", "message": "Subscription activated"}
    
    return {"status": "success", "message": "Subscription not found"}


@router.post("/webhooks/subscription/paused")
async def handle_subscription_paused(
    request: Request,
    x_shopify_hmac_sha256: str = Header(None, alias="X-Shopify-Hmac-Sha256")
):
    """
    Handle subscription pause webhook
    Updates subscription status to PAUSED
    """
    body = await request.body()
    
    if not verify_webhook_signature(
        body,
        x_shopify_hmac_sha256 or "",
        settings.SHOPIFY_API_SECRET
    ):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    
    data = await request.json()
    subscription_id = data.get("subscription_id") or data.get("id")
    
    if not subscription_id:
        raise HTTPException(status_code=400, detail="Invalid subscription data")
    
    # Update subscription status
    subscription = await Subscription.find_one(
        Subscription.shopify_subscription_id == str(subscription_id)
    )
    
    if subscription:
        subscription.status = SubscriptionStatus.PAUSED
        subscription.last_synced_at = datetime.utcnow()
        subscription.updated_at = datetime.utcnow()
        await subscription.save()
        return {"status": "success", "message": "Subscription paused"}
    
    return {"status": "success", "message": "Subscription not found"}


@router.post("/webhooks/subscription/cancelled")
async def handle_subscription_cancelled(
    request: Request,
    x_shopify_hmac_sha256: str = Header(None, alias="X-Shopify-Hmac-Sha256")
):
    """
    Handle subscription cancellation webhook
    Updates subscription status to CANCELLED
    """
    body = await request.body()
    
    if not verify_webhook_signature(
        body,
        x_shopify_hmac_sha256 or "",
        settings.SHOPIFY_API_SECRET
    ):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    
    data = await request.json()
    subscription_id = data.get("subscription_id") or data.get("id")
    
    if not subscription_id:
        raise HTTPException(status_code=400, detail="Invalid subscription data")
    
    # Update subscription status
    subscription = await Subscription.find_one(
        Subscription.shopify_subscription_id == str(subscription_id)
    )
    
    if subscription:
        subscription.status = SubscriptionStatus.CANCELLED
        subscription.ended_at = date.today()
        subscription.last_synced_at = datetime.utcnow()
        subscription.updated_at = datetime.utcnow()
        await subscription.save()
        return {"status": "success", "message": "Subscription cancelled"}
    
    return {"status": "success", "message": "Subscription not found"}
