"""
User service - handles user creation and preference management (MongoDB)
"""
from typing import Optional
from datetime import datetime
from models.database import User, UserPreference, Goal, ActivityLevel
from models.schemas import OnboardingComplete
import math


def calculate_calorie_target(
    age: int,
    height_cm: int,
    weight_kg: float,
    goal: Goal,
    activity_level: ActivityLevel,
    gender: str = "male"  # Default, should be collected in onboarding
) -> int:
    """
    Calculate daily calorie target using Mifflin-St Jeor Equation
    """
    # BMR calculation (Mifflin-St Jeor)
    if gender.lower() == "male":
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
    else:
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age - 161
    
    # Activity multipliers
    activity_multipliers = {
        ActivityLevel.SEDENTARY: 1.2,
        ActivityLevel.LIGHT: 1.375,
        ActivityLevel.MODERATE: 1.55,
        ActivityLevel.ACTIVE: 1.725,
        ActivityLevel.VERY_ACTIVE: 1.9
    }
    
    tdee = bmr * activity_multipliers.get(activity_level, 1.55)
    
    # Goal adjustments
    goal_adjustments = {
        Goal.WEIGHT_LOSS: -500,  # 500 cal deficit
        Goal.WEIGHT_GAIN: 500,   # 500 cal surplus
        Goal.MAINTAIN: 0,
        Goal.MUSCLE_GAIN: 300,   # Moderate surplus
        Goal.GENERAL_HEALTH: 0
    }
    
    target = tdee + goal_adjustments.get(goal, 0)
    return max(1200, int(target))  # Minimum 1200 calories


def calculate_macro_targets(calories: int, goal: Goal) -> dict:
    """
    Calculate protein, carb, and fat targets based on calories and goal
    """
    if goal == Goal.WEIGHT_LOSS:
        # Higher protein, moderate carbs, lower fat
        protein_ratio = 0.35
        carb_ratio = 0.35
        fat_ratio = 0.30
    elif goal == Goal.MUSCLE_GAIN:
        # High protein, high carbs, moderate fat
        protein_ratio = 0.30
        carb_ratio = 0.45
        fat_ratio = 0.25
    elif goal == Goal.WEIGHT_GAIN:
        # Moderate protein, high carbs, moderate fat
        protein_ratio = 0.25
        carb_ratio = 0.50
        fat_ratio = 0.25
    else:  # MAINTAIN or GENERAL_HEALTH
        # Balanced macros
        protein_ratio = 0.30
        carb_ratio = 0.40
        fat_ratio = 0.30
    
    # Calculate grams (protein/carbs = 4 cal/g, fat = 9 cal/g)
    protein_g = int((calories * protein_ratio) / 4)
    carb_g = int((calories * carb_ratio) / 4)
    fat_g = int((calories * fat_ratio) / 9)
    
    return {
        "protein_g": protein_g,
        "carb_g": carb_g,
        "fat_g": fat_g
    }


async def get_or_create_user(
    shopify_customer_id: int,
    email: str,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None
) -> User:
    """Get existing user or create new one"""
    user = await User.find_one(User.shopify_customer_id == shopify_customer_id)
    
    if not user:
        user = User(
            shopify_customer_id=shopify_customer_id,
            email=email,
            first_name=first_name,
            last_name=last_name
        )
        await user.insert()
    
    return user


async def save_onboarding_data(
    user_id: str,
    onboarding_data: OnboardingComplete
) -> UserPreference:
    """Save onboarding quiz data and calculate targets"""
    
    # Ensure goal and activity_level are Enum instances
    from database import Goal, ActivityLevel
    
    # Convert string to Enum if needed
    if isinstance(onboarding_data.step1.goal, str):
        goal = Goal(onboarding_data.step1.goal)
    else:
        goal = onboarding_data.step1.goal
    
    if isinstance(onboarding_data.step2.activity_level, str):
        activity_level = ActivityLevel(onboarding_data.step2.activity_level)
    else:
        activity_level = onboarding_data.step2.activity_level
    
    # Calculate calorie and macro targets
    calories = calculate_calorie_target(
        age=onboarding_data.step1.age,
        height_cm=onboarding_data.step1.height_cm,
        weight_kg=onboarding_data.step1.weight_kg,
        goal=goal,
        activity_level=activity_level
    )
    
    macros = calculate_macro_targets(calories, goal)
    
    # Get or create preference
    preference = await UserPreference.find_one(UserPreference.user_id == user_id)
    
    if preference:
        # Update existing
        preference.age = onboarding_data.step1.age
        preference.height_cm = onboarding_data.step1.height_cm
        preference.weight_kg = onboarding_data.step1.weight_kg
        preference.goal = goal
        preference.activity_level = activity_level
        preference.dietary_preferences = onboarding_data.step3.dietary_preferences
        preference.allergies = onboarding_data.step3.allergies
        preference.daily_calorie_target = calories
        preference.protein_target_g = macros["protein_g"]
        preference.carb_target_g = macros["carb_g"]
        preference.fat_target_g = macros["fat_g"]
        preference.onboarding_completed = True
        preference.updated_at = datetime.utcnow()
        await preference.save()
    else:
        # Create new
        preference = UserPreference(
            user_id=user_id,
            age=onboarding_data.step1.age,
            height_cm=onboarding_data.step1.height_cm,
            weight_kg=onboarding_data.step1.weight_kg,
            goal=goal,
            activity_level=activity_level,
            dietary_preferences=onboarding_data.step3.dietary_preferences,
            allergies=onboarding_data.step3.allergies,
            daily_calorie_target=calories,
            protein_target_g=macros["protein_g"],
            carb_target_g=macros["carb_g"],
            fat_target_g=macros["fat_g"],
            onboarding_completed=True
        )
        await preference.insert()
    
    return preference


async def get_user_preferences(user_id: str) -> Optional[UserPreference]:
    """Get user preferences"""
    return await UserPreference.find_one(UserPreference.user_id == user_id)
