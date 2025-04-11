from flask import Flask, render_template, request, redirect, url_for, session, flash
from database import init_db, hash_password, verify_password
from mapbox import Geocoder
import sqlite3
import os
import requests
import json

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY') or os.urandom(24)
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Initialize database
init_db()

# Mapbox setup
MAPBOX_ACCESS_TOKEN = 'pk.eyJ1IjoiYXJzYWw3NDc3IiwiYSI6ImNtOWJxa3gzbzBmenUya3F4d29sMGF1YTcifQ.N8QJTpKMo4fxh9vm_tGO-g'
geocoder = Geocoder(access_token=MAPBOX_ACCESS_TOKEN)

def geocode_location(location_text):
    try:
        response = geocoder.forward(location_text)
        if response.status_code == 200:
            features = response.geojson()['features']
            if features:
                coords = features[0]['geometry']['coordinates']
                print(f"Geocoded {location_text} to coordinates: {coords[1]}, {coords[0]}")  # Logging coordinates
                return coords[1], coords[0]  # Mapbox returns (lon, lat), we need (lat, lon)
        print(f"Geocoding failed for {location_text}")
        return None
    except Exception as e:
        print(f"Geocoding error: {e}")
        return None

def calculate_real_distance(pickup, dropoff):
    pickup_coords = geocode_location(pickup)
    dropoff_coords = geocode_location(dropoff)
    if not pickup_coords or not dropoff_coords:
        raise ValueError("Could not geocode one or both locations")

    # Mapbox Directions API expects coordinates in the format longitude,latitude
    coord_string = f"{pickup_coords[1]},{pickup_coords[0]};{dropoff_coords[1]},{dropoff_coords[0]}"
    url = f"https://api.mapbox.com/directions/v5/mapbox/driving/{coord_string}?access_token={MAPBOX_ACCESS_TOKEN}&overview=false"

    try:
        response = requests.get(url)
        data = response.json()
        if response.status_code == 200 and data['routes']:
            # Distance is in meters, convert to kilometers
            distance_km = data['routes'][0]['distance'] / 1000
            print(f"Mapbox driving distance: {distance_km:.2f} km")  # Log the driving distance
            return distance_km
        else:
            raise Exception("No route found")
    except Exception as e:
        print(f"Direction API error: {e}")
        raise ValueError("Could not retrieve real distance from Mapbox Directions API")

def calculate_fare(vehicle_type, distance_km):
    rates = {
        'bike': {'base': 50, 'per_km': 15, 'min_fare': 70},
        'car': {'base': 120, 'per_km': 25, 'min_fare': 150},
        'van': {'base': 200, 'per_km': 35, 'min_fare': 250}
    }
    config = rates[vehicle_type]
    fare = config['base'] + (distance_km * config['per_km'])
    return max(fare, config['min_fare'])

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.before_request
def require_login():
    allowed_routes = ['index', 'login', 'register', 'static']
    if request.endpoint not in allowed_routes and 'user_id' not in session:
        return redirect(url_for('login'))

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
        role = 'user'

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

    # Provide the Mapbox access token to the template for rendering the map
    return render_template('rides/home.html', rides=rides, MAPBOX_ACCESS_TOKEN=MAPBOX_ACCESS_TOKEN)

@app.route('/confirm-ride', methods=['POST'])
def confirm_ride():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        vehicle_type = request.form.get('vehicle_type')
        pickup = request.form.get('pickup', '').strip()
        dropoff = request.form.get('dropoff', '').strip()
        passengers = int(request.form.get('passengers', 1))
        distance_km = float(request.form.get('calculated_distance', 0))
        
        # Validate inputs
        if not pickup or not dropoff:
            flash('Please enter both locations', 'danger')
            return redirect(url_for('dashboard'))
        
        if distance_km <= 0:
            flash('Invalid distance calculated. Please reselect your locations.', 'danger')
            return redirect(url_for('dashboard'))
        
        if vehicle_type not in ['bike', 'car', 'van']:
            flash('Invalid vehicle type selected', 'danger')
            return redirect(url_for('dashboard'))
        
        # Calculate fare using the distance from home page
        fare = calculate_fare(vehicle_type, distance_km)
        
        # Store in session without distance (since we're not showing it)
        session['pending_ride'] = {
            'vehicle_type': vehicle_type,
            'pickup': pickup,
            'dropoff': dropoff,
            'passengers': passengers,
            'fare': fare  # Only storing fare, not distance
        }
        
        return render_template('rides/confirmation.html',
                            vehicle_type=vehicle_type,
                            pickup=pickup,
                            dropoff=dropoff,
                            passengers=passengers,
                            fare=f"PKR {fare:.2f}")  # Removed distance display
        
    except ValueError as e:
        print(f"Invalid input: {e}")
        flash('Invalid input values. Please try again.', 'danger')
        return redirect(url_for('dashboard'))
    except Exception as e:
        print(f"Unexpected error: {e}")
        flash('An error occurred while processing your ride.', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/finalize-ride', methods=['POST'])
def finalize_ride():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    try:
        # Get the pending ride details from session
        ride_details = session.get('pending_ride')
        if not ride_details:
            flash('No ride to confirm. Please book again.', 'danger')
            return redirect(url_for('dashboard'))

        # Connect to database
        conn = sqlite3.connect('ride_hailing.db')
        c = conn.cursor()

        # Insert the ride into database
        c.execute("""
            INSERT INTO rides 
            (user_id, vehicle_type, passengers, pickup, dropoff, distance, fare, status) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session['user_id'],
                ride_details['vehicle_type'],
                ride_details['passengers'],
                ride_details['pickup'],
                ride_details['dropoff'],
                ride_details.get('distance', 0),  # Using 0 if distance not stored
                ride_details['fare'],
                'pending'  # Initial status
            ))
        
        ride_id = c.lastrowid
        conn.commit()
        
        # Clear the pending ride from session
        session.pop('pending_ride', None)
        
        # Find available drivers (simplified example)
        c.execute("""
            SELECT id, name FROM users 
            WHERE role = 'driver' AND available = 1
            ORDER BY RANDOM() LIMIT 3
            """)
        available_drivers = c.fetchall()
        conn.close()

        return render_template('rides/driver_selection.html',
                            ride_id=ride_id,
                            drivers=available_drivers,
                            fare=ride_details['fare'])

    except Exception as e:
        print(f"Error finalizing ride: {e}")
        flash('Error completing your booking. Please try again.', 'danger')
        return redirect(url_for('dashboard'))


@app.route('/find-drivers/<int:ride_id>')
def find_drivers(ride_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = sqlite3.connect('ride_hailing.db')
    c = conn.cursor()

    c.execute("SELECT * FROM rides WHERE id = ?", (ride_id,))
    ride = c.fetchone()

    c.execute("""
        SELECT id, name FROM users 
        WHERE role = 'driver' 
        AND id NOT IN (
            SELECT driver_id FROM rides WHERE status = 'accepted'
        )
        LIMIT 3
    """)
    drivers = c.fetchall()
    conn.close()

    return render_template('rides/find_drivers.html',
                           ride=ride,
                           drivers=drivers,
                           ride_id=ride_id)

@app.route('/assign-driver/<int:ride_id>/<int:driver_id>')
def assign_driver(ride_id, driver_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    try:
        conn = sqlite3.connect('ride_hailing.db')
        c = conn.cursor()
        
        # Verify the ride belongs to the current user
        c.execute("SELECT id FROM rides WHERE id = ? AND user_id = ?", 
                 (ride_id, session['user_id']))
        if not c.fetchone():
            flash('Ride not found', 'danger')
            return redirect(url_for('dashboard'))
        
        # Update ride with driver assignment
        c.execute("""
            UPDATE rides SET 
            driver_id = ?,
            status = 'assigned',
            assigned_at = CURRENT_TIMESTAMP
            WHERE id = ? AND status = 'pending'
            """, (driver_id, ride_id))
        
        # Mark driver as unavailable
        c.execute("UPDATE users SET available = 0 WHERE id = ?", (driver_id,))
        
        conn.commit()
        
        # Get details for notification
        c.execute("""
            SELECT r.id, u.name as user_name, d.name as driver_name 
            FROM rides r
            JOIN users u ON r.user_id = u.id
            JOIN users d ON r.driver_id = d.id
            WHERE r.id = ?
            """, (ride_id,))
        
        ride = c.fetchone()
        conn.close()
        
        if ride:
            flash(f'Driver {ride[2]} assigned to your ride!', 'success')
            # Here you would typically send notifications to both user and driver
            return redirect(url_for('ride_status', ride_id=ride_id))
        else:
            flash('Could not assign driver', 'danger')
            return redirect(url_for('dashboard'))

    except Exception as e:
        print(f"Error assigning driver: {e}")
        flash('Error assigning driver', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/ride-status/<int:ride_id>')
def ride_status(ride_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        conn = sqlite3.connect('ride_hailing.db')
        c = conn.cursor()
        
        # Get ride details with driver name
        c.execute("""
            SELECT 
                r.id, r.user_id, r.driver_id, r.vehicle_type, r.passengers,
                r.pickup, r.dropoff, r.distance, r.fare, r.status,
                r.created_at, r.assigned_at, r.started_at, r.completed_at,
                d.name as driver_name
            FROM rides r
            LEFT JOIN users d ON r.driver_id = d.id
            WHERE r.id = ? AND r.user_id = ?
            """, (ride_id, session['user_id']))
        
        ride = c.fetchone()
        conn.close()
        
        if not ride:
            flash('Ride not found', 'danger')
            return redirect(url_for('dashboard'))
        
        # Format timestamps
        ride = list(ride)  # Convert tuple to list to modify
        if ride[10]:  # created_at
            ride[10] = ride[10].strftime('%Y-%m-%d %H:%M')
        if ride[11]:  # assigned_at
            ride[11] = ride[11].strftime('%Y-%m-%d %H:%M')
        if ride[12]:  # started_at
            ride[12] = ride[12].strftime('%Y-%m-%d %H:%M')
        if ride[13]:  # completed_at
            ride[13] = ride[13].strftime('%Y-%m-%d %H:%M')
        
        return render_template('rides/status.html', ride=ride)
    
    except Exception as e:
        print(f"Error fetching ride status: {e}")
        flash('Error loading ride details', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('email', None)
    session.pop('name', None)
    session.pop('role', None)
    flash('You have been logged out', 'info')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
