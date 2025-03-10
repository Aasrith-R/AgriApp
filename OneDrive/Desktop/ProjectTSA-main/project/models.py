from flask_login import UserMixin
from sqlalchemy.sql import func
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True)
    password = db.Column(db.String(150))
    first_name = db.Column(db.String(150))
    city_name = db.Column(db.String(100))
    bot = db.relationship('Agri2', backref='user')
    product = db.relationship('Products', backref='user')

class Products(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.String(150), unique=True)
    product_url= db.Column(db.String(150))
    qr_code = db.Column(db.String(200000000000))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
# THIS ONE BELOW
class Products2(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.String(50), unique=True)
    product_name = db.Column(db.String(100))
    variety = db.Column(db.String(100))
    organic_status = db.Column(db.String(50))
    location = db.Column(db.String(100))
    certifications = db.Column(db.Text)
    carbon_footprint = db.Column(db.String(100))
    sustainable_practices = db.Column(db.Text)
    harvest_date = db.Column(db.String(50))
    qr_code = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

class Agri2(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.String(100000000000))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

'''        new_city_name = User(city_name=city_name, user_id=current_user.id)
        db.session.add()
        db.session.commit()
        existing_city_name = User.query.filter_by(user_id=current_user.id).first()
        

        city_name = db.Column(db.String(150))

    #.user dont work cause thats wrong syntax
    while existing_city_name.city_name:
        temperature, humidity, _, wind_speed, precipitation = fetch_weather_data(city_name)
        pm25 = fetch_air_pollution_data(city_name)
        lat, lon = fetch_coordinates(city_name, api_key="b9cd298593ba9f5db898d737ff3107bd")
        times = datetime.now().strftime("%H:%M:%S")
        time.sleep(30 * 60)  # Pause for 30 minutes

        flash("Data retrieved successfully!") if times else flash("Failed to retrieve data.")
'''