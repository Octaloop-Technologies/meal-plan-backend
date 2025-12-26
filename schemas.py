"""
Pydantic schemas for request/response validation
"""
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List, Dict, Any
from datetime import date, datetime
from enum import Enum


# Enums
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


# Onboarding Schemas
class OnboardingStep1(BaseModel):
    username: Optional[str] = None
    age: int = Field(..., ge=13, le=120)
    height_cm: int = Field(..., ge=100, le=250)
    weight_kg: float = Field(..., ge=30, le=300)
    goal: Goal


class OnboardingStep2(BaseModel):
    activity_level: ActivityLevel


class OnboardingStep3(BaseModel):
    dietary_preferences: List[str] = Field(default_factory=list)  # ['vegetarian', 'vegan', 'keto', etc.]
    allergies: List[str] = Field(default_factory=list)  # ['nuts', 'dairy', 'gluten', etc.]


class OnboardingComplete(BaseModel):
    step1: OnboardingStep1
    step2: OnboardingStep2
    step3: OnboardingStep3


# User Schemas
class UserBase(BaseModel):
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserCreate(UserBase):
    shopify_customer_id: Optional[int] = None


class UserResponse(BaseModel):
    id: str  # MongoDB ObjectId as string
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    shopify_customer_id: Optional[int] = None
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class UserPreferenceResponse(BaseModel):
    id: str  # MongoDB ObjectId as string
    user_id: str  # MongoDB ObjectId as string
    age: Optional[int] = None
    height_cm: Optional[int] = None
    weight_kg: Optional[float] = None
    goal: Goal
    activity_level: ActivityLevel
    dietary_preferences: List[str]
    allergies: List[str]
    daily_calorie_target: Optional[int] = None
    protein_target_g: Optional[int] = None
    carb_target_g: Optional[int] = None
    fat_target_g: Optional[int] = None
    onboarding_completed: bool
    
    class Config:
        from_attributes = True


# Meal Schemas
class Ingredient(BaseModel):
    name: str
    quantity: float
    unit: str  # 'g', 'ml', 'cup', 'tbsp', etc.


class MealBase(BaseModel):
    title: str
    description: Optional[str] = None
    meal_type: MealType
    calories: int = Field(..., ge=0)
    protein_g: float = Field(..., ge=0)
    carbs_g: float = Field(..., ge=0)
    fat_g: float = Field(..., ge=0)
    fiber_g: float = Field(default=0, ge=0)
    ingredients: List[Ingredient]
    instructions: Optional[str] = None
    prep_time_minutes: Optional[int] = None
    cook_time_minutes: Optional[int] = None
    tags: List[str] = Field(default_factory=list)
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    is_active: bool = True


class MealCreate(MealBase):
    pass


class MealUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    calories: Optional[int] = Field(None, ge=0)
    protein_g: Optional[float] = Field(None, ge=0)
    carbs_g: Optional[float] = Field(None, ge=0)
    fat_g: Optional[float] = Field(None, ge=0)
    fiber_g: Optional[float] = Field(None, ge=0)
    ingredients: Optional[List[Ingredient]] = None
    instructions: Optional[str] = None
    prep_time_minutes: Optional[int] = None
    cook_time_minutes: Optional[int] = None
    tags: Optional[List[str]] = None
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    is_active: Optional[bool] = None


class MealResponse(MealBase):
    id: str  # MongoDB ObjectId as string
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# Daily Plan Schemas
class DailyMealPlanResponse(BaseModel):
    id: str  # MongoDB ObjectId as string
    user_id: str  # MongoDB ObjectId as string
    plan_date: date
    breakfast_meal: Optional[MealResponse] = None
    lunch_meal: Optional[MealResponse] = None
    dinner_meal: Optional[MealResponse] = None
    snack_meal: Optional[MealResponse] = None
    total_calories: Optional[int] = None
    total_protein_g: Optional[float] = None
    total_carbs_g: Optional[float] = None
    total_fat_g: Optional[float] = None
    
    class Config:
        from_attributes = True


# Weekly Plan Schemas
class WeeklyPlanResponse(BaseModel):
    id: str  # MongoDB ObjectId as string
    user_id: str  # MongoDB ObjectId as string
    week_start_date: date
    week_end_date: date
    status: str
    daily_plans: List[DailyMealPlanResponse] = []
    
    class Config:
        from_attributes = True


# Shopping List Schemas
class ShoppingListIngredient(BaseModel):
    name: str
    total_quantity: float
    unit: str


class ShoppingListResponse(BaseModel):
    id: str  # MongoDB ObjectId as string
    user_id: str  # MongoDB ObjectId as string
    week_start_date: date
    week_end_date: date
    ingredients: List[ShoppingListIngredient]
    pdf_url: Optional[str] = None
    generated_at: datetime
    
    class Config:
        from_attributes = True


# Subscription Schemas
class SubscriptionResponse(BaseModel):
    id: str  # MongoDB ObjectId as string
    user_id: str  # MongoDB ObjectId as string
    shopify_subscription_id: Optional[str] = None
    status: str
    subscription_provider: str
    next_charge_date: Optional[date] = None
    
    class Config:
        from_attributes = True


# API Response Schemas
class SuccessResponse(BaseModel):
    success: bool = True
    message: str


class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    details: Optional[Dict[str, Any]] = None

