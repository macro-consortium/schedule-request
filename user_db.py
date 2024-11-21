import sqlite3
import bcrypt

# Function to connect to the database
def connect_db():
    connection = sqlite3.connect("./user_data.db")
    return connection

# Function to create the users table
def create_users_table(cursor):
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        email TEXT UNIQUE,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        institution TEXT,
        observer_code TEXT UNIQUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)


# Function to hash a password
def hash_password(password):
    # Generate a salt and hash the password
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed


# Function to validate a password
def check_password(password, hashed):
    # Check if the password matches the hash
    return bcrypt.checkpw(password.encode('utf-8'), hashed)


def generate_observer_code(institution_code, first_name, last_name, existing_codes):
    # Generate a unique observer code based on the institution and user's name
    base_code = institution_code + first_name[0].lower() + last_name[0].lower()  # Example: "IRM"
    code = base_code

    # Resolve conflicts using alternate letters or slight variations
    counter = 1
    while code in existing_codes:
        if counter < len(first_name):  # Use an additional letter from the first name
            code = institution_code + first_name[counter].lower() + last_name[0].lower()
        elif counter < len(last_name):  # Use an additional letter from the last name
            code = institution_code + first_name[0].lower() + last_name[counter].lower()
        else:  # Fallback: Shift to a variation based on alphabet
            code = institution_code + chr(65 + (counter % 26)) + last_name[0].lower()
        counter += 1

    return code


# Function to add a new user
def add_user(connection, username, password, email, institution, first_name, last_name):
    try:
        hashed_password = hash_password(password)

        # Fetch the static institution code
        cursor = connection.cursor()
        cursor.execute("SELECT code FROM institutions WHERE name = ?", (institution,))
        institution_code = cursor.fetchone()[0]

        # Generate observer code
        cursor.execute("SELECT observer_code FROM users;")
        existing_codes = {row[0] for row in cursor.fetchall() if row[0]}  # Collect existing codes
        observer_code = generate_observer_code(institution_code, first_name, last_name, existing_codes)

        # Insert the user into the database
        cursor.execute("""
        INSERT INTO users (username, password_hash, email, first_name, last_name, institution, observer_code) 
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (username, hashed_password, email, first_name, last_name, institution, observer_code))
        connection.commit()
        print(f"User '{first_name} {last_name}' added successfully with institution '{institution}' and observer code '{observer_code}'.")
    except sqlite3.IntegrityError as e:
        print(f"Error adding user: {e}")


def validate_user_by_identifier(connection, identifier):
    cursor = connection.cursor()
    cursor.execute("""
    SELECT * FROM users WHERE username = ? OR email = ?;
    """, (identifier, identifier))
    return cursor.fetchone()  # Returns the user record or None if not found


def login_user(connection, identifier, password):
    user = validate_user_by_identifier(connection, identifier)
    if user:
        stored_hash = user[2]  # The password hash is in the 3rd column
        first_name = user[4]  # The first_name is in the 5th column
        if check_password(password, stored_hash):
            print(f"Login successful. Welcome, {first_name}!")
            return True    
    print("Login attempt failed: Invalid username/email or password.")
    return False
   

def initiate_password_reset(connection, identifier):
    user = validate_user_by_identifier(connection, identifier)
    if user:
        first_name = user[4]  # The first_name is in the 5th column
        print(f"Hello, {first_name}. Let's reset your password.")
        return user
    else:
        print("No account found with that username or email.")
        return None


def reset_password(connection, user_id, new_password):
    hashed_password = hash_password(new_password)  # Hash the new password
    cursor = connection.cursor()
    cursor.execute("""
    UPDATE users 
    SET password_hash = ? 
    WHERE user_id = ?;
    """, (hashed_password, user_id))
    connection.commit()
    print("Password reset successfully.")


def create_institutions_table(connection):
    cursor = connection.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS institutions (
        institution_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        code TEXT NOT NULL UNIQUE  -- Single-letter code for the institution
    );
    """)
    connection.commit()
    print("Institutions table created.")


def populate_institutions(connection):
    institutions = [
        ("Macalester College", "m"),
        ("Augustana College", "a"),
        ("Coe College", "c"),
        ("Knox College", "k"),
        ("The University of Iowa", "i"),
        ("External/Other", "x")
    ]
    cursor = connection.cursor()
    try:
        cursor.executemany("""
        INSERT INTO institutions (name, code) VALUES (?, ?)
        """, institutions)
        connection.commit()
        print("Institutions table populated.")
    except sqlite3.IntegrityError:
        print("Institutions already populated.")


def list_institutions(connection):
    cursor = connection.cursor()
    cursor.execute("SELECT name, code FROM institutions;")
    institutions = cursor.fetchall()
    if institutions:
        print("Available Institutions:")
        for name, code in institutions:
            print(f"- {name} (Code: {code})")
    else:
        print("No institutions found.")


def get_institutions(connection):
    cursor = connection.cursor()
    cursor.execute("SELECT name FROM institutions;")
    return [row[0] for row in cursor.fetchall()]  # Returns a list of institution names
