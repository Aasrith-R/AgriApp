from flask import Blueprint, render_template, request, flash, redirect, url_for
from models import db
from models import User
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, current_user
auth = Blueprint('auth', __name__)



@auth.route('/signup', methods = ['GET', 'POST'])
def signup():
    #chekcs if user filled ouut signup forms
    if request.method == 'POST':
        email = request.form.get('email')
        first_name = request.form.get('firstName')
        password1 = request.form.get('password1')
        password2 = request.form.get('password2')

        print(email + first_name + password1)
        user = User.query.filter_by(email=email).first()
        print("User found in db", user)
        print(type(user))
        print("HELLO")
        if not user:
            new_user = User(email=email, first_name=first_name, password=generate_password_hash(password1, method='pbkdf2:sha256'))
            db.session.add(new_user)
            db.session.commit()
            print("IN DATABASE")
            flash('Account created!', category='success')
            return redirect(url_for('auth.login'))
        #debugging through error handling
        else:
            print('s')
            print("ERROR")
    return render_template('signup.html') 


@auth.route('/login', methods = ['GET', 'POST'])
def login():
    #chekcs if user filled out loging forms
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        #checks the user related details
        user = User.query.filter_by(email=email).first()
        if user:
            if check_password_hash(user.password, password):   
                flash('logged in, succesfully!', category ='success')
                print('LOGGED IN!!!')
                login_user(user, remember=True)
                return redirect(url_for('logedin'))
            #debugging error handling
            else:
                print("ERROR")
    return render_template('login.html', user=current_user)