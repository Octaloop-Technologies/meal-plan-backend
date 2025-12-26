"""
Authentication Endpoints
Handles Shopify OAuth, user registration, and login
Includes security utilities (JWT, password hashing, etc.)
"""
from fastapi import APIRouter, Request, HTTPException, Query, Depends, status, Header
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
import bcrypt
import hmac
import hashlib
from urllib.parse import urlencode, unquote
import httpx

# Import settings and models
from config import settings
from database import User
from schemas import UserRegister, UserLogin, UserResponse, TokenResponse

router = APIRouter()
security = HTTPBearer()

# ============================================================================
# Security Utilities (consolidated from core/security.py)
# ============================================================================

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> dict:
    """Verify and decode JWT token"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash"""
    try:
        # Ensure password is a string and encode to bytes
        if isinstance(plain_password, str):
            password_bytes = plain_password.encode('utf-8')
        else:
            password_bytes = plain_password
        
        # Ensure hash is bytes
        if isinstance(hashed_password, str):
            hash_bytes = hashed_password.encode('utf-8')
        else:
            hash_bytes = hashed_password
        
        # Truncate password to 72 bytes if needed (bcrypt limitation)
        if len(password_bytes) > 72:
            password_bytes = password_bytes[:72]
        
        # Verify password using bcrypt
        return bcrypt.checkpw(password_bytes, hash_bytes)
    except Exception as e:
        if settings.DEBUG:
            print(f"[ERROR] Password verification failed: {str(e)}")
        return False


def get_password_hash(password: str) -> str:
    """Hash a password"""
    try:
        # Ensure password is a string and encode to bytes
        if isinstance(password, str):
            password_bytes = password.encode('utf-8')
        else:
            password_bytes = password
        
        # Truncate password to 72 bytes if needed (bcrypt limitation)
        if len(password_bytes) > 72:
            password_bytes = password_bytes[:72]
        
        # Generate salt and hash password
        salt = bcrypt.gensalt(rounds=12)
        hashed = bcrypt.hashpw(password_bytes, salt)
        
        # Return as string
        return hashed.decode('utf-8')
    except Exception as e:
        if settings.DEBUG:
            print(f"[ERROR] Password hashing failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Password hashing failed: {str(e)}"
        )


async def get_current_user_from_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """Get current user from JWT token"""
    token = credentials.credentials
    payload = verify_token(token)
    user_id: str = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    return {"user_id": user_id, "email": payload.get("email")}


def verify_shopify_app_proxy_signature(
    signature: str,
    query_string: str,
    secret: str
) -> bool:
    """Verify Shopify App Proxy request signature"""
    params = query_string.split('&')
    params_without_sig = [p for p in params if not p.startswith('signature=')]
    query_string_clean = '&'.join(sorted(params_without_sig))
    
    expected_signature = hmac.new(
        secret.encode('utf-8'),
        query_string_clean.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(signature, expected_signature)


def get_shopify_customer_id_from_request(request: Request) -> Optional[int]:
    """Extract Shopify customer ID from App Proxy request"""
    customer_id = request.query_params.get('customer_id')
    if customer_id:
        try:
            return int(customer_id)
        except ValueError:
            pass
    return None


async def verify_shopify_request(request: Request) -> dict:
    """Middleware to verify Shopify App Proxy request"""
    if settings.DEBUG:
        customer_id = get_shopify_customer_id_from_request(request)
        if not customer_id:
            customer_id = 123  # Test customer ID
        return {"shopify_customer_id": customer_id}
    
    signature = request.query_params.get('signature')
    if not signature:
        raise HTTPException(status_code=401, detail="Missing signature")
    
    query_params = dict(request.query_params)
    query_params.pop('signature', None)
    query_string = '&'.join([f"{k}={v}" for k, v in sorted(query_params.items())])
    
    if not verify_shopify_app_proxy_signature(
        signature,
        query_string,
        settings.SHOPIFY_APP_PROXY_SECRET
    ):
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    customer_id = get_shopify_customer_id_from_request(request)
    if not customer_id:
        raise HTTPException(status_code=400, detail="Customer ID not found in request")
    
    return {"shopify_customer_id": customer_id}


def verify_admin_api_key(
    request: Request,
    api_key: Optional[str] = Header(None, alias="X-Admin-API-Key")
) -> str:
    """Verify admin API key for protected endpoints"""
    if request.method == "OPTIONS":
        return api_key or ""
    
    if settings.DEBUG:
        print(f"[DEBUG] Admin API Key Check: {api_key[:10] + '...' if api_key else 'None'}")
    
    if not settings.ADMIN_API_KEY:
        raise HTTPException(status_code=500, detail="Admin API key not configured")
    
    if not api_key or api_key != settings.ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid admin API key")
    
    return api_key

# ============================================================================
# Authentication Routes
# ============================================================================


def verify_hmac(query_params: dict, secret: str) -> bool:
    """Verify HMAC signature from Shopify"""
    hmac_param = query_params.pop('hmac', None)
    if not hmac_param:
        return False
    
    # Sort and encode parameters
    sorted_params = sorted(query_params.items())
    message = '&'.join([f"{k}={v}" for k, v in sorted_params])
    
    # Calculate expected HMAC
    expected_hmac = hmac.new(
        secret.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(hmac_param, expected_hmac)


@router.get("/auth/install")
async def install_app(
    shop: str = Query(..., description="Shop domain (e.g., store.myshopify.com)"),
    host: str = Query(None, description="Host parameter from Shopify")
):
    """
    Initiate OAuth installation flow
    Redirects to Shopify OAuth authorization page
    """
    if not shop.endswith('.myshopify.com'):
        raise HTTPException(status_code=400, detail="Invalid shop domain")
    
    # Generate state for CSRF protection (in production, store in session/redis)
    import secrets
    state = secrets.token_urlsafe(32)
    
    # Build authorization URL
    auth_url = f"https://{shop}/admin/oauth/authorize"
    params = {
        'client_id': settings.SHOPIFY_API_KEY,
        'scope': ','.join([
            # Customer data
            'read_customers',
            'write_customers',
            # Orders for subscriptions
            'read_orders',
            'write_orders',
            # Subscriptions
            'read_own_subscription_contracts',
            'write_own_subscription_contracts',
            # App proxy
            'write_app_proxy',
            # Products (if needed for meal products)
            'read_products',
            # Draft orders (for subscription setup)
            'read_draft_orders',
            'write_draft_orders',
        ]),
        'redirect_uri': f"{settings.APP_BASE_URL}/api/v1/auth/callback",
        'state': state,
    }
    
    if host:
        params['host'] = host
    
    redirect_url = f"{auth_url}?{urlencode(params)}"
    return RedirectResponse(url=redirect_url)


@router.get("/auth/callback")
async def oauth_callback(
    code: str = Query(..., description="Authorization code from Shopify"),
    shop: str = Query(..., description="Shop domain"),
    state: str = Query(None, description="State parameter for CSRF protection"),
    hmac_param: str = Query(None, alias="hmac", description="HMAC signature"),
    host: str = Query(None, description="Host parameter"),
):
    """
    Handle OAuth callback from Shopify
    Exchanges authorization code for access token
    """
    # Verify HMAC
    query_params = {
        'code': code,
        'shop': shop,
        'state': state or '',
        'host': host or '',
    }
    if hmac_param:
        query_params['hmac'] = hmac_param
    
    if not verify_hmac(query_params.copy(), settings.SHOPIFY_API_SECRET):
        raise HTTPException(status_code=401, detail="Invalid HMAC signature")
    
    # Exchange code for access token
    token_url = f"https://{shop}/admin/oauth/access_token"
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            token_url,
            json={
                'client_id': settings.SHOPIFY_API_KEY,
                'client_secret': settings.SHOPIFY_API_SECRET,
                'code': code,
            }
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Failed to get access token: {response.text}"
            )
        
        token_data = response.json()
        access_token = token_data.get('access_token')
        scope = token_data.get('scope', '')
        
        # Store access token in database
        from database import AccessToken
        from datetime import datetime
        
        print(f"Access token received for {shop}")
        print(f"Scopes granted: {scope}")
        
        # Check if token already exists for this shop
        existing_token = await AccessToken.find_one(AccessToken.shop == shop)
        
        if existing_token:
            # Update existing token
            existing_token.access_token = access_token
            existing_token.scope = scope
            existing_token.updated_at = datetime.utcnow()
            await existing_token.save()
            print(f"Updated access token for {shop}")
        else:
            # Create new token record
            new_token = AccessToken(
                shop=shop,
                access_token=access_token,
                scope=scope,
                expires_at=None  # Shopify tokens don't expire unless revoked
            )
            await new_token.insert()
            print(f"Stored new access token for {shop}")
    
    # Redirect to app or success page
    if host:
        # Embedded app redirect
        redirect_url = f"https://{shop}/admin/apps/{settings.SHOPIFY_API_KEY}"
    else:
        # Standalone app redirect
        redirect_url = f"https://{shop}/admin"
    
    return RedirectResponse(url=redirect_url)


@router.get("/auth/verify")
async def verify_installation(
    shop: str = Query(..., description="Shop domain")
):
    """
    Verify if app is installed and has required scopes
    """
    from database import AccessToken
    
    # Check database for stored access token
    token = await AccessToken.find_one(AccessToken.shop == shop)
    
    if token:
        return {
            "shop": shop,
            "installed": True,
            "scopes": token.scope.split(',') if token.scope else [],
            "has_token": True
        }
    else:
        return {
            "shop": shop,
            "installed": False,
            "scopes": [],
            "has_token": False,
            "message": "App not installed. Please install via OAuth."
        }


@router.post("/auth/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserRegister):
    """
    Register a new user with email and password
    """
    # Check if user already exists
    existing_user = await User.find_one(User.email == user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    hashed_password = get_password_hash(user_data.password)
    new_user = User(
        email=user_data.email,
        password_hash=hashed_password,
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        shopify_customer_id=None,  # Not linked to Shopify
        is_active=True
    )
    await new_user.insert()
    
    # Create access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(new_user.id), "email": new_user.email},
        expires_delta=access_token_expires
    )
    
    # Return token and user data
    user_response = UserResponse(
        id=str(new_user.id),
        email=new_user.email,
        first_name=new_user.first_name,
        last_name=new_user.last_name,
        phone=new_user.phone,
        shopify_customer_id=new_user.shopify_customer_id,
        is_active=new_user.is_active,
        created_at=new_user.created_at
    )
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=user_response
    )


@router.post("/auth/login", response_model=TokenResponse)
async def login(credentials: UserLogin):
    """
    Login with email and password
    """
    try:
        # Find user by email
        user = await User.find_one(User.email == credentials.email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password"
            )
        
        # Check if user has password (not Shopify-only user)
        if not user.password_hash:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Please use Shopify login for this account"
            )
        
        # Verify password
        try:
            password_valid = verify_password(credentials.password, user.password_hash)
            if not password_valid:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Incorrect email or password"
                )
        except HTTPException:
            raise
        except Exception as e:
            if settings.DEBUG:
                print(f"[ERROR] Password verification error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password"
            )
        
        # Check if user is active
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is deactivated"
            )
        
        # Create access token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": str(user.id), "email": user.email},
            expires_delta=access_token_expires
        )
        
        # Verify token was created
        if not access_token:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create access token"
            )
        
        # Return token and user data
        user_response = UserResponse(
            id=str(user.id),
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            phone=user.phone,
            shopify_customer_id=user.shopify_customer_id,
            is_active=user.is_active,
            created_at=user.created_at
        )
        
        response = TokenResponse(
            access_token=access_token,
            token_type="bearer",
            user=user_response
        )
        
        # Debug logging in development
        if settings.DEBUG:
            print(f"[DEBUG] Login successful for user: {user.email}")
            print(f"[DEBUG] Token created: {access_token[:20]}...")
            print(f"[DEBUG] Response: {response.model_dump()}")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        if settings.DEBUG:
            import traceback
            print(f"[ERROR] Login error: {str(e)}")
            traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {str(e)}"
        )


@router.get("/auth/me", response_model=UserResponse)
async def get_current_user(
    current_user: dict = Depends(get_current_user_from_token)
):
    """
    Get current authenticated user
    """
    user_id = current_user["user_id"]
    user = await User.get(user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return UserResponse(
        id=str(user.id),
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        phone=user.phone,
        shopify_customer_id=user.shopify_customer_id,
        is_active=user.is_active,
        created_at=user.created_at
    )
