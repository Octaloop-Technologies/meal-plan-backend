"""
OpenAI service for AI-powered meal suggestions
"""
from typing import Dict, List, Optional
from models.database import UserPreference
from config import settings
from openai import OpenAI
import json

# Initialize OpenAI client
client = None
if settings.OPENAI_API_KEY:
    client = OpenAI(api_key=settings.OPENAI_API_KEY)


def build_meal_suggestion_prompt(
    preferences: UserPreference,
    plan_type: str = "daily"  # "daily" or "weekly"
) -> str:
    """
    Build a prompt for OpenAI to generate meal suggestions
    """
    goal = preferences.goal.value if preferences.goal else "general_health"
    activity_level = preferences.activity_level.value if preferences.activity_level else "moderate"
    dietary_prefs = ", ".join(preferences.dietary_preferences) if preferences.dietary_preferences else "none"
    allergies = ", ".join(preferences.allergies) if preferences.allergies else "none"
    daily_calories = preferences.daily_calorie_target or 2000
    
    # Calculate meal calorie distribution
    breakfast_cals = int(daily_calories * 0.25)  # 25%
    lunch_cals = int(daily_calories * 0.35)      # 35%
    dinner_cals = int(daily_calories * 0.30)     # 30%
    snack_cals = int(daily_calories * 0.10)      # 10%
    
    if plan_type == "daily":
        prompt = f"""You are a professional nutritionist AI assistant. Generate a personalized daily meal plan based on the following user preferences:

User Profile:
- Age: {preferences.age} years
- Height: {preferences.height_cm} cm
- Weight: {preferences.weight_kg} kg
- Goal: {goal.replace('_', ' ').title()}
- Activity Level: {activity_level.replace('_', ' ').title()}
- Daily Calorie Target: {daily_calories} calories
- Dietary Preferences: {dietary_prefs}
- Allergies: {allergies}

Meal Requirements:
- Breakfast: approximately {breakfast_cals} calories
- Lunch: approximately {lunch_cals} calories
- Dinner: approximately {dinner_cals} calories
- Snack (optional): approximately {snack_cals} calories

Please provide a detailed daily meal plan with:
1. Breakfast meal name, description, and exact calories
2. Lunch meal name, description, and exact calories
3. Dinner meal name, description, and exact calories
4. Snack meal name, description, and exact calories (optional)

Format your response as a JSON object with this structure:
{{
  "breakfast": {{
    "name": "meal name",
    "description": "brief description",
    "calories": number
  }},
  "lunch": {{
    "name": "meal name",
    "description": "brief description",
    "calories": number
  }},
  "dinner": {{
    "name": "meal name",
    "description": "brief description",
    "calories": number
  }},
  "snack": {{
    "name": "meal name",
    "description": "brief description",
    "calories": number
  }},
  "total_calories": number,
  "recommendations": "brief nutritionist notes about this meal plan"
}}

Ensure all meals respect dietary preferences and allergies. Total calories should be close to {daily_calories} calories."""
    
    else:  # weekly
        prompt = f"""You are a professional nutritionist AI assistant. Generate a personalized weekly meal plan based on the following user preferences:

User Profile:
- Age: {preferences.age} years
- Height: {preferences.height_cm} cm
- Weight: {preferences.weight_kg} kg
- Goal: {goal.replace('_', ' ').title()}
- Activity Level: {activity_level.replace('_', ' ').title()}
- Daily Calorie Target: {daily_calories} calories
- Dietary Preferences: {dietary_prefs}
- Allergies: {allergies}

Meal Requirements per day:
- Breakfast: approximately {breakfast_cals} calories
- Lunch: approximately {lunch_cals} calories
- Dinner: approximately {dinner_cals} calories
- Snack (optional): approximately {snack_cals} calories

Please provide a complete weekly meal plan (Monday through Sunday) with:
- Each day should have breakfast, lunch, dinner, and optional snack
- Each meal should include name, description, and exact calories
- Ensure variety across the week
- Total daily calories should be close to {daily_calories} calories

Format your response as a JSON object with this structure:
{{
  "monday": {{
    "breakfast": {{"name": "...", "description": "...", "calories": number}},
    "lunch": {{"name": "...", "description": "...", "calories": number}},
    "dinner": {{"name": "...", "description": "...", "calories": number}},
    "snack": {{"name": "...", "description": "...", "calories": number}},
    "total_calories": number
  }},
  "tuesday": {{...}},
  "wednesday": {{...}},
  "thursday": {{...}},
  "friday": {{...}},
  "saturday": {{...}},
  "sunday": {{...}},
  "weekly_recommendations": "brief nutritionist notes about this weekly meal plan"
}}

Ensure all meals respect dietary preferences and allergies. Provide variety and ensure each day totals approximately {daily_calories} calories."""
    
    return prompt


async def generate_meal_suggestions(
    preferences: UserPreference,
    plan_type: str = "daily"
) -> Dict:
    """
    Generate meal suggestions using OpenAI based on user preferences
    
    Args:
        preferences: UserPreference object
        plan_type: "daily" or "weekly"
    
    Returns:
        Dictionary with meal suggestions
    """
    if not client:
        raise ValueError("OpenAI API key not configured. Please set OPENAI_API_KEY in environment variables.")
    
    if not settings.OPENAI_API_KEY:
        raise ValueError("OpenAI API key not configured.")
    
    prompt = build_meal_suggestion_prompt(preferences, plan_type)
    
    try:
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional nutritionist AI assistant. Always respond with valid JSON format only, no additional text before or after the JSON."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.7,
            max_tokens=2000 if plan_type == "daily" else 4000
        )
        
        # Extract JSON from response
        content = response.choices[0].message.content.strip()
        
        # Try to parse JSON (sometimes OpenAI wraps it in markdown code blocks)
        if content.startswith("```json"):
            content = content.replace("```json", "").replace("```", "").strip()
        elif content.startswith("```"):
            content = content.replace("```", "").strip()
        
        # Parse JSON
        meal_plan = json.loads(content)
        
        return meal_plan
        
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse OpenAI response as JSON: {str(e)}. Response: {content[:200]}")
    except Exception as e:
        raise ValueError(f"OpenAI API error: {str(e)}")

