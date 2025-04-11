from flask import Flask, render_template, request, redirect, url_for, session, flash
from database import init_db, hash_password, verify_password
import sqlite3
import os
import math

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY') or os.urandom(24)
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Initialize database
init_db()

# Fuel prices per km (in PKR)
FUEL_PRICES = {
    'bike': 5,
    'car': 10,
    'van': 15
}

# Vehicle capacities
VEHICLE_CAPACITIES = {
    'bike': 1,
    'car': 4,
    'van': 8
}

# Root route
@app.route('/')
def index():
    return redirect(url_for('login'))

# Security middleware
@app.before_request
def require_login():
    allowed_routes = ['index', 'login', 'register', 'static']
    if request.endpoint not in allowed_routes and 'user_id' not in session:
        return redirect(url_for('login'))

# Authentication routes (unchanged)
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        conn = sqlite3.connect('ride_hailing.db')
        c = conn.cursor()
        c.execute("SELECT id, email, password, name, role FROM users WHERE email = ?", (email,))
        user = c.fetchone()
        conn.close()
        
        if user and verify_password(user[2], password):
            session['user_id'] = user[0]
            session['email'] = user[1]
            session['name'] = user[3]
            session['role'] = user[4]
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password', 'danger')
    return render_template('auth/login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = hash_password(request.form['password'])
        name = request.form['name']
        role = 'user'  # Default role
        
        try:
            conn = sqlite3.connect('ride_hailing.db')
            c = conn.cursor()
            c.execute("INSERT INTO users (email, password, name, role) VALUES (?, ?, ?, ?)",
                     (email, password, name, role))
            conn.commit()
            conn.close()
            flash('Registration successful! Please login', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Email already exists', 'danger')
    return render_template('auth/register.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('ride_hailing.db')
    c = conn.cursor()
    c.execute("SELECT * FROM rides WHERE user_id = ?", (session['user_id'],))
    rides = c.fetchall()
    conn.close()
    
    return render_template('rides/home.html', rides=rides)

def calculate_distance(lat1, lon1, lat2, lon2):
    # Haversine formula to calculate distance between two coordinates
    R = 6371  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat/2) * math.sin(dlat/2) +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon/2) * math.sin(dlon/2))
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

def calculate_fare(vehicle_type, distance_km):
    # Fare = distance × (fuel price + 10 PKR profit)
    return distance_km * (FUEL_PRICES[vehicle_type] + 10)

@app.route('/book-ride', methods=['POST'])
def book_ride():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    vehicle_type = request.form.get('vehicle_type')
    pickup = request.form.get('pickup', '').strip()
    dropoff = request.form.get('dropoff', '').strip()
    passengers = int(request.form.get('passengers', 1))
    
    # Validate inputs
    if not pickup or not dropoff:
        flash('Please enter both locations', 'danger')
        return redirect(url_for('dashboard'))
    
    if vehicle_type not in ['bike', 'car', 'van']:
        flash('Invalid vehicle type selected', 'danger')
        return redirect(url_for('dashboard'))
    
    if passengers < 1 or passengers > VEHICLE_CAPACITIES[vehicle_type]:
        flash(f'Number of passengers exceeds {vehicle_type} capacity', 'danger')
        return redirect(url_for('dashboard'))
    
    # In a real app, we'd get actual coordinates from Mapbox API
    # For demo, we'll use fixed coordinates
    pickup_lat, pickup_lon = 33.6844, 73.0479  # Islamabad coordinates
    dropoff_lat, dropoff_lon = 33.6906, 73.0551  # Nearby location
    
    distance = calculate_distance(pickup_lat, pickup_lon, dropoff_lat, dropoff_lon)
    fare = calculate_fare(vehicle_type, distance)
    
    conn = sqlite3.connect('ride_hailing.db')
    c = conn.cursor()
    c.execute("INSERT INTO rides (user_id, vehicle_type, passengers, pickup, dropoff, distance, fare, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
             (session['user_id'], vehicle_type, passengers, pickup, dropoff, distance, fare, 'requested'))
    conn.commit()
    conn.close()
    
    flash(f'Ride booked successfully! Fare: PKR {fare:.2f}', 'success')
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)