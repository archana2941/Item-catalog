# import Flask class from flask library
from flask import Flask

from flask import render_template
# to get data from form import request
from flask import request

# for flash messages
from flask import redirect, url_for, flash

from flask import jsonify



# import CRUD operations
from database_setup import Base, Restaurant, MenuItem, User
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, asc

# this loggin_session works like dictionary.. we can add user's info
from flask import session as login_session

# used to identify each seesion by pseudo-random string
import random, string

# flow_from_clientsecrets method  creates flow object from clientsecrets JSON file
from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError

import httplib2

# to convert to json representation
import json

# make_response method converts the return value from a function
# into real response objects that we can send to our clients
from flask import make_response
import requests


# create instance of Flask class with name of running app.
app = Flask(__name__)

CLIENT_ID = json.loads(
    open('client_secrets.json', 'r').read())['web']['client_id']
APPLICATION_NAME = "Restaurant Menu Application"


# Create session and connect to database
engine = create_engine('sqlite:///restaurantmenuwithusers.db')
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)
session = DBSession()


# Create anti-forgery state token 
# For cross-site request forgery attacker would ahve to guess this code
@app.route('/login')
def showLogin():
    state = ''.join(random.choice(string.ascii_uppercase + string.digits)
                    for x in xrange(32))
    login_session['state'] = state
    # return "The current session state is %s" % login_session['state']
    return render_template('login.html', STATE=state)



@app.route('/gconnect', methods=['POST'])
def gconnect():

    # Validate state token
    # check that the  token the client sent to server matches the token sent by server to client
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Obtain authorization code
    code = request.data

    try:
        # Upgrade the authorization code into a credentials object
        oauth_flow = flow_from_clientsecrets('client_secrets.json', scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:
        response = make_response(
                    json.dumps('Failed to upgrade the authorization code.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Check that the access token is valid.
    access_token = credentials.access_token
    url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s'
           % access_token)

    h = httplib2.Http()
    result = json.loads(h.request(url, 'GET')[1])


    # If there was an error in the access token info, abort.
    if result.get('error') is not None:
        response = make_response(json.dumps(result.get('error')), 500)
        response.headers['Content-Type'] = 'application/json'
        return response


    # Verify that the access token is used for the intended user.
    gplus_id = credentials.id_token['sub']
    if result['user_id'] != gplus_id:
        response = make_response(
                    json.dumps("Token's user ID doesn't match given user ID."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response


    # Verify that the access token is valid for this app.
    if result['issued_to'] != CLIENT_ID:
        response = make_response(
                    json.dumps("Token's client ID does not match app's."), 401)
        print "Token's client ID does not match app's."
        response.headers['Content-Type'] = 'application/json'
        return response

    
    stored_credentials = login_session.get('credentials')
    stored_gplus_id = login_session.get('gplus_id')

    if stored_credentials is not None and gplus_id == stored_gplus_id:
        response = make_response(json.dumps('Current user is already connected.'),
                                 200)
        response.headers['Content-Type'] = 'application/json'
        return response


    # Store the access token in the session for later use.
    login_session['access_token'] = credentials.access_token
    login_session['gplus_id'] = gplus_id


    # Get user info
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    params = {'access_token': credentials.access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)

    data = answer.json()


    # ADD PROVIDER TO LOGIN SESSION
    login_session['provider'] = 'google'
    
    login_session['username'] = data['name']
    login_session['picture'] = data['picture']
    login_session['email'] = data['email']

    

    # see if user exists, if it doesn't make a new one
    user_id = getUserID(data["email"])
    if not user_id:
        user_id = createUser(login_session)
    login_session['user_id'] = user_id

    output = ''
    output += '<h1>Welcome, '
    output += login_session['username']
    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    output += ' " style = "width: 300px; height: 300px;border-radius: 150px;-webkit-border-radius: 150px;-moz-border-radius: 150px;"> '
    flash("You are now LOGGED in as %s" % login_session['username'])
    print "SUCCESSFUL !"
    return output
    


# User Helper Functions

# creates a new user in database
def createUser(login_session):
    newUser = User(name=login_session['username'], email=login_session[
                   'email'], picture=login_session['picture'])
    session.add(newUser)
    session.commit()
    user = session.query(User).filter_by(email=login_session['email']).one()
    return user.id


# returns user object associated with user_id
def getUserInfo(user_id):
    
    user = session.query(User).filter_by(id=user_id).one()
    return user


# return userid if email address belongs to user  stored in database
def getUserID(email):
    try:
        user = session.query(User).filter_by(email=email).one()
        return user.id
    except:
        return None



# DISCONNECT - Revoke a current user's token and reset their login_session
@app.route('/gdisconnect')
def gdisconnect():

    # Only disconnect a connected user.
    credentials = login_session.get('credentials')
    if credentials is None:
        response = make_response(
                json.dumps('Current user not connected.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Execute HTTP get request to revoke current token.    
    access_token = credentials.access_token
    url = 'https://accounts.google.com/o/oauth2/revoke?token=%s' % access_token
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]
    
    if result['status'] != '200':
        # For whatever reason, the given token was invalid.
        response = make_response(
                json.dumps('Failed to revoke token for given user.'), 400)
        response.headers['Content-Type'] = 'application/json'
        return response



# JSON APIs to view Restaurant Information
@app.route('/restaurant/<int:restaurant_id>/menu/JSON')
def restaurantMenuJSON(restaurant_id):
    restaurant = session.query(Restaurant).filter_by(id=restaurant_id).one()
    items = session.query(MenuItem).filter_by(
        restaurant_id=restaurant_id).all()
    # return jsonify class
    return jsonify(MenuItems=[i.serialize for i in items])


# for menu item
@app.route('/restaurant/<int:restaurant_id>/menu/<int:menu_id>/JSON')
def menuItemJSON(restaurant_id, menu_id):
    Menu_Item = session.query(MenuItem).filter_by(id=menu_id).one()
    return jsonify(Menu_Item=Menu_Item.serialize)


# for restaurants
@app.route('/restaurant/JSON')
def restaurantsJSON():
    restaurants = session.query(Restaurant).all()
    return jsonify(restaurants=[r.serialize for r in restaurants])


# Show all restaurants
@app.route('/')
@app.route('/restaurant/')
def showRestaurants():
    restaurants = session.query(Restaurant).order_by(asc(Restaurant.name))

    #if not logged-in user render publicrestaurants template
    if 'username' not in login_session:
        return render_template('publicrestaurants.html', restaurants=restaurants)
    else:
        return render_template('restaurants.html', restaurants=restaurants)



# Create a new restaurant
@app.route('/restaurant/new/', methods=['GET', 'POST'])
def newRestaurant():
    
    if 'username' not in login_session:
        return redirect('/login')
    
    if request.method == 'POST':
        newRestaurant = Restaurant(name=request.form['name'], user_id=login_session['user_id'])
        session.add(newRestaurant)
        flash('New Restaurant %s Successfully Created' % newRestaurant.name)
        session.commit()
        return redirect(url_for('showRestaurants'))
    else:
        return render_template('newRestaurant.html')



# Delete a restaurant
@app.route('/restaurant/<int:restaurant_id>/delete/', methods=['GET', 'POST'])
def deleteRestaurant(restaurant_id):

    if 'username' not in login_session:
        return redirect('/login')
    
    restaurantToDelete = session.query(Restaurant).filter_by(id=restaurant_id).one()

    # if not logged-in user, don't allow to delete restaurants
    if restaurantToDelete.user_id != login_session['user_id']:
        return "<script>function myFunction() {alert('You are not authorized to delete this restaurant. Please create your own restaurant in order to delete.');}</script><body onload='myFunction()''>"

    if not restaurantToDelete:
        return redirect('/')

    if request.method == 'POST':
        session.delete(restaurantToDelete)
        flash('%s Successfully Deleted' % restaurantToDelete.name)
        session.commit()
        return redirect(url_for('showRestaurants', restaurant_id=restaurant_id))
    else:
        return render_template('deleteRestaurant.html', restaurant=restaurantToDelete)



# Edit a restaurant
@app.route('/restaurant/<int:restaurant_id>/edit/', methods=['GET', 'POST'])
def editRestaurant(restaurant_id):

    if 'username' not in login_session:
        return redirect('/login')
    
    editedRestaurant = session.query(Restaurant).filter_by(id=restaurant_id).one()

    # if not current user-> don't allow access to edit
    if editedRestaurant.user_id != login_session['user_id']:
        return "<script>function myFunction() {alert('You are not authorized to edit this restaurant.');}</script><body onload='myFunction()''>"

    if not editedRestaurant:
        return redirect('/')

    if request.method == 'POST':
        if request.form['name']:
            editedRestaurant.name = request.form['name']
            flash('Restaurant Successfully Edited %s' % editedRestaurant.name)
            return redirect(url_for('showRestaurants'))
    else:
        return render_template('editRestaurant.html', restaurant=editedRestaurant)



# Show a restaurant menu
@app.route('/restaurant/<int:restaurant_id>/')
@app.route('/restaurant/<int:restaurant_id>/menu/')
def showMenu(restaurant_id):
    
    restaurant = session.query(Restaurant).filter_by(id=restaurant_id).one()

    if not restaurant:
        return redirect('/')

    # who is the  creator of the current restaurant whoes menu item user is looking at!
    creator = getUserInfo(restaurant.user_id)
    items = session.query(MenuItem).filter_by(
        restaurant_id=restaurant_id).all()

    if not items:
        return redirect('/')
    
    if 'username' not in login_session or creator.id != login_session['user_id']:
        return render_template('publicmenu.html', items=items, restaurant=restaurant, creator=creator)
    else:
        return render_template('menu.html', items=items, restaurant=restaurant, creator=creator)


# Create a route for new menu item
@app.route('/restaurant/<int:restaurant_id>/menu/new/', methods=['GET', 'POST'])
def newMenuItem(restaurant_id):
    # if user not logged-in redirect to login page to coontinue further
    if 'username' not in login_session:
        return redirect('/login')
    
    restaurant = session.query(Restaurant).filter_by(id=restaurant_id).one()
    if not restaurant:
        return redirect('/')
    
    # don't give INSERT access
    if login_session['user_id'] != restaurant.user_id:
        return "<script>function myFunction() {alert('You are not authorized to add menu items to this restaurant. ');}</script><body onload='myFunction()''>"
        
        if request.method == 'POST':
            # extract name,price etc fields from form using request.form
            newItem = MenuItem(name=request.form['name'], description=request.form['description'], price=request.form[
                               'price'], course=request.form['course'], restaurant_id=restaurant_id, user_id=restaurant.user_id)
            session.add(newItem)
            session.commit()
            flash('New Menu %s Item Successfully Created' % (newItem.name))

            # to redirect back to users' page
            return redirect(url_for('showMenu', restaurant_id=restaurant_id))
        
    else:
        return render_template('newmenuitem.html', restaurant_id=restaurant_id)



# Delete a menu item
@app.route('/restaurant/<int:restaurant_id>/menu/<int:menu_id>/delete', methods=['GET', 'POST'])
def deleteMenuItem(restaurant_id, menu_id):
    if 'username' not in login_session:
        return redirect('/login')
    restaurant = session.query(Restaurant).filter_by(id=restaurant_id).one()

    if not restaurant:
        return redirect('/')
    
    itemToDelete = session.query(MenuItem).filter_by(id=menu_id).one()
    if login_session['user_id'] != restaurant.user_id:
        return "<script>function myFunction() {alert('You are not authorized to delete menu items to this restaurant. ');}</script><body onload='myFunction()''>"

    if not itemToDelete:
        return redirect('/')
    
    if request.method == 'POST':
        session.delete(itemToDelete)

        # after delete operation commit the changes
        session.commit()
        flash('Menu Item Successfully Deleted')
        return redirect(url_for('showMenu', restaurant_id=restaurant_id))
    else:
        return render_template('deleteMenuItem.html', item=itemToDelete)
    


# Edit a menu item
@app.route('/restaurant/<int:restaurant_id>/menu/<int:menu_id>/edit', methods=['GET', 'POST'])
def editMenuItem(restaurant_id, menu_id):
    
    if 'username' not in login_session:
        return redirect('/login')
    
    editedItem = session.query(MenuItem).filter_by(id=menu_id).one()
    restaurant = session.query(Restaurant).filter_by(id=restaurant_id).one()

    if not restaurant:
        return redirect('/')
        
    if login_session['user_id'] != restaurant.user_id:
        return "<script>function myFunction() {alert('You are not authorized to edit menu items to this restaurant. ');}</script><body onload='myFunction()''>"

    if not editedItem:
        return redirect('/')
    
    if request.method == 'POST':
        if request.form['name']:
            editedItem.name = request.form['name']
        if request.form['description']:
            editedItem.description = request.form['description']
        if request.form['price']:
            editedItem.price = request.form['price']
        if request.form['course']:
            editedItem.course = request.form['course']
        session.add(editedItem)
        session.commit()
        flash('Menu Item Successfully Edited')
        return redirect(url_for('showMenu', restaurant_id=restaurant_id))
    else:
        return render_template('editmenuitem.html', restaurant_id=restaurant_id, menu_id=menu_id, item=editedItem)



# Disconnect based on provider
@app.route('/disconnect')
def disconnect():
    
    if 'provider' in login_session:
        if login_session['provider'] == 'google':
            gdisconnect()
            del login_session['gplus_id']
            del login_session['credentials']
            
        del login_session['username']
        del login_session['email']
        del login_session['picture']
        del login_session['user_id']
        del login_session['provider']
        # display log out message
        flash("You have successfully been logged out.")
        return redirect(url_for('showRestaurants'))
    else:
        flash("You were not logged in")
        return redirect(url_for('showRestaurants'))


if __name__ == '__main__':
    app.secret_key = 'super_secret_key'
    app.debug = True
    app.run(host='0.0.0.0', port=5000)
