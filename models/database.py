"""
MongoDB database models using Beanie ODM
"""
from beanie import Document, Indexed
from pydantic import Field
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from enum import Enum
from config import settings


# Enum definitions
class Goal(str, Enum):
    WEIGHT_LOSS = "weight_loss"
    WEIGHT_GAIN = "weight_gain"
    MAINTAIN = "maintain"
    MUSCLE_GAIN = "muscle_gain"
    GENERAL_HEALTH = "general_health"


class ActivityLevel(str, Enum):
    SEDENTARY = "sedentary"
    LIGHT = "light"
    MODERATE = "moderate"
    ACTIVE = "active"
    VERY_ACTIVE = "very_active"


class MealType(str, Enum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"


class PlanStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"


class SubscriptionStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class SubscriptionProvider(str, Enum):
    RECHARGE = "recharge"
    APPSTLE = "appstle"
    LOOP = "loop"
    SHOPIFY = "shopify"


# MongoDB Document Models
class User(Document):
    shopify_customer_id: Optional[Indexed(int)] = None  # Optional for non-Shopify users
    email: Indexed(str, unique=True)
    password_hash: Optional[str] = None  # Hashed password for email/password auth
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Settings:
        name = "users"
        indexes = [
            [("shopify_customer_id", 1)],
            [("email", 1)],
        ]


class UserPreference(Document):
    user_id: Indexed(str)  # Reference to User._id
    age: Optional[int] = None
    height_cm: Optional[int] = None
    weight_kg: Optional[float] = None
    goal: Goal
    activity_level: ActivityLevel = ActivityLevel.MODERATE
    dietary_preferences: List[str] = Field(default_factory=list)
    allergies: List[str] = Field(default_factory=list)
    daily_calorie_target: Optional[int] = None
    protein_target_g: Optional[int] = None
    carb_target_g: Optional[int] = None
    fat_target_g: Optional[int] = None
    onboarding_completed: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Settings:
        name = "user_preferences"
        indexes = [
            [("user_id", 1)],
        ]


class Meal(Document):
    title: str
    description: Optional[str] = None
    meal_type: MealType
    calories: int
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: float = 0.0
    ingredients: List[Dict[str, Any]]  # List of ingredient dicts
    instructions: Optional[str] = None
    prep_time_minutes: Optional[int] = None
    cook_time_minutes: Optional[int] = None
    tags: List[str] = Field(default_factory=list)
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Settings:
        name = "meals"
        indexes = [
            [("meal_type", 1)],
            [("is_active", 1)],
            [("calories", 1)],
        ]


class DailyMealPlan(Document):
    user_id: Indexed(str)  # Reference to User._id
    plan_date: Indexed(date)
    breakfast_meal_id: Optional[str] = None  # Reference to Meal._id
    lunch_meal_id: Optional[str] = None
    dinner_meal_id: Optional[str] = None
    snack_meal_id: Optional[str] = None
    total_calories: Optional[int] = None
    total_protein_g: Optional[float] = None
    total_carbs_g: Optional[float] = None
    total_fat_g: Optional[float] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Settings:
        name = "daily_meal_plans"
        indexes = [
            [("user_id", 1), ("plan_date", 1)],  # Unique compound index
            [("user_id", 1)],
            [("plan_date", 1)],
        ]


class WeeklyPlan(Document):
    user_id: Indexed(str)  # Reference to User._id
    week_start_date: Indexed(date)
    week_end_date: date
    status: PlanStatus = PlanStatus.DRAFT
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Settings:
        name = "weekly_plans"
        indexes = [
            [("user_id", 1)],
            [("week_start_date", 1), ("week_end_date", 1)],
        ]


class ShoppingList(Document):
    user_id: Indexed(str)  # Reference to User._id
    weekly_plan_id: Optional[str] = None  # Reference to WeeklyPlan._id
    week_start_date: Indexed(date)
    week_end_date: date
    ingredients: List[Dict[str, Any]]  # List of ingredient dicts
    pdf_url: Optional[str] = None
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Settings:
        name = "shopping_lists"
        indexes = [
            [("user_id", 1)],
            [("week_start_date", 1), ("week_end_date", 1)],
        ]


class SubscriptionPlan(Document):
    """Subscription plan templates (daily, weekly, monthly)"""
    name: str
    description: Optional[str] = None
    billing_frequency: Indexed(str)  # 'daily', 'weekly', or 'monthly'
    price: float
    price_period: str  # 'per day', 'per week', 'per month'
    features: List[str] = Field(default_factory=list)
    is_active: bool = True
    display_order: int = 0  # For sorting plans
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Settings:
        name = "subscription_plans"
        indexes = [
            [("billing_frequency", 1)],
            [("is_active", 1)],
            [("display_order", 1)],
        ]


class Subscription(Document):
    user_id: Indexed(str)  # Reference to User._id
    shopify_subscription_id: Indexed(str, unique=True)
    status: SubscriptionStatus = SubscriptionStatus.ACTIVE
    subscription_provider: SubscriptionProvider = SubscriptionProvider.SHOPIFY
    billing_frequency: Optional[str] = None  # 'weekly' or 'monthly'
    next_charge_date: Optional[date] = None
    last_charge_date: Optional[date] = None
    started_at: Optional[date] = None
    ended_at: Optional[date] = None
    last_synced_at: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Settings:
        name = "subscriptions"
        indexes = [
            [("user_id", 1)],
            [("shopify_subscription_id", 1)],
            [("status", 1)],
        ]


class AccessToken(Document):
    """Store Shopify OAuth access tokens for each shop"""
    shop: Indexed(str, unique=True)  # Shop domain (e.g., store.myshopify.com)
    access_token: str  # OAuth access token (should be encrypted in production)
    scope: str  # Comma-separated list of granted scopes
    expires_at: Optional[datetime] = None  # Token expiration (if applicable)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Settings:
        name = "access_tokens"
        indexes = [
            [("shop", 1)],
        ]


class MealRotationLog(Document):
    user_id: Indexed(str)  # Reference to User._id
    meal_id: Indexed(str)  # Reference to Meal._id
    served_date: Indexed(date)
    meal_type: MealType
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Settings:
        name = "meal_rotation_log"
        indexes = [
            [("user_id", 1), ("meal_id", 1), ("served_date", 1)],
            [("served_date", 1)],
        ]


class AccessToken(Document):
    """Store Shopify OAuth access tokens for each shop"""
    shop: Indexed(str, unique=True)  # Shop domain (e.g., store.myshopify.com)
    access_token: str  # OAuth access token (should be encrypted in production)
    scope: str  # Comma-separated list of granted scopes
    expires_at: Optional[datetime] = None  # Token expiration (if applicable)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Settings:
        name = "access_tokens"
        indexes = [
            [("shop", 1)],
        ]


class AIMealSuggestion(Document):
    """Store AI-generated meal suggestions for users"""
    user_id: Indexed(str)  # Reference to User._id
    plan_type: str  # "daily" or "weekly"
    meal_plan: Dict[str, Any]  # The full meal plan response from OpenAI
    user_preferences_snapshot: Dict[str, Any]  # Snapshot of user preferences at generation time
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Settings:
        name = "ai_meal_suggestions"
        indexes = [
            [("user_id", 1)],
            [("user_id", 1), ("created_at", -1)],  # For getting latest suggestions per user
        ]


# Database initialization
async def init_db():
    """Initialize MongoDB connection and register documents"""
    from motor.motor_asyncio import AsyncIOMotorClient
    from beanie import init_beanie
    
    # Connect to MongoDB
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    
    # Initialize Beanie with database using attribute access
    # IMPORTANT: Use attribute access (client.db_name) not dictionary access (client['db_name'])
    # Since database name comes from settings, we use getattr for dynamic access
    database = getattr(client, settings.MONGODB_DB_NAME)
    
    await init_beanie(
        database=database,
        document_models=[
            User,
            UserPreference,
            Meal,
            DailyMealPlan,
            WeeklyPlan,
            ShoppingList,
            SubscriptionPlan,
            Subscription,
            MealRotationLog,
            AccessToken,
            AIMealSuggestion,
        ]
    )
    
    return database
