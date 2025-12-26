"""
Products API - Public endpoints for customers to view and purchase products
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, List, Dict, Any
from shopify import shopify_client
from subscription import get_current_user
from database import User

security = HTTPBearer(auto_error=False)

router = APIRouter()


@router.get("/products")
async def get_products(
    request: Request,
    limit: int = 50,
    status: str = "active"
):
    """
    Get products from Shopify store (public endpoint)
    Returns only active/published products for customers
    """
    try:
        access_token = await shopify_client.get_access_token()
        if not access_token:
            raise HTTPException(
                status_code=400,
                detail="Shopify store not configured. Please contact support."
            )
        
        # Fetch products from Shopify
        products = await shopify_client.list_products(limit=limit, access_token=access_token)
        
        # Filter only active/published products for customers
        if status == "active":
            products = [p for p in products if p.get("status") == "active"]
        
        # Format products for frontend (include only necessary fields)
        formatted_products = []
        for product in products:
            # Get first variant for price
            variants = product.get("variants", [])
            first_variant = variants[0] if variants else {}
            
            # Get first image
            images = product.get("images", [])
            first_image = images[0] if images else {}
            
            formatted_products.append({
                "id": product.get("id"),
                "title": product.get("title"),
                "handle": product.get("handle"),
                "description": product.get("body_html", ""),
                "price": first_variant.get("price", "0.00"),
                "compare_at_price": first_variant.get("compare_at_price"),
                "image": first_image.get("src") if first_image else None,
                "images": [img.get("src") for img in images[:5]],  # Limit to 5 images
                "variants": [
                    {
                        "id": v.get("id"),
                        "title": v.get("title"),
                        "price": v.get("price"),
                        "compare_at_price": v.get("compare_at_price"),
                        "sku": v.get("sku"),
                        "inventory_quantity": v.get("inventory_quantity"),
                        "available": v.get("inventory_quantity", 0) > 0 if v.get("inventory_management") == "shopify" else True
                    }
                    for v in variants
                ],
                "vendor": product.get("vendor"),
                "product_type": product.get("product_type"),
                "tags": product.get("tags", "").split(",") if product.get("tags") else [],
                "available": any(
                    v.get("inventory_quantity", 0) > 0 
                    if v.get("inventory_management") == "shopify" 
                    else True 
                    for v in variants
                ) if variants else True
            })
        
        return {
            "products": formatted_products,
            "count": len(formatted_products)
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to fetch products: {str(e)}")


@router.get("/products/{product_id}")
async def get_product(
    product_id: int,
    request: Request
):
    """
    Get a single product by ID
    """
    try:
        access_token = await shopify_client.get_access_token()
        if not access_token:
            raise HTTPException(
                status_code=400,
                detail="Shopify store not configured. Please contact support."
            )
        
        # Fetch all products and find the one we need
        products = await shopify_client.list_products(limit=250, access_token=access_token)
        product = next((p for p in products if p.get("id") == product_id), None)
        
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        
        # Format product
        variants = product.get("variants", [])
        images = product.get("images", [])
        
        return {
            "id": product.get("id"),
            "title": product.get("title"),
            "handle": product.get("handle"),
            "description": product.get("body_html", ""),
            "variants": [
                {
                    "id": v.get("id"),
                    "title": v.get("title"),
                    "price": v.get("price"),
                    "compare_at_price": v.get("compare_at_price"),
                    "sku": v.get("sku"),
                    "inventory_quantity": v.get("inventory_quantity"),
                    "available": v.get("inventory_quantity", 0) > 0 if v.get("inventory_management") == "shopify" else True
                }
                for v in variants
            ],
            "images": [img.get("src") for img in images],
            "vendor": product.get("vendor"),
            "product_type": product.get("product_type"),
            "tags": product.get("tags", "").split(",") if product.get("tags") else [],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch product: {str(e)}")


@router.post("/products/checkout")
async def create_checkout(
    request: Request,
    items: List[Dict[str, Any]],
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
):
    """
    Create a Shopify checkout URL for the cart items
    Returns a checkout URL that redirects to Shopify checkout
    """
    try:
        from config import settings
        
        access_token = await shopify_client.get_access_token()
        if not access_token:
            raise HTTPException(
                status_code=400,
                detail="Shopify store not configured. Please contact support."
            )
        
        # Build checkout URL with cart items
        # Format: https://{shop}.myshopify.com/cart/{variant_id}:{quantity},{variant_id}:{quantity}
        shop_domain = settings.SHOPIFY_SHOP_DOMAIN or shopify_client.shop_domain
        
        # Build cart items string
        cart_items = []
        for item in items:
            variant_id = item.get("variant_id")
            quantity = item.get("quantity", 1)
            if variant_id:
                cart_items.append(f"{variant_id}:{quantity}")
        
        if not cart_items:
            raise HTTPException(status_code=400, detail="No items in cart")
        
        # Create checkout URL
        checkout_url = f"https://{shop_domain}/cart/{','.join(cart_items)}"
        
        return {
            "checkout_url": checkout_url,
            "success": True
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to create checkout: {str(e)}")

