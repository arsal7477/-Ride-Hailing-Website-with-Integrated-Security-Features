import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

def init_db():
    conn = sqlite3.connect('ride_hailing.db')
    c = conn.cursor()

    # Create users table if it doesn't exist
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                 email TEXT UNIQUE NOT NULL,
                 password TEXT NOT NULL,
                 name TEXT NOT NULL,
                 role TEXT NOT NULL CHECK(role IN ('user', 'driver', 'admin')),
                 available BOOLEAN DEFAULT 1,
                 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

    # Create rides table with all required fields
    c.execute('''CREATE TABLE IF NOT EXISTS rides
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                 user_id INTEGER NOT NULL,
                 driver_id INTEGER,
                 vehicle_type TEXT NOT NULL,
                 passengers INTEGER NOT NULL,
                 pickup TEXT NOT NULL,
                 dropoff TEXT NOT NULL,
                 distance REAL NOT NULL,
                 fare REAL NOT NULL,
                 status TEXT NOT NULL CHECK(status IN ('pending', 'assigned', 'in_progress', 'completed', 'cancelled')),
                 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                 assigned_at TIMESTAMP,
                 started_at TIMESTAMP,
                 completed_at TIMESTAMP,
                 FOREIGN KEY(user_id) REFERENCES users(id),
                 FOREIGN KEY(driver_id) REFERENCES users(id))''')

    c.execute('''CREATE TABLE IF NOT EXISTS payments
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                 ride_id INTEGER NOT NULL,
                 amount REAL NOT NULL,
                 method TEXT NOT NULL,
                 transaction_id TEXT,
                 status TEXT DEFAULT 'pending',
                 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                 FOREIGN KEY(ride_id) REFERENCES rides(id))''')
    
    # Create indexes for better performance on history queries
    c.execute('''CREATE INDEX IF NOT EXISTS idx_rides_user_id ON rides(user_id)''')
    c.execute('''CREATE INDEX IF NOT EXISTS idx_rides_created_at ON rides(created_at)''')
    c.execute('''CREATE INDEX IF NOT EXISTS idx_rides_status ON rides(status)''')

    # Insert admin user if not exists
    try:
        hashed_pw = generate_password_hash('admin123')
        c.execute("INSERT INTO users (email, password, name, role) VALUES (?, ?, ?, ?)",
                  ('admin@example.com', hashed_pw, 'Admin User', 'admin'))
    except sqlite3.IntegrityError:
        pass

    # Insert sample driver if none exists (for testing)
    try:
        hashed_pw = generate_password_hash('driver123')
        c.execute("INSERT INTO users (email, password, name, role) VALUES (?, ?, ?, ?)",
                  ('driver@example.com', hashed_pw, 'Sample Driver', 'driver'))
    except sqlite3.IntegrityError:
        pass

    conn.commit()
    conn.close()

def hash_password(password):
    """Hash a password for storing."""
    return generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)

def verify_password(hashed_password, password):
    """Verify a stored password against one provided by user"""
    return check_password_hash(hashed_password, password)

def get_db_connection():
    """Get a database connection with row factory"""
    conn = sqlite3.connect('ride_hailing.db')
    conn.row_factory = sqlite3.Row
    return conn

def get_user_rides(user_id, limit=None):
    """Get ride history for a specific user"""
    conn = get_db_connection()
    query = '''
        SELECT r.*, u.name as driver_name 
        FROM rides r
        LEFT JOIN users u ON r.driver_id = u.id
        WHERE r.user_id = ?
        ORDER BY r.created_at DESC
    '''
    if limit:
        query += f' LIMIT {limit}'
    
    rides = conn.execute(query, (user_id,)).fetchall()
    conn.close()
    return rides

def get_ride_details(ride_id):
    """Get complete details for a specific ride"""
    conn = get_db_connection()
    ride = conn.execute('''
        SELECT r.*, u.name as user_name, d.name as driver_name
        FROM rides r
        JOIN users u ON r.user_id = u.id
        LEFT JOIN users d ON r.driver_id = d.id
        WHERE r.id = ?
    ''', (ride_id,)).fetchone()
    conn.close()
    return ride