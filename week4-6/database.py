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
                 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

    # Add 'available' column if it doesn't exist
    c.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in c.fetchall()]
    if 'available' not in columns:
        c.execute("ALTER TABLE users ADD COLUMN available BOOLEAN DEFAULT 1")

    # Create or update rides table
    c.execute("""
        CREATE TABLE IF NOT EXISTS rides (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            FOREIGN KEY(driver_id) REFERENCES users(id)
        )
    """)

    # Add admin user if not exists
    try:
        hashed_pw = generate_password_hash('admin123')
        c.execute("INSERT INTO users (email, password, name, role) VALUES (?, ?, ?, ?)",
                  ('admin@example.com', hashed_pw, 'Admin User', 'admin'))
    except sqlite3.IntegrityError:
        pass

    conn.commit()
    conn.close()

def hash_password(password):
    return generate_password_hash(password, method='pbkdf2:sha256')

def verify_password(hashed_password, password):
    return check_password_hash(hashed_password, password)
