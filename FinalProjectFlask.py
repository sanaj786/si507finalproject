from flask import Flask, render_template, request
import json
import requests
import plotly
from plotly.graph_objs import Pie, Bar, Layout
from bs4 import BeautifulSoup
import sqlite3

app = Flask(__name__)

API_KEY = 'KxdZAnLvP7gUaZ94zoCW5bvcN5h5hmAZTR802Xo6k0vdE4aNiu-DfAIjpSgDdvq7j1zdBNc_G7pFY0BNJNxMwqf1ydszdWdVz7DZpRS1Q58ksF84CJT7QIkRea6DXnYx'
headers = {'Authorization': 'Bearer %s' % API_KEY}
BASE_URL = 'https://api.yelp.com/v3/businesses/search'
CACHE_FILENAME = 'cachefile.json'

prices = ['$', '$$', '$$$', '$$$$']
restaurants = []
method = ''
imageMethod = ''
CACHED_DICT = {}
userdetails = []


class Restaurant:
    def __init__(self, name, rating, price, address, zip_code, phone, url, image_urls):
        self.name = name
        self.rating = rating
        self.price = price
        self.address = address
        self.zip_code = zip_code
        self.phone = phone
        self.url = url
        self.image_urls = image_urls


@app.route('/')
def index():
    '''Redirect to login page for the application

    Parameters
    ----------
    None

    Returns
    -------
    render_template: HTML page
    '''
    return render_template('login.html')


@app.route('/login', methods=['POST'])
def home():
    '''Checks login info entered by the user and enters home page with username and location or shows error msg if the credentials are incorrect

    Parameters
    ----------
    Data from HTML Form

    Returns
    -------
    render_template: HTML page
    '''
    if checkLogin(request.form.get('username'), request.form.get('password')):
        global userdetails
        userdetails = getUserDetails(request.form.get('username'))
        return render_template('index.html', username=userdetails[0][0], loc=userdetails[0][1])
    return render_template('login.html', error="Invalid Credentials")


@app.route('/home')
def searchAgain():
    '''Return to home page and repopulate the page

    Parameters
    ----------
    None

    Returns
    -------
    render_template: HTML page
    '''
    return render_template('index.html', username=userdetails[0][0], loc=userdetails[0][1])


@app.route('/create', methods=['POST'])
def addAccount():
    '''Add user to login database and show error if user already exists

    Parameters
    ----------
    Data from HTML form

    Returns
    -------
    render_template: HTML page
    '''
    connection = sqlite3.connect("login.sqlite")
    cursor = connection.cursor()
    try:
        query = "insert into login values (\"" + request.form.get('name') + "\",\"" + request.form.get(
            'username') + "\",\"" + request.form.get('password') + "\",\"" + request.form.get('location') + "\")"
        cursor.execute(query)
        connection.commit()
        connection.close()
    except:
        return render_template('login.html', error2="User already exists")
    return render_template('login.html')


@app.route('/sendData', methods=['POST'])
def sendData():
    '''Create param dict to get data of restaurants

    Parameters
    ----------
    Data from HTML form

    Returns
    -------
    render_template: HTML page
    '''
    loc = request.form.get('Location')
    term = request.form.get('Term')
    price = request.form.getlist('Price')
    attributes = request.form.getlist('Attribute')
    param = {'location': loc, 'term': term,
             'price': ','.join([str(elem) for elem in price]) if len(price) > 0 else '1,2,3,4',
             'attributes': ','.join([str(elem) for elem in attributes]), 'limit': 5}
    del restaurants[:]
    try:
        getData(param)
        return render_template('results.html', restaurants=restaurants, method=method, imageMethod=imageMethod)
    except:
        return render_template('index.html', restaurants=restaurants, method=method, imageMethod=imageMethod, error="Invalid parameters")


@app.route('/prices')
def showPieChart():
    '''
    Display pie chart showing the distribution of prices among restaurants

    Parameters
    ----------
    None

    Returns
    -------
    HTML Page
    '''
    print('Plotting pie chart...')
    plotly.offline.plot({
        "data": [Pie(labels=prices, values=getPriceValues())],
        "layout": Layout(title="Prices")
    })
    return render_template('results.html', restaurants=restaurants, method=method)


@app.route('/ratings')
def showBarChart():
    '''Display bar chart showing the trend of rating for restaurants

    Parameters
    ----------
    None

    Returns
    -------
    HTML Page
    '''
    print('Plotting bar graph...')
    plotly.offline.plot({
        "data": [Bar(x=getNameArray(), y=getRatingArray())],
        "layout": Layout(title="Rating")
    })
    return render_template('results.html', restaurants=restaurants, method=method)


def getRatingArray():
    '''Calculate array of ratings for all restaurants to be used in bar chart formation

    Parameters
    ----------
    None

    Returns
    -------
    allRatings: list
    '''
    allRatings = []
    for i in range(len(restaurants)):
        allRatings.append(restaurants[i].rating)
    return allRatings


def getNameArray():
    '''Calculate array of names for all restaurants to be used in bar chart formation

    Parameters
    ----------
    None

    Returns
    -------
    allNames: list
    '''
    allNames = []
    for i in range(len(restaurants)):
        allNames.append(restaurants[i].name)
    return allNames


def getPriceValues():
    '''Count value for each price value

    Parameters
    ----------
    None

    Returns
    -------
    values: list
    '''
    values = [0, 0, 0, 0]
    for i in range(len(restaurants)):
        values[prices.index(restaurants[i].price)] += 1
    return values


def checkDataInCache(params):
    '''Check cache file for data based on given params

    Parameters
    ----------
    params: dict

    Returns
    -------
    list
    '''
    try:
        cache_file = open(CACHE_FILENAME, 'r')
        cache_contents = cache_file.read()
        cache_dict = json.loads(cache_contents)
        if json.dumps(params) in cache_dict.keys():
            print("Getting data from cache.........")
            global method
            method = 'CACHE'
            return cache_dict[json.dumps(params)]
        cache_file.close()
    except:
        return None


def getData(params):
    '''Get restaurant list based on the params from either new API call or cache

    Parameters
    ----------
    params: dict

    Returns
    -------
    None
    '''
    data = checkDataInCache(params)
    if data is None:
        data = getDataFromAPI(params)
    createRestrauntArray(data)


def addDataToCache():
    '''Add data for restaurants for current params to cache file

    Parameters
    ----------
    None

    Returns
    -------
    None
    '''
    dumped_json_cache = json.dumps(CACHED_DICT)
    fw = open(CACHE_FILENAME, "w")
    fw.write(dumped_json_cache)
    fw.close()


def getDataFromAPI(params):
    '''Get restaurant list based on the params from new API call

    Parameters
    ----------
    params: dict

    Returns
    -------
    allRestaurants: list
    '''
    print("Fetching from API.........")
    global method
    method = 'API'
    allRestaurants = json.loads(requests.get(BASE_URL, params=params, headers=headers).text)['businesses']
    CACHED_DICT[json.dumps(params)] = allRestaurants
    addDataToCache()
    return allRestaurants


def createRestrauntArray(allRestaurants):
    '''Create Restaurant array and add to restaurants list for all restaurants based

    Parameters
    ----------
    allRestaurants: dict

    Returns
    -------
    None
    '''
    for i in range(len(allRestaurants)):
        address = str(allRestaurants[i]['location']['address1']) + ", " + str(
            allRestaurants[i]['location']['address2']) + ", " + \
                  str(allRestaurants[i]['location']['address3'])
        mUrl = getImages(allRestaurants[i]['id'], allRestaurants[i]['url'])
        restaurant = Restaurant(allRestaurants[i]['name'], allRestaurants[i]['rating'], allRestaurants[i]['price'],
                                address, allRestaurants[i]['location']['zip_code'], allRestaurants[i]['display_phone'],
                                allRestaurants[i]['url'], mUrl)
        saveRestaurantToDatabase(allRestaurants[i]['id'], restaurant)
        restaurants.append(restaurant)


def checkLogin(username, password):
    '''Validate username and password tuple from database

    Parameters
    ----------
    username: str
    password: str

    Returns
    -------
    bool
    '''
    connection = sqlite3.connect("login.sqlite")
    cursor = connection.cursor()
    query = "SELECT Password FROM login where Username=\"" + username + "\""
    result = cursor.execute(query).fetchall()
    connection.close()
    try:
        if result[0][0] == password:
            return True
        else:
            return False
    except:
        return False


def getUserDetails(username):
    '''Get username and location for current user

    Parameters
    ----------
    username: str

    Returns
    -------
    result: list
    '''
    connection = sqlite3.connect("login.sqlite")
    cursor = connection.cursor()
    query = "SELECT Name, Location from login where Username = \"" + username + "\""
    result = cursor.execute(query).fetchall()
    connection.close()
    return result


def getImages(rId, url):
    global imageMethod
    imageUrls = getImagesFromDatabase(rId)
    if imageUrls is not None:
        print("Getting images from database...")
        imageMethod = 'DATABASE'
        return imageUrls
    print("Getting images using crawling...")
    imageMethod = 'CRAWLING'
    return getImagesFromCrawling(rId, url)


def getImagesFromDatabase(rId):
    try:
        connection = sqlite3.connect("login.sqlite")
        cursor = connection.cursor()
        query = "SELECT ImageUrls from images where restaurantId = \"" + rId + "\""
        result = cursor.execute(query).fetchall()
        imageUrls = result[0][0].split(';')
        connection.close()
        return imageUrls
    except:
        return None


def saveImagesToDatabase(rId, urls):
    connection = sqlite3.connect("login.sqlite")
    cursor = connection.cursor()
    query = "insert into images values (\"" + rId + "\",\"" + urls + "\")"
    cursor.execute(query)
    connection.commit()
    connection.close()
    return None


def saveRestaurantToDatabase(rId, restaurant):
    connection = sqlite3.connect("login.sqlite")
    cursor = connection.cursor()
    query = "select * from restaurants where id=\""+rId+"\""
    result = cursor.execute(query).fetchall()
    if len(result) < 1:
        insertQuery = "insert into restaurants values (\"{rid}\",\"{name}\",\"{rating}\",\"{price}\",\"{address}\",\"{zip_code}\",\"{phone}\",\"{url}\")".format(rid=rId,name=restaurant.name,rating=restaurant.rating,price=restaurant.price,address=restaurant.address,zip_code=restaurant.zip_code,phone=restaurant.phone,url=restaurant.url)
        cursor.execute(insertQuery)
        connection.commit()
    connection.close()


def getImagesFromCrawling(rId, url):
    imageUrls = []
    html_content = BeautifulSoup(requests.get(url).text, 'html.parser')
    images = html_content.find_all('img', attrs={'class': 'lemon--img__373c0__3GQUb'})
    for i in range(10, 15):
        imageUrls.append(images[i].get('src'))
    saveImagesToDatabase(rId, ';'.join([str(elem) for elem in imageUrls]))
    return imageUrls


if __name__ == '__main__':
    app.run()
