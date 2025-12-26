"""
Helper utility functions
"""
from typing import Any, Dict, Optional
from datetime import datetime, timedelta
import json


def format_datetime(dt: datetime) -> str:
    """Format datetime to ISO string"""
    return dt.isoformat()


def parse_datetime(dt_str: str) -> datetime:
    """Parse ISO datetime string"""
    return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))


def calculate_age(birth_date: datetime) -> int:
    """Calculate age from birth date"""
    today = datetime.now()
    age = today.year - birth_date.year
    if today.month < birth_date.month or (today.month == birth_date.month and today.day < birth_date.day):
        age -= 1
    return age


def safe_json_loads(json_str: str, default: Any = None) -> Any:
    """Safely parse JSON string"""
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return default


def safe_json_dumps(obj: Any, default: str = "{}") -> str:
    """Safely serialize object to JSON string"""
    try:
        return json.dumps(obj)
    except (TypeError, ValueError):
        return default


def merge_dicts(*dicts: Dict[str, Any]) -> Dict[str, Any]:
    """Merge multiple dictionaries"""
    result = {}
    for d in dicts:
        if d:
            result.update(d)
    return result


def get_nested_value(data: Dict[str, Any], path: str, default: Any = None) -> Any:
    """Get nested dictionary value using dot notation"""
    keys = path.split('.')
    value = data
    for key in keys:
        if isinstance(value, dict):
            value = value.get(key)
            if value is None:
                return default
        else:
            return default
    return value

