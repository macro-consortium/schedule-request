import sqlite3, bcrypt, secrets, logging
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler()])


def create_sessions_table(cursor):
    """
    Create the sessions table to manage active user sessions.

    The sessions table stores information about active user sessions, including the session ID, user ID,
    observer code, creation time, and expiration time.

    Parameters
    ----------
    cursor : :class:`sqlite3.Cursor`
        A cursor object to execute SQL queries.

    Returns
    -------
    None
    """
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        session_id TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        observer_code TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expires_at TIMESTAMP NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
    );
    """)
    logging.info("Sessions table created or already exists.")


def start_session(connection, user_id, duration_minutes=60):
    """
    Start a new session for the user.

    A session is created by generating a session ID, setting the expiration time, and inserting the session

    Parameters
    ----------
    connection : :class:`sqlite3.Connection`
        A connection object to the SQLite database.
    user_id : `int`
        The ID of the user starting the session.
    duration_minutes : `int`, optional
        Duration of the session in minutes. Default is 60 minutes.

    Returns
    -------
    `str`
        The session token.

    Raises
    ------
    `sqlite3.Error`
        If an error occurs during session creation.
    """
    session_id = secrets.token_hex(16)
    expires_at = datetime.now() + timedelta(minutes=duration_minutes)
    cursor = connection.cursor()
    cursor.execute("SELECT observer_code FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    if not result:
        logging.error("Observer code not found for user ID: %d", user_id)
        raise ValueError("Observer code is required to start a session.")
    
    observer_code = result[0]
    
    try:
        cursor.execute("""
        INSERT INTO sessions (session_id, user_id, observer_code, expires_at)
        VALUES (?, ?, ?, ?);
        """, (session_id, user_id, observer_code, expires_at))
        connection.commit()
        logging.info(f"Session started for user ID {user_id}.")
        return session_id
    except sqlite3.Error as e:
        logging.error(f"Error starting session: {e}")
        raise


def validate_session(connection, session_id):
    """
    Validate a session by checking its expiration.

    Parameters
    ----------
    connection : :class:`sqlite3.Connection`
        A connection object to the SQLite database.
    session_id : `str`
        The session token.

    Returns
    -------
    `int`
        The user ID if the session is valid, otherwise `None`.

    Raises
    ------
    `sqlite3.Error`
        If an error occurs during session validation.
    """
    cursor = connection.cursor()
    try:
        cursor.execute("""
        SELECT user_id FROM sessions
        WHERE session_id = ? AND expires_at > CURRENT_TIMESTAMP;
        """, (session_id,))
        result = cursor.fetchone()
        if result:
            logging.info("Session validated successfully.")
            return result[0]
        else:
            logging.warning("Session validation failed.")
            return None
    except sqlite3.Error as e:
        logging.error(f"Error validating session: {e}")
        raise


def end_session(connection, session_id):
    """
    End a user session by deleting it from the database.

    Parameters
    ----------
    connection : :class:`sqlite3.Connection`
        A connection object to the SQLite database.
    session_id : `str`
        The session token to end.

    Returns
    -------
    None

    Raises
    ------
    `sqlite3.Error`
        If an error occurs during session deletion.
    """
    cursor = connection.cursor()
    try:
        cursor.execute("DELETE FROM sessions WHERE session_id = ?;", (session_id,))
        connection.commit()
        logging.info("Session ended successfully.")
    except sqlite3.Error as e:
        logging.error(f"Error ending session: {e}")
        raise


# Function to connect to the database
def connect_db():
    """
    Connect to the SQLite database and return the connection object.

    Returns
    -------
    `sqlite3.Connection`
        A connection object to the SQLite database.

    Raises
    ------
    `sqlite3.Error`
        If an error occurs while connecting to the database.
    """
    connection = sqlite3.connect("./user_data.db")
    return connection

# Function to create the users table
def create_users_table(cursor):
    """
    Create the users table in the database.

    Parameters
    ----------
    `cursor` : `sqlite3.Cursor`
        A cursor object to execute SQL queries.
    
    Returns
    -------
    None

    Raises
    ------
    `sqlite3.Error`
        If an error occurs while executing the SQL query.    
    """
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        password_hash TEXT NOT NULL,
        email TEXT UNIQUE,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        institution TEXT,
        observer_code TEXT UNIQUE,
        user_level TEXT DEFAULT 'novice',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)


# Function to hash a password
def hash_password(password):
    """
    Hash a password using bcrypt.

    Parameters
    ----------
    `password` : `str`
        The password to hash.

    Returns
    -------
    `hashed` : `str`
        The hashed password.

    Raises
    ------
    `ValueError`
        If the password is not a string.
    """
    # Generate a salt and hash the password
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed


# Function to validate a password
def check_password(password, hashed):
    """
    Check if a password matches a given hash.

    Parameters
    ----------
    `password` : `str`
        The password to check.
    `hashed` : `str`
        The hashed password to compare against.

    Returns
    -------
    `bool`
        `True` if the password matches the hash, `False` otherwise.

    Raises
    ------
    `ValueError`
        If the password or hash is not a string.
    """
    # Check if the password matches the hash
    return bcrypt.checkpw(password.encode('utf-8'), hashed)


def generate_observer_code(institution_code, first_name, last_name, existing_codes):
    """
    Generate a unique observer code based on the institution and user's name.

    Generates a unique observer code based on the institution code, first name, and last name of the user.
    The observer code is used to identify the user in the system.
    If a conflict arises with an existing observer code, the function will resolve it by using alternate letters
    from the first name, last name, or slight variations.
    Institution codes will be determined by the institution chosen by the user on sign-up.

    Parameters
    ----------
    `institution_code` : `str`
        A single-letter code representing the institution.
    `first_name` : `str`
        The first name of the user.
    `last_name` : `str`
        The last name of the user.
    `existing_codes` : `set`
        A set of existing observer codes in the system.

    Returns
    -------
    `code` : `str`
        A unique observer code for the user.
    """
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
def add_user(connection, hashed_password, email, institution, first_name, last_name, user_level='novice'):
    """
    Add a new user to the database.

    Parameters
    ----------
    `connection` : `sqlite3.Connection`
        A connection object to the SQLite database.
    `username` : `str`
        The username of the user.
    `password` : `str`
        The password of the user.
    `email` : `str`
        The email address of the user.
    `institution` : `str`
        The institution the user belongs to.
    `first_name` : `str`
        The first name of the user.
    `last_name` : `str`
        The last name of the user.

    Returns
    -------
    None

    Raises
    ------
    `sqlite3.IntegrityError`
        If an error occurs while inserting the user into the database.
    """
    try:
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
        INSERT INTO users (password_hash, email, first_name, last_name, institution, observer_code, user_level) 
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (hashed_password, email, first_name, last_name, institution, observer_code, user_level))
        connection.commit()
        print(f"User '{first_name} {last_name}' added successfully with institution '{institution}' and observer code '{observer_code}'.")
    except sqlite3.IntegrityError as e:
        print(f"Error adding user: {e}")


def validate_user_by_identifier(connection, identifier):
    """
    Validate a user by their username or email.

    Parameters
    ----------
    `connection` : `sqlite3.Connection`
        A connection object to the SQLite database.
    `identifier` : `str`

    Returns
    -------
    `user` : `tuple`
        A tuple representing the user record if found, or `None` if not found.

    Raises
    ------
    `sqlite3.Error`
        If an error occurs while executing the SQL query.
    """
    print(f"Identifier received: {identifier}")  # Debugging
    cursor = connection.cursor()
    cursor.execute("""
        SELECT * FROM users WHERE email = ? OR observer_code = ?;
    """, (identifier, identifier))
    return cursor.fetchone()


def login_user(connection, identifier, password):
    """
    Login a user by their username or email and password.
    
    Parameters
    ----------
    `connection` : `sqlite3.Connection`
        A connection object to the SQLite database.
    `identifier` : `str`
        The username or email of the user.
    `password` : `str`
        The password of the user.

    Returns
    -------
    `str`
        A session token if the login is successful, or `None` if failed.

    Raises
    ------
    `sqlite3.Error`
        If an error occurs while executing the SQL query.    
    """
    user = validate_user_by_identifier(connection, identifier)
    if user:
        user_id, stored_hash, first_name = user[0], user[2], user[4]
        if check_password(password, stored_hash):
            logging.info(f"Login successful. Welcome, {first_name}!")
            return start_session(connection, user_id)
    logging.warning("Login failed: Invalid username/email or password.")
    return None
   

def initiate_password_reset(connection, identifier):
    """
    Initiate the password reset process for a user by their username or email.

    Currently, this function only prints a message indicating that the password reset process has been initiated.
    In the future, this will handle the resetting of the user's password, using reser_password() after validation.
    """
    user = validate_user_by_identifier(connection, identifier)
    if user:
        first_name = user[4]  # The first_name is in the 5th column
        print(f"Hello, {first_name}. Let's reset your password.")
        return user
    else:
        print("No account found with that username or email.")
        return None


def reset_password(connection, session_id, user_id, new_password):
    """
    Reset password.

    Resets the password for a user. Checks to make sure the current user is logged in before resetting the password.

    Parameters
    ----------
    `connection` : `sqlite3.Connection`
        A connection object to the SQLite database.
    `user_id` : `int`
        The user ID of the user whose password is being reset.
    `new_password` : `str`
        The new password to set for the user.

    Returns
    -------
    None

    Raises
    ------
    `sqlite3.Error`
        If an error occurs while executing
    """

    if not validate_session(connection, session_id):
        logging.warning("Unauthorized request: Invalid or expired session.")
        return    
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
    """
    Create the institutions table in the database.

    Parameters
    ----------
    `connection` : `sqlite3.Connection`
        A connection object to the SQLite database.

    Returns
    -------
    None

    Raises
    ------
    `sqlite3.Error`
        If an error occurs while executing the SQL query.
    """
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
    """
    Populate the institutions table with MACRO institutions.

    In the future, this function could be expanded to allow for adding and removing institutions.

    Parameters
    ----------
    `connection` : `sqlite3.Connection`
        A connection object to the SQLite database.

    Returns
    -------
    None

    Raises
    ------
    `sqlite3.IntegrityError`
        If an error occurs while inserting the institutions into the database.
    """
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
    """
    List the available institutions in the database.

    Parameters
    ----------
    `connection` : `sqlite3.Connection`
        A connection object to the SQLite database.

    Returns
    -------
    None

    Raises
    ------
    `sqlite3.Error`
        If an error occurs while executing the SQL query.
    """
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
    """
    Get a list of institution names from the database.

    Parameters
    ----------
    `connection` : `sqlite3.Connection`
        A connection object to the SQLite database.

    Returns
    -------
    `list`
        A list of institution names.

    Raises
    ------
    `sqlite3.Error` 
        If an error occurs while executing the SQL query.
    """
    cursor = connection.cursor()
    cursor.execute("SELECT name FROM institutions;")
    return [row[0] for row in cursor.fetchall()]  # Returns a list of institution names
