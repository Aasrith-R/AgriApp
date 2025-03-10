from flask import Flask, render_template, request, flash, redirect, url_for, session, jsonify
from flask_login import LoginManager, login_required, logout_user, current_user
from models import User, db, Agri2, Products, Products2
from auth import auth
from footprint import FarmCarbonFootprint
import requests
from ml import generate_plant_care_recommendations, fetch_realtime_weather 
from agribot import agribot_
from Weather import fetch_air_pollution_data, fetch_weather_data, calculate_aqi_pm25, print_data, fetch_coordinates
from datetime import datetime, timedelta
import os
import json
from typing import Dict, List, Optional
import logging
from requests.exceptions import RequestException, Timeout
import streamlit as st
import matplotlib.pyplot as plt
import io
import qrcode
import base64
from io import BytesIO
import numpy as np
from sklearn.ensemble import RandomForestRegressor
import pytz
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'TSA'
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configure API keys
ACCUWEATHER_API_KEY = "b9cd298593ba9f5db898d737ff3107bd"
WEATHER_REQUEST_TIMEOUT = 10  # seconds

# API endpoints
ACCUWEATHER_BASE_URL = "http://dataservice.accuweather.com"

OurDB = "database.db"
                            
RESPONSE = None

def DeleteTheDB():
    if os.path.exists(OurDB):
        os.remove(OurDB)
        print("Database deleted successfully.")
    else:
        print("No database file found.")

db.init_app(app)
app.register_blueprint(auth, url_prefix='/')

with app.app_context():
    db.drop_all()
    db.create_all()
    
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.init_app(app)


@login_manager.user_loader
def load_user(id):
    return User.query.get(int(id))

@app.route("/logout", methods=['GET', 'POST'])
def logout():
    logout_user()
    return redirect(url_for("check"))


@app.route("/a", methods=['GET', 'POST'])
@login_required
def logedin():
    times, temperature, humidity, wind_speed, precipitation, pm25, lat, lon, soil_temp, description = None, None, None, None, None, None, None, None, None, None

    if request.method == 'POST':
        city_name = request.form.get('city')
        print(f"City received: {city_name}")
        
        # Assign city to id its linked to
        current_user.city_name = city_name
        db.session.commit()  # Save changes to the database
        
        soil_depth = float(request.form.get('depth', 0))
        temperature, humidity, description, wind_speed, precipitation, soil_temp = fetch_weather_data(city_name, soil_depth)
        pm25 = fetch_air_pollution_data(city_name)
        lat, lon = fetch_coordinates(city_name, api_key="b9cd298593ba9f5db898d737ff3107bd")
        times = datetime.now().strftime("%H:%M:%S")

    return render_template(
        'test.html',
        times=times,
        temperature=temperature,
        humidity=humidity,
        wind_speed=wind_speed,
        precipitation=precipitation,
        pm25=pm25,
        lat=lat,
        lon=lon,
        soil_temp=soil_temp,
        description=description
    )


@app.route("/agribot", methods=['GET', 'POST'])
@login_required
def agribot():
    response = None
    if request.method == 'POST':
        user_input = request.form.get('agribot_input')
        print(f"Received user input: {user_input}")
        response = agribot_(user_input)
        print(f"Response is: {response}")

    
    return render_template('agribot.html', response=response)


@app.route("/schedule", methods=['GET', 'POST'])
@login_required
def schedule():
    if not current_user.city_name:
        flash("Please set your city in your profile first.", "warning")
        return redirect(url_for("logedin"))
    
    schedule_items = []
    weather_data = get_weather_data(current_user.city_name)
    
    if request.method == 'POST':
        # Check if this is a city update form submission
        if 'city' in request.form:
            city_name = request.form.get('city')
            if city_name:
                current_user.city_name = city_name
                db.session.commit()
                flash(f"Location updated to {city_name}", "success")
                return redirect(url_for('schedule'))
        
        # Handle schedule generation form submission
        available_days = request.form.getlist('available_days[]')
        start_time = request.form.get('start_time')
        end_time = request.form.get('end_time')
        
        if not available_days:
            flash("Please select at least one day.", "warning")
            return render_template(
                "schedule.html",
                schedule_items=[],
                weather_data=weather_data,
                now=datetime.now(),
                timedelta=timedelta,
                datetime=datetime
            )
        
        if not start_time or not end_time:
            flash("Please select both start and end times.", "warning")
            return render_template(
                "schedule.html",
                schedule_items=[],
                weather_data=weather_data,
                now=datetime.now(),
                timedelta=timedelta,
                datetime=datetime
            )
            
        try:
            # Validate time format
            start = datetime.strptime(start_time, '%H:%M').time()
            end = datetime.strptime(end_time, '%H:%M').time()
            
            if start >= end:
                flash("End time must be later than start time.", "warning")
                return render_template(
                    "schedule.html",
                    schedule_items=[],
                    weather_data=weather_data,
                    now=datetime.now(),
                    timedelta=timedelta,
                    datetime=datetime
                )
                
            # Calculate time slots
            for day in available_days:
                try:
                    day_date = datetime.strptime(day, '%Y-%m-%d').date()
                    start_dt = datetime.combine(day_date, start)
                    end_dt = datetime.combine(day_date, end)
                    available_minutes = (end_dt - start_dt).total_seconds() / 60
                    
                    if available_minutes < 60:
                        flash(f"Time slot for {day} is too short (minimum 1 hour required)", "warning")
                        continue
                    
                    # Calculate time slots
                    early_slot = min(
                        start_dt + timedelta(minutes=available_minutes * 0.2),
                        end_dt - timedelta(minutes=60)
                    )
                    mid_slot = min(
                        start_dt + timedelta(minutes=available_minutes * 0.5),
                        end_dt - timedelta(minutes=30)
                    )
                    late_slot = min(
                        start_dt + timedelta(minutes=available_minutes * 0.8),
                        end_dt
                    )
                    
                    # Get weather-based tasks
                    weather_tasks = get_weather_based_tasks(
                        weather_data.get('description', ''),
                        weather_data.get('temperature', 70),
                        weather_data.get('humidity', 50),
                        weather_data.get('wind_speed', 0)
                    )
                    
                    # Add weather-specific tasks to appropriate time slots
                    for i, task in enumerate(weather_tasks):
                        # Distribute tasks across available time slots
                        if i % 3 == 0:
                            task_time = early_slot
                        elif i % 3 == 1:
                            task_time = mid_slot
                        else:
                            task_time = late_slot
                            
                        schedule_items.append({
                            'time': task_time.time().strftime('%H:%M'),
                            'task': task['task'],
                            'icon': task['icon'],
                            'priority': task['priority'],
                            'date': day_date.strftime('%Y-%m-%d'),
                            'completed': False
                        })
                    
                    # Add general maintenance task
                    schedule_items.append({
                        'time': mid_slot.time().strftime('%H:%M'),
                        'task': 'General plant inspection and maintenance',
                        'icon': '🌱',
                        'priority': 'medium',
                        'date': day_date.strftime('%Y-%m-%d'),
                        'completed': False
                    })
                    
                except ValueError as e:
                    flash(f"Invalid date format for {day}: {str(e)}", "warning")
                    continue
                
            if not schedule_items:
                flash("No valid time slots found for scheduling.", "warning")
            
        except ValueError as e:
            flash(f"Error generating schedule: {str(e)}", "danger")
            
    # Sort schedule items by date and time
    schedule_items.sort(key=lambda x: (x['date'], x['time']))
    
    return render_template(
        "schedule.html",
        schedule_items=schedule_items,
        weather_data=weather_data,
        now=datetime.now(),
        timedelta=timedelta,
        datetime=datetime
    )

def calculate_optimal_watering_time(forecast, sunrise, sunset, current_temp, plant_type):
    """Calculate the best time to water based on conditions"""
    watering_preferences = {
        'Tomatoes': {'morning_offset': 1, 'evening_offset': 2},
        'Lettuce': {'morning_offset': 0.5, 'evening_offset': 1.5},
        'Herbs': {'morning_offset': 0.5, 'evening_offset': 1},
        'default': {'morning_offset': 1, 'evening_offset': 2}
    }
    
    prefs = watering_preferences.get(plant_type, watering_preferences['default'])
    
    # Calculate morning and evening watering times
    morning_time = sunrise + timedelta(hours=prefs['morning_offset'])
    evening_time = sunset - timedelta(hours=prefs['evening_offset'])
    
    # Check temperature and evaporation conditions
    if current_temp > 25:
        return evening_time  # Water in evening if hot
    else:
        return morning_time  # Water in morning if mild

def calculate_shade_time(time_obj, temp, plant_type):
    """Calculate when to provide shade based on temperature forecast"""
    # Default to 30 minutes before peak temperature
    shade_time = (datetime.combine(datetime.today(), time_obj) - 
                 timedelta(minutes=30)).time()
    return shade_time

def calculate_ventilation_time(hour, humidity, plant_type):
    """Calculate best time to check ventilation"""
    # Check ventilation before humidity peaks
    check_time = (datetime.strptime(hour, '%H:%M') - 
                 timedelta(minutes=45)).time()
    return check_time

def calculate_support_check_time(current_time, wind_speed, forecast, plant_type):
    """Calculate when to check plant supports"""
    if wind_speed > 30:
        # Immediate check for very strong winds
        return current_time.time()
    else:
        # Check before wind speeds increase
        return (current_time + timedelta(minutes=30)).time()

def get_sun_times(city, date=None):
    """Get sunrise and sunset times for location"""
    try:
        location_key = get_location_key(city)
        if location_key:
            url = f"http://dataservice.accuweather.com/forecasts/v1/daily/1day/{location_key}"
            params = {
                'apikey': ACCUWEATHER_API_KEY,
                'details': True
            }
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if 'DailyForecasts' in data and data['DailyForecasts']:
                    sun_data = data['DailyForecasts'][0]
                    return {
                        'sunrise': datetime.strptime(sun_data['Sun']['Rise'], "%Y-%m-%dT%H:%M:%S%z").time(),
                        'sunset': datetime.strptime(sun_data['Sun']['Set'], "%Y-%m-%dT%H:%M:%S%z").time()
                    }
    except Exception as e:
        print(f"Error fetching sun times: {e}")
    
    # Fallback to default times if API fails
    return {
        'sunrise': datetime.strptime('06:00', '%H:%M').time(),
        'sunset': datetime.strptime('18:00', '%H:%M').time()
    }

def get_humidity_forecast(forecast):
    """
    Extract humidity values from the forecast data
    """
    humidity_forecast = {}
    for time_str, data in forecast.items():
        humidity_forecast[time_str] = data['humidity']
    return humidity_forecast

def needs_watering(plant, weather_data):
    """Check if a specific plant needs watering based on conditions"""
    precipitation = weather_data[4]
    temperature = weather_data[0]
    humidity = weather_data[1]
    
    # Basic watering needs based on plant type
    watering_needs = {
        'Tomatoes': {'threshold': 3, 'temp_factor': 0.2},
        'Lettuce': {'threshold': 2, 'temp_factor': 0.15},
        'Herbs': {'threshold': 1.5, 'temp_factor': 0.1},
        'default': {'threshold': 2, 'temp_factor': 0.15}
    }
    
    plant_needs = watering_needs.get(plant.name, watering_needs['default'])
    
    # Calculate watering need based on conditions
    watering_score = (
        plant_needs['threshold'] +
        (max(0, temperature - 25) * plant_needs['temp_factor']) -
        (precipitation * 0.5) -
        (max(0, humidity - 60) * 0.02)
    )
    
    return watering_score > 1.5

def is_humidity_sensitive(plant):
    """Check if plant is sensitive to high humidity"""
    sensitive_plants = ['Tomatoes', 'Squash', 'Cucumbers', 'Roses']
    return plant.name in sensitive_plants

def is_heat_sensitive(plant):
    """Check if plant is sensitive to high temperatures"""
    sensitive_plants = ['Lettuce', 'Spinach', 'Peas', 'Broccoli']
    return plant.name in sensitive_plants

def needs_wind_protection(plant):
    """Check if plant needs protection from strong winds"""
    needs_protection = ['Tomatoes', 'Peppers', 'Corn', 'Sunflowers']
    return plant.name in needs_protection

def is_cold_sensitive(plant):
    """Check if plant is sensitive to cold soil"""
    sensitive_plants = ['Tomatoes', 'Peppers', 'Eggplants', 'Basil']
    return plant.name in sensitive_plants

# Create a global farm object
farm = FarmCarbonFootprint()

def calculate_smart_timeline(weather_data: Dict, harvest_date: datetime, product_type: str, location: str) -> List[Dict]:
    # Crop-specific optimal conditions
    CROP_CONDITIONS = {
        'Tomatoes': {
            'optimal_temp': (18, 26),
            'optimal_humidity': (65, 75),
            'heat_sensitive': True,
            'rain_sensitive': True,
            'processing_time': 4,
            'optimal_harvest_moisture': (60, 70)
        },
        'Lettuce': {
            'optimal_temp': (15, 22),
            'optimal_humidity': (60, 70),
            'heat_sensitive': True,
            'rain_sensitive': False,
            'processing_time': 2,
            'optimal_harvest_moisture': (50, 65)
        },
        'Apples': {
            'optimal_temp': (15, 24),
            'optimal_humidity': (60, 75),
            'heat_sensitive': False,
            'rain_sensitive': True,
            'processing_time': 6,
            'optimal_harvest_moisture': (55, 75)
        },
    }

    timeline = []
    crop_info = CROP_CONDITIONS.get(product_type, CROP_CONDITIONS['Tomatoes'])
    
    # Get extended weather forecast(FROM API )
    forecast = get_weather_forecast(location)
    
    # Calculate optimal harvest window
    harvest_window = calculate_harvest_window(
        harvest_date,
        forecast,
        crop_info,
        location
    )
    
    # Add harvest timing
    timeline.append({
        'stage': 'Optimal Harvest Time',
        'time': harvest_window['optimal_time'].strftime('%Y-%m-%d %H:%M'),
        'icon': '🌾',
        'weather': {
            'temperature': harvest_window['temperature'],
            'humidity': harvest_window['humidity'],
            'conditions': harvest_window['conditions']
        },
        'recommendations': harvest_window['recommendations'],
        'warning_level': harvest_window['warning_level']
    })

    # Calculate processing timing
    processing = calculate_processing_phase(
        harvest_window['optimal_time'],
        forecast,
        crop_info,
        product_type
    )
    
    timeline.append({
        'stage': 'Processing',
        'time': processing['start_time'].strftime('%Y-%m-%d %H:%M'),
        'duration': f"{processing['duration']} hours",
        'icon': '⚙️',
        'facility_conditions': processing['facility_conditions'],
        'recommendations': processing['recommendations']
    })

    # Quality check timing
    quality_check = calculate_quality_check(
        processing['end_time'],
        crop_info,
        product_type
    )
    
    timeline.append({
        'stage': 'Quality Verification',
        'time': quality_check['time'].strftime('%Y-%m-%d %H:%M'),
        'icon': '✅',
        'checks': quality_check['required_checks'],
        'certifications': quality_check['certifications']
    })

    # Calculate packaging and storage
    storage = calculate_storage_conditions(
        quality_check['time'],
        forecast,
        crop_info,
        product_type
    )
    
    timeline.append({
        'stage': 'Storage and Packaging',
        'time': storage['time'].strftime('%Y-%m-%d %H:%M'),
        'icon': '📦',
        'conditions': storage['conditions'],
        'recommendations': storage['recommendations']
    })

    # Distribution timing
    distribution = calculate_distribution_timing(
        storage['time'],
        forecast,
        location,
        crop_info
    )
    
    timeline.append({
        'stage': 'Distribution Ready',
        'time': distribution['time'].strftime('%Y-%m-%d %H:%M'),
        'icon': '🚛',
        'route_conditions': distribution['route_conditions'],
        'recommendations': distribution['recommendations'],
        'warning_level': distribution['warning_level']
    })

    return timeline

def calculate_harvest_window(base_date: datetime, forecast: Dict, crop_info: Dict, location: str) -> Dict:
    """Calculate optimal harvest time based on weather and crop requirements"""
    
    # Get sunrise/sunset timess for diff locations
    sun_times = get_sun_times(location, base_date)
    optimal_temp_range = crop_info['optimal_temp']
    
    # Find best 3-hour window for harvest.(the change)
    best_window = {
        'optimal_time': None,
        'temperature': None,
        'humidity': None,
        'conditions': None,
        'recommendations': [],
        'warning_level': 'normal'
    }

    # Default to early morning in case we can't find any better time 
    default_time = base_date.replace(hour=6, minute=0)
    
    for hour in range(24):
        temp = forecast.get(f'temp_{hour}', 20)
        humidity = forecast.get(f'humidity_{hour}', 60)
        conditions = forecast.get(f'conditions_{hour}', 'clear')
        
        score = calculate_harvest_score(
            hour,
            temp,
            humidity,
            conditions,
            sun_times,
            crop_info
        )
        
        if not best_window['optimal_time'] or score > best_window.get('score', 0):
            best_window.update({
                'optimal_time': base_date.replace(hour=hour),
                'temperature': temp,
                'humidity': humidity,
                'conditions': conditions,
                'score': score
            })
    
    # Generate recommendations by looking at the condition
    best_window['recommendations'] = generate_harvest_recommendations(
        best_window,
        crop_info
    )
    
    return best_window

def calculate_processing_phase(harvest_time: datetime, forecast: Dict, crop_info: Dict, product_type: str) -> Dict:
    """Calculate optimal processing timing and conditions"""
    base_duration = crop_info['processing_time']
    
    # Adjust the time also based on the condition 
    temp = forecast.get(f'temp_{harvest_time.hour}', 20)
    humidity = forecast.get(f'humidity_{harvest_time.hour}', 60)
    
    duration_multiplier = 1.0
    if temp > crop_info['optimal_temp'][1]:
        duration_multiplier += 0.2
    if humidity > crop_info['optimal_humidity'][1]:
        duration_multiplier += 0.15
        
    realDuration = base_duration * duration_multiplier
    
    return {
        'start_time': harvest_time + timedelta(hours=1),
        'end_time': harvest_time + timedelta(hours=1+realDuration),
        'duration': realDuration,
        'facility_conditions': {
            'temperature': f"{crop_info['optimal_temp'][0]}-{crop_info['optimal_temp'][1]}°C",
            'humidity': f"{crop_info['optimal_humidity'][0]}-{crop_info['optimal_humidity'][1]}%"
        },
        'recommendations': generate_processing_recommendations(temp, humidity, crop_info)
    }


@app.route('/blocksupchain', methods=['POST', 'GET'])
@app.route('/blocksupchain/<product_id>')
@login_required
def supplychain(product_id=None):
    if product_id:
        product = Products2.query.filter_by(product_id=product_id).first()
        if not product:
            return "Product not found", 404
        return render_template('view_product.html', product=product)

    if request.method == 'POST':
        # Getting the data
        product_name = request.form.get('productName')
        variety = request.form.get('variety')
        organic_status = request.form.get('organicStatus')
        location = request.form.get('location')
        certifications = request.form.getlist('certifications')
        carbon_footprint = request.form.get('carbonFootprint')
        sustainable_practices = request.form.getlist('sustainablePractices')
        harvest_date = request.form.get('harvestDate')

        if not product_name or not variety or not location:
            return jsonify({'error': 'Missing required fields'}), 400

        # Generating the unique ids, with PROD-
        product_id = f"PROD-{int(time.time())}"

        # Correcting the format(fix)
        product_url = f"{request.url_root}blocksupchain/{product_id}"

        # QR CODE GENERATING Proc
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(product_url)
        qr.make(fit=True)

        qr_img = qr.make_image(fill="black", back_color="white")
        buffer = BytesIO()
        qr_img.save(buffer, format="PNG")
        qr_image_data = base64.b64encode(buffer.getvalue()).decode('utf-8')

        # Savign all of the data to the DB
        new_product = Products2(
            product_id=product_id,
            product_name=product_name,
            variety=variety,
            organic_status=organic_status,
            location=location,
            certifications=','.join(certifications),
            carbon_footprint=carbon_footprint,
            sustainable_practices=','.join(sustainable_practices),
            harvest_date=harvest_date,
            qr_code=qr_image_data,
            user_id=current_user.id
        )
        db.session.add(new_product)
        db.session.commit()

        return render_template(
            'supplychain.html',
            product_url=product_url,
            product_id=product_id,
            qr_code=qr_image_data
        )

    return render_template('supplychain.html', qr_code=None)

@app.route('/products')
@login_required
def view_products(qr_code):
    products = Products.query.filter_by(qr_code=qr_code).all()
    return render_template('view_product_codes.html', products=products)


@app.route('/product_page/<product_id>')
@login_required
def product_page(product_id):
    print(product_id)
    product_data = Products2.query.filter_by(product_id=product_id).first()
    print(product_data)
    if not product_data:
        print("not found chat??")
        return "Product not found", 404
    return render_template('product_page.html', product=product_data)

@app.route('/footprint', methods=['GET', 'POST'])
@login_required
def footprint():
    if request.method == 'POST':
        try:
            # Getting the values 
            diesel = float(request.form.get("diesel", 0))
            gasoline = float(request.form.get("gasoline", 0))
            electricity = float(request.form.get("electricity", 0))
            fertilizer = float(request.form.get("fertilizer", 0))
            livestock = int(request.form.get("livestock", 0))

            activities_added = all([
                farm.add_activity("diesel", diesel),
                farm.add_activity("gasoline", gasoline),
                farm.add_activity("electricity", electricity),
                farm.add_activity("fertilizer", fertilizer),
                farm.add_activity("livestock", livestock)
            ])

            if not activities_added:
                flash("Unable to add some activities. Check your inputs", "error")
                return redirect(url_for('footprint'))

            emissions = farm.calculate_footprint()
            recommendations = farm.get_recommendations()
            total_emissions = farm.get_total_emissions()

            session['emissions'] = emissions
            session['recommendations'] = recommendations
            session['total_emissions'] = total_emissions

            return render_template(
                "footprint.html",
                emissions=emissions,
                recommendations=recommendations,
                total_emissions=total_emissions,
                show_results=True
            )

        except ValueError as e:
            flash("Please enter valid numbers for all fields.", "error")
            return redirect(url_for('footprint'))

    return render_template(
        "footprint.html",
        emissions=session.get('emissions'),
        recommendations=session.get('recommendations'),
        total_emissions=session.get('total_emissions'),
        show_results=bool(session.get('emissions'))
    )

@app.route('/reset-footprint', methods=['POST'])
@login_required
def reset_footprint():
    global farm
    farm = FarmCarbonFootprint()
    session.pop('emissions', None)
    session.pop('recommendations', None)
    session.pop('total_emissions', None)
    flash("Carbon footprint calculator was reseted.", "success")
    return redirect(url_for('footprint'))

@app.route('/dashboard')
def dashboard():
    emissions = farm.calculate_footprint()
    
    st.title("Farm Carbon Footprint Dashboard")
    fig, ax = plt.subplots()
    ax.bar(emissions.keys(), emissions.values(), color='green')
    ax.set_ylabel("kg CO2")
    ax.set_title("Carbon Footprint by Activity")
    
    # Formatting stuff
    buf = io.BytesIO()
    plt.savefig(buf, format="png")
    buf.seek(0)
    # specifying the formats and stuff
    image_base64 = base64.b64encode(buf.read()).decode("utf-8")
    
    st.image(f"data:image/png;base64,{image_base64}", use_column_width=True)
    return "Graph done"

@app.route("/machine-learning", methods=["GET", "POST"])
@login_required
def machine_learning():
    city_name = current_user.city_name
    if not city_name:
        flash("Please set your city, to get the recommendations", "warning")
        return redirect(url_for("logedin"))

    plant_type = None
    recommendations = []

    API_KEY = "b9cd298593ba9f5db898d737ff3107bd" 

    if request.method == "POST":
        plant_type = request.form.get("plant_type", "default")
        recommendations = generate_plant_care_recommendations(city_name, plant_type, API_KEY)

    return render_template(
        "ml.html", 
        recommendations=recommendations, 
        city_name=city_name, 
        plant_type=plant_type
    )

@app.route("/")
def check():
    logout_user()
    return render_template('welcome.html')

@app.route("/footprint-guide", methods=['GET', 'POST'])
def footprint_guide():
    if request.method == 'POST':
        machinery = request.form.get('machinery')
        fertilizer_type = request.form.get('fertilizer_type')
        energy = request.form.get('energy')
        livestock = request.form.get('livestock')

        estimated_values = {
            'diesel': 100 if machinery == 'older' else 50 if machinery == 'modern' else 20,
            'gasoline': 80 if machinery == 'older' else 40 if machinery == 'modern' else 15,
            'electricity': 1000 if energy == 'grid' else 200 if energy == 'mixed' else 50,
            'fertilizer': 500 if fertilizer_type == 'synthetic' else 200 if fertilizer_type == 'organic' else 50,
            'livestock': 50 if livestock == 'large' else 20 if livestock == 'small' else 0
        }

        for activity, value in estimated_values.items():
            farm.add_activity(activity, value)

        emissions = farm.calculate_footprint()
        recommendations = farm.get_recommendations()
        total_emissions = farm.get_total_emissions()

        session['emissions'] = emissions
        session['recommendations'] = recommendations
        session['total_emissions'] = total_emissions
        return redirect(url_for('footprint'))

    return render_template('footprint_guide.html')

@app.route("/disaster-alerts")
@login_required
def disaster_alerts():
    if not current_user.city_name:
        flash("Set your city in your profile to get the alerts.", "warning")
        return redirect(url_for("logedin"))

    # Fetch historical weather data and create predictions
    API_KEY = "b9cd298593ba9f5db898d737ff3107bd"
    city = current_user.city_name
    
    # Get historical data for analysis
    url = f"https://api.openweathermap.org/data/2.5/forecast?q={city}&appid={API_KEY}&units=metric"
    response = requests.get(url)
    data = response.json()

    if response.status_code != 200:
        flash("Unable to fetch weather data. Please try again.", "error")
        return redirect(url_for("logedin"))

    # Process weather data for predictions
    temps = []
    humidity = []
    pressure = []
    
    for item in data['list']:
        temps.append(item['main']['temp'])
        humidity.append(item['main']['humidity'])
        pressure.append(item['main']['pressure'])

    X = np.column_stack([humidity, pressure])
    y = np.array(temps)
    
    model = RandomForestRegressor(n_estimators=100)
    model.fit(X[:-10], y[:-10])
    
    alerts = []
    future_conditions = model.predict(X[-10:])
    
    temp_trend = np.mean(future_conditions) - np.mean(y[:-10])
    if temp_trend > 5:
        alerts.append({
            'type': 'heat',
            'severity': 'high',
            'message': 'High risk of heatwave in the next 2 weeks. Plan the possiblity of adjusting irrigation schedules.',
            'icon': '🌡️',
            'recommendations': [
                'Install shade cloths over sensitive crops',
                'Increase irrigation frequency',
                'Monitor soil moisture levels closely'
            ]
        })
    
    # Rainfall prediction based on humidity and pressure
    rain_risk = np.mean(humidity[-5:]) > 70 and np.mean(pressure[-5:]) < 1010
    if rain_risk:
        alerts.append({
            'type': 'rain',
            'severity': 'medium',
            'message': 'Increased chance of heavy rainfall next week. Prepare your farm drainage systems.',
            'icon': '🌧️',
            'recommendations': [
                'Clear drainage channels',
                'Protect sensitive crops',
                'Check flood barriers'
            ]
        })
    
    # Drought prediction
    drought_risk = np.mean(humidity[-7:]) < 40 and np.mean(temps[-7:]) > 30
    if drought_risk:
        alerts.append({
            'type': 'drought',
            'severity': 'critical',
            'message': 'Drought conditions likely in the next month. Plan water conservation measures.',
            'icon': '☀️',
            'recommendations': [
                'Implement water conservation techniques',
                'Consider drought-resistant crops',
                'Check irrigation system efficiency'
            ]
        })

    return render_template('disaster_alerts.html', alerts=alerts, city=city)

def fetch_weather_forecast(city_name):
    api_key = "b9cd298593ba9f5db898d737ff3107bd"  
    base_url = "http://api.openweathermap.org/data/2.5/forecast"
    
    try:
        lat, lon = fetch_coordinates(city_name, api_key)
        
        params = {
            'lat': lat,
            'lon': lon,
            'appid': api_key,
            'units': 'metric'  # For Celsius
        }
        
        response = requests.get(base_url, params=params)
        data = response.json()
        

        forecast = {}
        current_time = datetime.now()
        
        for item in data['list'][:8]: 
            timestamp = datetime.fromtimestamp(item['dt'])
            if timestamp > current_time:
                time_str = timestamp.strftime('%H:%M')
                forecast[time_str] = {
                    'temp': item['main']['temp'],
                    'humidity': item['main']['humidity'],
                    'conditions': item['weather'][0]['main'],
                    'wind_speed': item['wind']['speed']
                }
        
        return forecast
        
    except Exception as e:
        print(f"Error fetching forecast: {e}")
        # Default forecast
        return {
            '06:00': {'temp': 20, 'humidity': 65, 'conditions': 'Clear', 'wind_speed': 5},
            '09:00': {'temp': 22, 'humidity': 70, 'conditions': 'Clear', 'wind_speed': 6},
            '12:00': {'temp': 25, 'humidity': 75, 'conditions': 'Clear', 'wind_speed': 7},
            '15:00': {'temp': 26, 'humidity': 70, 'conditions': 'Clear', 'wind_speed': 8},
            '18:00': {'temp': 24, 'humidity': 65, 'conditions': 'Clear', 'wind_speed': 6},
            '21:00': {'temp': 22, 'humidity': 70, 'conditions': 'Clear', 'wind_speed': 5},
            '00:00': {'temp': 20, 'humidity': 75, 'conditions': 'Clear', 'wind_speed': 4},
            '03:00': {'temp': 19, 'humidity': 80, 'conditions': 'Clear', 'wind_speed': 3}
        }

def fetch_coordinates(city_name, api_key):
    base_url = "http://api.openweathermap.org/geo/1.0/direct"
    
    try:
        params = {
            'q': city_name,
            'limit': 1,
            'appid': api_key
        }
        
        response = requests.get(base_url, params=params)
        data = response.json()
        
        if data:
            return data[0]['lat'], data[0]['lon']
        else:
            # incase nothing was found
            return 0, 0
            
    except Exception as e:
        print(f"Error fetching coordinates: {e}")
        return 0, 0

@app.route('/product/<product_id>')
def view_product(product_id):
    product = Products2.query.filter_by(product_id=product_id).first()
    if not product:
        return "Product not found", 404
    
    return render_template('view_product.html', product=product)

# Helper functions for weather data
def fetch_location_data(city_name: str) -> Optional[Dict]:
    """Fetch location data from AccuWeather API with error handling."""
    try:
        # First try to get coordinates using OpenWeatherMap (more reliable for city names)
        lat, lon = fetch_coordinates(city_name, ACCUWEATHER_API_KEY)
        if lat == 0 and lon == 0:
            logger.warning(f"Could not find coordinates for city: {city_name}")
            return None

        # Then get AccuWeather location key using coordinates
        url = f"{ACCUWEATHER_BASE_URL}/locations/v1/cities/geoposition/search"
        params = {
            'apikey': ACCUWEATHER_API_KEY,
            'q': f"{lat},{lon}"
        }
        response = requests.get(url, params=params, timeout=WEATHER_REQUEST_TIMEOUT)
        response.raise_for_status()
        
        location_data = response.json()
        if location_data and 'Key' in location_data:
            return location_data
            
        logger.warning(f"No location found for coordinates: {lat}, {lon}")
        return None
        
    except Timeout:
        logger.error(f"Timeout while fetching location data for {city_name}")
        flash("Weather service is taking too long to respond. Please try again.", "warning")
    except RequestException as e:
        logger.error(f"Error fetching location data: {str(e)}")
        flash("Unable to fetch weather data. Please try again later.", "danger")
    except Exception as e:
        logger.error(f"Unexpected error fetching location data: {str(e)}")
        flash("An unexpected error occurred. Please try again later.", "danger")
    return None

def fetch_current_conditions(location_key: str) -> Optional[Dict]:
    """Fetch current weather conditions from AccuWeather API."""
    try:
        url = f"{ACCUWEATHER_BASE_URL}/currentconditions/v1/{location_key}"
        params = {
            'apikey': ACCUWEATHER_API_KEY,
            'details': True
        }
        response = requests.get(url, params=params, timeout=WEATHER_REQUEST_TIMEOUT)
        response.raise_for_status()
        
        data = response.json()
        if data and len(data) > 0:
            return data[0]
        logger.warning(f"No current conditions found for location key: {location_key}")
        return None
        
    except Timeout:
        logger.error(f"Timeout while fetching current conditions for location {location_key}")
    except RequestException as e:
        logger.error(f"Error fetching current conditions: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error fetching current conditions: {str(e)}")
    return None

def fetch_forecast(location_key: str, days: int = 5) -> Optional[Dict]:
    """Fetch weather forecast from AccuWeather API."""
    try:
        url = f"{ACCUWEATHER_BASE_URL}/forecasts/v1/daily/{days}day/{location_key}"
        params = {
            'apikey': ACCUWEATHER_API_KEY,
            'details': True
        }
        response = requests.get(url, params=params, timeout=WEATHER_REQUEST_TIMEOUT)
        response.raise_for_status()
        
        return response.json()
        
    except Timeout:
        logger.error(f"Timeout while fetching forecast for location {location_key}")
        flash("Weather service is taking too long to respond. Please try again.", "warning")
    except RequestException as e:
        logger.error(f"Error fetching forecast: {str(e)}")
        flash("Unable to fetch weather forecast. Please try again later.", "danger")
    return None

def get_weather_data(city_name: str) -> Dict:
    """Get comprehensive weather data for a city."""
    weather_data = {
        'temperature': None,
        'humidity': None,
        'precipitation': None,
        'soil_temp': None,
        'description': None,
        'wind_speed': None
    }
    
    try:
        # First try to get weather data from OpenWeatherMap as backup
        temp, humidity, description, wind_speed, precipitation, soil_temp = fetch_weather_data(city_name, 0)
        if temp is not None:
            weather_data.update({
                'temperature': temp * 9/5 + 32,  # Convert to Fahrenheit
                'humidity': humidity,
                'precipitation': precipitation,
                'wind_speed': wind_speed,
                'description': description,
                'soil_temp': soil_temp * 9/5 + 32  # Convert to Fahrenheit
            })
            
        # Then try to get more detailed data from AccuWeather
        location_data = fetch_location_data(city_name)
        if location_data:
            location_key = location_data.get('Key')
            if location_key:
                current_conditions = fetch_current_conditions(location_key)
                if current_conditions:
                    weather_data.update({
                        'temperature': current_conditions['Temperature']['Imperial']['Value'],
                        'humidity': current_conditions['RelativeHumidity'],
                        'precipitation': current_conditions.get('Precip1hr', {}).get('Imperial', {}).get('Value', 0),
                        'wind_speed': current_conditions.get('Wind', {}).get('Speed', {}).get('Imperial', {}).get('Value', 0),
                        'description': current_conditions.get('WeatherText', description or 'No description available')
                    })
                    
                    # Calculate soil temperature (simplified model)
                    if weather_data['temperature'] is not None:
                        weather_data['soil_temp'] = weather_data['temperature'] - 3.5  # Soil temp is usually slightly lower
        
        if all(v is None for v in weather_data.values()):
            flash(f"Could not find weather data for {city_name}. Please check the city name.", "warning")
            
    except Exception as e:
        logger.error(f"Error in get_weather_data: {str(e)}")
        flash("An error occurred while fetching weather data. Please try again later.", "danger")
        
    return weather_data

def get_weather_based_tasks(weather_description: str, temperature: float, humidity: float, wind_speed: float) -> List[Dict]:
    """Generate weather-specific tasks based on conditions."""
    tasks = []
    
    # Convert weather description to lowercase for easier matching
    weather_description = weather_description.lower()
    
    # Temperature-based recommendations
    if temperature < 40:
        tasks.append({
            'task': 'Check plants for frost damage and protect sensitive plants',
            'priority': 'high',
            'icon': '❄️'
        })
    elif temperature > 85:
        tasks.append({
            'task': 'Increase watering frequency and provide shade',
            'priority': 'high',
            'icon': '🌡️'
        })
        tasks.append({
            'task': 'Check for signs of heat stress',
            'priority': 'high',
            'icon': '🌱'
        })
    
    # Weather description based recommendations
    if any(word in weather_description for word in ['rain', 'shower', 'drizzle', 'thunderstorm']):
        tasks.extend([
            {
                'task': 'Check drainage systems and protect from water logging',
                'priority': 'high',
                'icon': '🌧️'
            },
            {
                'task': 'Monitor for fungal diseases due to moisture',
                'priority': 'medium',
                'icon': '🔍'
            }
        ])
    elif any(word in weather_description for word in ['clear', 'sunny']):
        tasks.append({
            'task': 'Check soil moisture and water if needed',
            'priority': 'medium',
            'icon': '☀️'
        })
    elif 'cloud' in weather_description:
        tasks.append({
            'task': 'Ideal conditions for general maintenance',
            'priority': 'medium',
            'icon': '☁️'
        })
    
    # Humidity based recommendations
    if humidity > 80:
        tasks.append({
            'task': 'Monitor for fungal growth and ensure good air circulation',
            'priority': 'high',
            'icon': '💧'
        })
    elif humidity < 30:
        tasks.append({
            'task': 'Consider using humidity trays or misting plants',
            'priority': 'medium',
            'icon': '🌫️'
        })
    
    # Wind speed based recommendations
    if wind_speed > 15:
        tasks.append({
            'task': 'Check plant supports and protect from wind damage',
            'priority': 'high',
            'icon': '💨'
        })
    
    return tasks

if __name__ == "__main__":
    app.run(debug=True)
