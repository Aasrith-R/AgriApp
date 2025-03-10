import requests
from datetime import datetime

API_KEY = "b9cd298593ba9f5db898d737ff3107bd"  # AccuWeather API key used to pull weather data for functionality purposes

def fetch_coordinates(city_name, api_key="b9cd298593ba9f5db898d737ff3107bd"):
    geocode_url = f"https://api.openweathermap.org/data/2.5/weather?q={city_name}&appid={api_key}"
    response = requests.get(geocode_url)
    data = response.json()
    
    if data.get("cod") == 200:  
        lat = data["coord"]["lat"]
        lon = data["coord"]["lon"]
        return lat, lon
    else:
        return None, None
#fetching weatehr data from the api key
def fetch_weather_data(city_name, depth=0 ,api_key="b9cd298593ba9f5db898d737ff3107bd"):
    weather_url = f'https://api.openweathermap.org/data/2.5/weather?q={city_name}&appid={api_key}'
    response = requests.get(weather_url)
    weather_info = response.json()
    
    if weather_info['cod'] == 200:
        kelvin = 273
        temp = int(weather_info['main']['temp'] - kelvin)
        humidity = weather_info['main']['humidity']
        description = weather_info['weather'][0]['description']
        wind_speed = weather_info['wind']['speed']
        precipitation = weather_info.get('rain', {}).get('1h', 0) 


        soil_temp = temp - 0.5 * depth
        print(f"original temp {temp}, soil temp {soil_temp} real depth {depth}")


        return temp, humidity, description.capitalize(), wind_speed, precipitation, soil_temp
    else:
        return None, None, "Weather data not found!", None, None

#fetching air pollution data from the api key
def fetch_air_pollution_data(city_name, api_key="b9cd298593ba9f5db898d737ff3107bd"):
    lat, lon = fetch_coordinates(city_name, api_key)
    if lat is None and lon is None:
        return 0.0
    else:
        url = f"https://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={api_key}"
        response = requests.get(url)
        data = response.json()
        
        if data.get("list"):
            pm25_concentration = data["list"][0]["components"]["pm2_5"]
            return round(pm25_concentration)
        else:
            return 0.0
        
#caluclating pm25 baed on certain metrics
def calculate_aqi_pm25(concentration):
    try:
        concentration = float(concentration)
    except ValueError:
        return "Invalid data for AQI calculation"
    if concentration <= 12:
        return "Poor"
    elif concentration <= 35.4:
        return "Moderate"
    elif concentration <= 55.4:
        return "Unhealthy for Sensitive Groups"
    else:
        return "Unhealthy"

#function for processing wetaher related data of city
def print_data(city_name):
    temp, humidity, weather_description = fetch_weather_data(city_name)
    pm25 = fetch_air_pollution_data()
    aqi_description = calculate_aqi_pm25(pm25)
    lat, lon = fetch_coordinates(city_name, API_KEY)
    now = datetime.now()
    current_time = now.strftime("%H:%M:%S")

    data = {
        "time": current_time,
        "temperature": temp,
        "humidity": humidity,
        "weather_description": weather_description,
        "aqi_description": aqi_description,
        "pm25": pm25,
        "lattiude": lat,
        "longitude": lon,
        #"soil_temp": soil_temp,
    }
    return data



