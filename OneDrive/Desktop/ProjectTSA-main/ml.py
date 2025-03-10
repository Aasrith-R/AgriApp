from functools import lru_cache, wraps
from typing import Dict, List, Optional
import requests
from time import time

# Plant-specific temperature thresholds
PLANT_THRESHOLDS = {
    "tomato": {"min_temp": 10, "max_temp": 35},
    "lettuce": {"min_temp": 5, "max_temp": 25},
    "default": {"min_temp": 0, "max_temp": 30}
}

def timed_lru_cache(seconds: int, maxsize: int = 128):
    def wrapper_decorator(func):
        func = lru_cache(maxsize=maxsize)(func)
        func.lifetime = seconds
        func.expiration = time() + seconds

        @wraps(func)
        def wrapped_func(*args, **kwargs):
            if time() >= func.expiration:
                func.cache_clear()
                func.expiration = time() + func.lifetime
            return func(*args, **kwargs)

        return wrapped_func
    return wrapper_decorator

@timed_lru_cache(seconds=1800, maxsize=128)  # Cache results for 30 minutes
def fetch_realtime_weather(city_name: str, api_key: str) -> Optional[Dict]:
    if not city_name or not api_key:
        print("Error: Missing city name or API key")
        return None

    url = f"https://api.openweathermap.org/data/2.5/weather?q={city_name}&units=metric&appid={api_key}"
    
    try:
        response = requests.get(url, timeout=10)  # Add timeout
        response.raise_for_status()  # Raise exception for bad status codes
        
        data = response.json()
        return {
            "temperature": data["main"].get("temp"),
            "humidity": data["main"].get("humidity"),
            "wind_speed": data["wind"].get("speed"),
            "description": data["weather"][0].get("description") if data.get("weather") else None,
            "city": data.get("name")
        }
    except requests.RequestException as e:
        print(f"Error fetching weather data: {e}")
        return None
    except (KeyError, ValueError) as e:
        print(f"Error parsing weather data: {e}")
        return None

def generate_plant_care_recommendations(city_name: str, plant_type: str, api_key: str) -> List[str]:
    if not city_name or not plant_type:
        return ["Please provide both city name and plant type."]

    weather_data = fetch_realtime_weather(city_name, api_key)
    if not weather_data:
        return ["Failed to fetch weather data. Please try again later."]

    # Get plant-specific thresholds or use defaults
    thresholds = PLANT_THRESHOLDS.get(plant_type.lower(), PLANT_THRESHOLDS["default"])
    recommendations = []

    # Temperature recommendations
    temp = weather_data.get("temperature")
    if temp is not None:
        if temp < thresholds["min_temp"]:
            recommendations.append(
                f"Warning: Temperature ({temp}°C) is below minimum for {plant_type} "
                f"({thresholds['min_temp']}°C). Consider moving plants indoors."
            )
        elif temp > thresholds["max_temp"]:
            recommendations.append(
                f"Warning: Temperature ({temp}°C) is above maximum for {plant_type} "
                f"({thresholds['max_temp']}°C). Provide shade and increase watering."
            )

    humidity = weather_data.get("humidity", None)
    if humidity is not None:
        if humidity > 70:
            recommendations.append(f"High humidity detected. Check your {plant_type} plants for fungal infections and ensure good airflow.")
        elif humidity < 30:
            recommendations.append(f"Low humidity detected. Increase watering frequency or mist your {plant_type} plants to prevent drying out.")

    wind_speed = weather_data.get("wind_speed", None)
    if wind_speed is not None:
        if wind_speed > 6:
            recommendations.append(f"High wind speed detected. Secure tall plants or delicate {plant_type} plants with stakes.")
        elif wind_speed > 3:
            recommendations.append("Moderate wind speed. Check for dryness as wind may increase evaporation.")

    precipitation = weather_data.get("precipitation", 0)
    if precipitation is not None:
        if precipitation == 0:
            recommendations.append(f"No precipitation detected. Water your {plant_type} plants as needed.")
        elif precipitation > 10:
            recommendations.append(f"Heavy rainfall detected. Ensure proper drainage for your {plant_type} plants to prevent waterlogging.")

    aqi = weather_data.get("aqi", None)
    if aqi is not None:
        if aqi > 100:
            recommendations.append("Poor air quality detected. Minimize outdoor exposure for sensitive plants.")
        elif aqi <= 50:
            recommendations.append("Good air quality. No specific actions needed.")

    soil_temp = weather_data.get("soil_temperature", None)
    if soil_temp is not None:
        if soil_temp < 0:
            recommendations.append(f"Cold soil temperature detected. Avoid planting new {plant_type} seeds or watering frequently.")
        elif soil_temp > 10:
            recommendations.append(f"Good soil conditions. You can plant and water your {plant_type} as usual.")

    return recommendations or ["No specific recommendations at this time."]
