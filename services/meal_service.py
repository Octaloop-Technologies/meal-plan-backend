"""
Meal Engine - generates personalized daily meal plans (MongoDB/Beanie version)
"""
from typing import List, Optional, Dict
from datetime import date, timedelta
from models.database import (
    Meal, UserPreference, DailyMealPlan, MealRotationLog, MealType, SubscriptionStatus
)
import random


async def get_available_meals(
    meal_type: MealType,
    preferences: UserPreference,
    exclude_meal_ids: List[str] = None
) -> List[Meal]:
    """
    Get available meals matching user preferences and constraints
    """
    exclude_meal_ids = exclude_meal_ids or []
    
    # First, check if ANY meals exist for this meal_type (for debugging)
    all_meals_count = await Meal.find(Meal.meal_type == meal_type).count()
    print(f"[DEBUG] Total meals in DB for {meal_type.value}: {all_meals_count}")
    
    # Base query - only filter by meal_type and is_active
    query = Meal.find(
        Meal.meal_type == meal_type,
        Meal.is_active == True
    )
    
    # Get all meals first, then filter in Python (Beanie doesn't support complex tag filtering easily)
    meals = await query.to_list()
    print(f"[DEBUG] Active meals found for {meal_type.value}: {len(meals)}")
    
    # If no active meals found, try without is_active filter (fallback)
    if not meals:
        print(f"[WARNING] No active meals found for {meal_type.value}, trying without is_active filter...")
        query_fallback = Meal.find(Meal.meal_type == meal_type)
        meals = await query_fallback.to_list()
        print(f"[DEBUG] Meals found (including inactive) for {meal_type.value}: {len(meals)}")
    
    # Filter by dietary preferences
    dietary_prefs = preferences.dietary_preferences or []
    initial_count = len(meals)
    
    # Filter by dietary preferences
    if "vegetarian" in dietary_prefs:
        meals = [m for m in meals if "meat" not in m.tags and "fish" not in m.tags and "poultry" not in m.tags]
    
    if "vegan" in dietary_prefs:
        meals = [m for m in meals if "dairy" not in m.tags and "eggs" not in m.tags 
                and "meat" not in m.tags and "fish" not in m.tags and "poultry" not in m.tags]
    
    if "keto" in dietary_prefs:
        meals = [m for m in meals if "keto" in m.tags]
    
    if "paleo" in dietary_prefs:
        meals = [m for m in meals if "paleo" in m.tags]
    
    print(f"[DEBUG] After dietary filter ({dietary_prefs}): {len(meals)} meals (from {initial_count})")
    
    # Filter out allergies
    allergies = preferences.allergies or []
    for allergy in allergies:
        meals = [m for m in meals if allergy not in m.tags]
        # Also check ingredients
        meals = [m for m in meals if not any(
            ing.get("name", "").lower() == allergy.lower() for ing in (m.ingredients or [])
        )]
    
    print(f"[DEBUG] After allergy filter ({allergies}): {len(meals)} meals")
    
    # Exclude recently served meals
    if exclude_meal_ids:
        meals = [m for m in meals if str(m.id) not in exclude_meal_ids]
        print(f"[DEBUG] After excluding {len(exclude_meal_ids)} recent meals: {len(meals)} meals")
    
    return meals


async def select_meal_for_type(
    meal_type: MealType,
    preferences: UserPreference,
    target_calories: int,
    exclude_meal_ids: List[str] = None,
    user_id: str = None
) -> Optional[Meal]:
    """
    Select a meal for a specific meal type that fits calorie target
    """
    # Get available meals
    available_meals = await get_available_meals(meal_type, preferences, exclude_meal_ids)
    
    if not available_meals:
        print(f"[WARNING] No available meals found for {meal_type.value} after filtering")
        # Try to get ANY meal of this type without filters (last resort)
        fallback_meals = await Meal.find(Meal.meal_type == meal_type).to_list()
        if fallback_meals:
            print(f"[INFO] Found {len(fallback_meals)} meals without filters, using first one")
            return fallback_meals[0]
        return None
    
    # Filter by calorie range (allow ±20% flexibility)
    calorie_min = int(target_calories * 0.8)
    calorie_max = int(target_calories * 1.2)
    
    # Try to find meals in calorie range
    suitable_meals = [m for m in available_meals if calorie_min <= m.calories <= calorie_max]
    
    if not suitable_meals:
        # If no exact match, get closest
        suitable_meals = sorted(available_meals, key=lambda m: abs(m.calories - target_calories))[:5]
    
    # Check rotation - prefer meals not served recently
    if user_id:
        recent_dates = [date.today() - timedelta(days=i) for i in range(1, 8)]  # Last 7 days
        # Query for recent meals
        recent_meals_query = MealRotationLog.find(
            MealRotationLog.user_id == user_id,
            MealRotationLog.meal_type == meal_type
        )
        recent_meals = await recent_meals_query.to_list()
        # Filter by date in Python
        recent_meals = [m for m in recent_meals if m.served_date in recent_dates]
        
        recent_meal_ids = [str(m.meal_id) for m in recent_meals]
        
        # Prefer meals not in recent rotation
        preferred_meals = [m for m in suitable_meals if str(m.id) not in recent_meal_ids]
        if preferred_meals:
            suitable_meals = preferred_meals
    
    # Random selection from suitable meals
    return random.choice(suitable_meals) if suitable_meals else None


def calculate_meal_distribution(preferences: UserPreference) -> Dict[MealType, int]:
    """
    Calculate calorie distribution across meal types
    """
    total_calories = preferences.daily_calorie_target or 2000
    
    # Standard distribution
    distribution = {
        MealType.BREAKFAST: int(total_calories * 0.25),  # 25%
        MealType.LUNCH: int(total_calories * 0.35),      # 35%
        MealType.DINNER: int(total_calories * 0.30),     # 30%
        MealType.SNACK: int(total_calories * 0.10),      # 10%
    }
    
    return distribution


async def generate_daily_plan(
    user_id: str,
    plan_date: date,
    preferences: UserPreference
) -> DailyMealPlan:
    """
    Generate a complete daily meal plan for a user
    """
    # Check if plan already exists
    existing_plan = await DailyMealPlan.find_one(
        DailyMealPlan.user_id == user_id,
        DailyMealPlan.plan_date == plan_date
    )
    
    if existing_plan:
        return existing_plan
    
    # Calculate calorie distribution
    distribution = calculate_meal_distribution(preferences)
    
    # Select meals for each type
    breakfast = await select_meal_for_type(
        MealType.BREAKFAST, preferences,
        distribution[MealType.BREAKFAST],
        user_id=user_id
    )
    
    lunch = await select_meal_for_type(
        MealType.LUNCH, preferences,
        distribution[MealType.LUNCH],
        user_id=user_id
    )
    
    dinner = await select_meal_for_type(
        MealType.DINNER, preferences,
        distribution[MealType.DINNER],
        user_id=user_id
    )
    
    snack = await select_meal_for_type(
        MealType.SNACK, preferences,
        distribution[MealType.SNACK],
        user_id=user_id
    )
    
    # Check if we have at least some meals
    if not breakfast and not lunch and not dinner and not snack:
        # Debug: Check what meals exist in database
        total_meals = await Meal.find_all().count()
        breakfast_count = await Meal.find(Meal.meal_type == MealType.BREAKFAST).count()
        lunch_count = await Meal.find(Meal.meal_type == MealType.LUNCH).count()
        dinner_count = await Meal.find(Meal.meal_type == MealType.DINNER).count()
        snack_count = await Meal.find(Meal.meal_type == MealType.SNACK).count()
        
        error_msg = (
            f"No meals available in database. "
            f"Total meals: {total_meals}, "
            f"Breakfast: {breakfast_count}, "
            f"Lunch: {lunch_count}, "
            f"Dinner: {dinner_count}, "
            f"Snack: {snack_count}. "
            f"Please add meals first."
        )
        print(f"[ERROR] {error_msg}")
        raise ValueError(error_msg)
    
    # Calculate totals
    total_calories = sum([
        breakfast.calories if breakfast else 0,
        lunch.calories if lunch else 0,
        dinner.calories if dinner else 0,
        snack.calories if snack else 0
    ])
    
    total_protein = sum([
        float(breakfast.protein_g) if breakfast else 0,
        float(lunch.protein_g) if lunch else 0,
        float(dinner.protein_g) if dinner else 0,
        float(snack.protein_g) if snack else 0
    ])
    
    total_carbs = sum([
        float(breakfast.carbs_g) if breakfast else 0,
        float(lunch.carbs_g) if lunch else 0,
        float(dinner.carbs_g) if dinner else 0,
        float(snack.carbs_g) if snack else 0
    ])
    
    total_fat = sum([
        float(breakfast.fat_g) if breakfast else 0,
        float(lunch.fat_g) if lunch else 0,
        float(dinner.fat_g) if dinner else 0,
        float(snack.fat_g) if snack else 0
    ])
    
    # Create daily plan
    daily_plan = DailyMealPlan(
        user_id=user_id,
        plan_date=plan_date,
        breakfast_meal_id=str(breakfast.id) if breakfast else None,
        lunch_meal_id=str(lunch.id) if lunch else None,
        dinner_meal_id=str(dinner.id) if dinner else None,
        snack_meal_id=str(snack.id) if snack else None,
        total_calories=total_calories,
        total_protein_g=total_protein,
        total_carbs_g=total_carbs,
        total_fat_g=total_fat
    )
    
    await daily_plan.insert()
    
    # Log meal rotation
    meals_to_log = [
        (breakfast, MealType.BREAKFAST),
        (lunch, MealType.LUNCH),
        (dinner, MealType.DINNER),
        (snack, MealType.SNACK)
    ]
    
    for meal, meal_type in meals_to_log:
        if meal:
            rotation_log = MealRotationLog(
                user_id=user_id,
                meal_id=str(meal.id),
                served_date=plan_date,
                meal_type=meal_type
            )
            await rotation_log.insert()
    
    return daily_plan


async def generate_weekly_plan(
    user_id: str,
    week_start_date: date,
    preferences: UserPreference
) -> List[DailyMealPlan]:
    """
    Generate meal plans for an entire week
    """
    daily_plans = []
    
    for i in range(7):
        plan_date = week_start_date + timedelta(days=i)
        daily_plan = await generate_daily_plan(user_id, plan_date, preferences)
        daily_plans.append(daily_plan)
    
    return daily_plans
