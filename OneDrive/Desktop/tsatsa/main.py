from flask import Flask, render_template
from flask_login import LoginManager, login_required
from models import User, db
from auth import auth


DB_NAME = "database.db"

app = Flask(__name__)
app.config['SECRET_KEY'] = 'TSA'
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_NAME}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
app.register_blueprint(auth, url_prefix='/')

with app.app_context():
    db.create_all()
    
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.init_app(app)


@login_manager.user_loader
def load_user(id):
    # return User.query.get(int(id))
    return User.query.get(int(id))

@app.route("/a")
@login_required
def logedin():
    return render_template('test.html')

@app.route("/")
def check():
    return render_template('base.html')

# @app.route("/login")
# def login():
#     return render_template('login.html')


# @app.route("/signup")
# def signup():
#     return render_template('signup.html')

if __name__ == "__main__":
    app.run(debug=True)
