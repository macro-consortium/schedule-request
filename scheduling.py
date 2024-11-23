import sqlite3
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

DEFAULT_VALUES = {
    "priority": "normal",
    "status": "pending",
    "target_name": None,
    "observation_type": "default",
    "filters": None,
    "nexp": 1,
    "exposure_time": 1,
    "reposition": False,
    "reposition_x": 1024,
    "reposition_y": 1024,
    "cadence": None,
    "utc_start_time": None,
    "utc_start_date": None,
    "utc_end_time": None,
    "utc_end_date": None,
    "lst_start_time": None,
    "lst_start_date": None,
    "lst_end_time": None,
    "lst_end_date": None,
}


def connect_observation_db():
    """
    Establishes a connection to the observation request database.

    Returns
    -------
    :class:`sqlite3.Connection`: A connection object to the SQLite database.
    
    Raises
    ------
    :class:`sqlite3.Error`: If there is an error connecting to the database.
    """
    try:
        return sqlite3.connect("./observation_data.db")
    except sqlite3.Error as e:
        logging.error(f"Database connection error: {e}")
        raise


def create_observation_requests_table(cursor):
    """
    Creates the observation requests table if it does not already exist.

    Parameters
    ----------
    cursor : :class:`sqlite3.Cursor`
        A cursor object to execute SQL queries.

    Returns
    -------
    None
    """
    table_query = """
    CREATE TABLE IF NOT EXISTS observation_requests (
        request_id INTEGER PRIMARY KEY AUTOINCREMENT,
        observer_code TEXT NOT NULL,
        target_name TEXT NOT NULL,
        ra TEXT NOT NULL,
        dec TEXT NOT NULL,
        observation_type TEXT NOT NULL,
        filters TEXT,
        priority TEXT NOT NULL DEFAULT 'normal',
        status TEXT NOT NULL DEFAULT 'pending',
        nexp INTEGER NOT NULL,
        exposure_time INTEGER NOT NULL DEFAULT 1,
        reposition BOOLEAN NOT NULL DEFAULT false,
        reposition_x INTEGER NOT NULL DEFAULT 1024,
        reposition_y INTEGER NOT NULL DEFAULT 1024,
        successive_block INTEGER,
        cadence TEXT,
        readout TEXT,
        utc_start_time TEXT,
        utc_start_date TEXT,
        utc_end_time TEXT,
        utc_end_date TEXT,
        lst_start_time TEXT,
        lst_start_date TEXT,
        lst_end_time TEXT,
        lst_end_date TEXT,
        submitted_on TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    cursor.execute(table_query)
    logging.info("Observation requests table created or already exists.")


def is_duplicate_request(cursor, observer_code, **kwargs):
    """
    Checks for duplicate observation requests in the database.

    Parameters
    ----------
    `cursor` : :class:`sqlite3.Cursor`
        A cursor object to execute SQL queries.
    `observer_code` : `str`
        The observer code of the user.
    `**kwargs` : `dict`
        Keyword arguments for the observation request.
    
    Returns
    -------
    `bool`
        `True` if a duplicate request is found, `False` otherwise.
    """
    query = """
    SELECT COUNT(*) FROM observation_requests
    WHERE observer_code = ? AND ra = ? AND dec = ? AND target_name = ? AND observation_type = ?
          AND filters = ? AND nexp = ? AND exposure_time = ? AND priority = ? AND status = ?
          AND reposition = ? AND reposition_x = ? AND reposition_y = ?
          AND (cadence IS ? OR cadence = ?) AND
               (utc_start_time IS ? OR utc_start_time = ?) AND
               (utc_start_date IS ? OR utc_start_date = ?) AND
               (utc_end_time IS ? OR utc_end_time = ?) AND
               (utc_end_date IS ? OR utc_end_date = ?) AND
               (lst_start_time IS ? OR lst_start_time = ?) AND
               (lst_start_date IS ? OR lst_start_date = ?) AND
               (lst_end_time IS ? OR lst_end_time = ?) AND
               (lst_end_date IS ? OR lst_end_date = ?)
    """
    reposition = 1 if kwargs.get("reposition", False) else 0
    params = (
        observer_code, kwargs["ra"], kwargs["dec"],
        kwargs.get("target_name", f"J2000-{kwargs['ra']}{kwargs['dec']}"),
        kwargs.get("observation_type", DEFAULT_VALUES["observation_type"]),
        kwargs.get("filters"), kwargs["nexp"], kwargs["exposure_time"],
        kwargs.get("priority", DEFAULT_VALUES["priority"]),
        kwargs.get("status", DEFAULT_VALUES["status"]),
        reposition, kwargs.get("reposition_x", DEFAULT_VALUES["reposition_x"]),
        kwargs.get("reposition_y", DEFAULT_VALUES["reposition_y"]),
        kwargs.get("cadence"), kwargs.get("cadence"),
        kwargs.get("utc_start_time"), kwargs.get("utc_start_time"),
        kwargs.get("utc_start_date"), kwargs.get("utc_start_date"),
        kwargs.get("utc_end_time"), kwargs.get("utc_end_time"),
        kwargs.get("utc_end_date"), kwargs.get("utc_end_date"),
        kwargs.get("lst_start_time"), kwargs.get("lst_start_time"),
        kwargs.get("lst_start_date"), kwargs.get("lst_start_date"),
        kwargs.get("lst_end_time"), kwargs.get("lst_end_time"),
        kwargs.get("lst_end_date"), kwargs.get("lst_end_date"),
    )
    cursor.execute(query, params)
    count = cursor.fetchone()[0]
    return count > 0


def add_observation_request(cursor, observer_code, save=True, **kwargs):
    """
    Adds an individual observation request to the database.

    This function takes a user submitted observation request and adds it to the database.
    In addition, it checks for duplicate requests before adding the observation to the database.
    See the Notes section for more useful information.


    Parameters
    ----------
    `cursor` : :class:`sqlite3.Cursor`
        A cursor object to execute SQL queries.
    `observer_code` : `str`
        The observer code of the user. Follows the format {institution_code}+{user_id},
        where user_id is a unique identifier for the observer. Will be users initials 
        when possible.
    `save` : `bool`, optional
        Whether to commit the transaction immediately. Default is `True`. This is set 
        to `False` when adding multiple observations in a batch.
    `**kwargs` : `dict`
        Keyword arguments for the observation request. The following keys are accepted:
        - `ra` : `str`
            The Right Ascension of the target.
        - `dec` : `str`
            The Declination of the target.
        - `target_name` : `str`, optional
            The name of the target. If not provided, a default name will be generated.
            This will follow the format J2000-{ra}{dec}.
        - `observation_type` : `str`, optional
            The type of observation. Default is `default`. May include values such as
            `beginner`, `intermediate`, `advanced`, etc.
        - `filters` : `str`, optional
            The filters to use for the observation.
        - `nexp` : `int`, optional
            The number of exposures to take.
        - `exptime` : `int`, optional
            The exposure time in seconds.
        - `priority` : `str`, optional
            The priority of the observation. Default is `normal`.
        - `status` : `str`, optional
            The status of the observation. Default is `pending`. Will be updated to
            `scheduled` once the observation is scheduled and `completed` once it is
            completed.
        - `reposition` : `bool`, optional
            Whether to reposition the telescope for the observation. Default is `False`.
        - `reposition_x` : `int`, optional
            The x-coordinate to reposition the telescope to. Default is 1024.
        - `reposition_y` : `int`, optional
            The y-coordinate to reposition the telescope to. Default is 1024.
        - `cadence` : `str`, optional
            The cadence of the observation i.e., how long between individual exposure 
            start times. This should follow the format: {hh}:{mm}:{ss} if provided. 
            Default is `None`.
        - `utc_start_time` : `str`, optional
            The UTC start time of the observation. This should follow the format: 
            {hh}:{mm}:{ss} if provided. Default is `None`.
        - `utc_start_date` : `str`, optional
            The UTC start date of the observation. This should follow the format: 
            {yyyy}-{mm}-{dd}T{hh}:{mm}:{ss} if provided. Default is `None`.
        - `utc_end_time` : `str`, optional
            The UTC end time of the observation. This should follow the format: 
            {hh}:{mm}:{ss} if provided. Default is `None`.
        - `utc_end_date` : `str`, optional
            The UTC end date of the observation. This should follow the format: 
            {yyyy}-{mm}-{dd}T{hh}:{mm}:{ss} if provided. Default is `None`.
        - `lst_start_time` : `str`, optional
            The LST start time of the observation. This should follow the format: 
            {hh}:{mm}:{ss} if provided. Default is `None`.
        - `lst_start_date` : `str`, optional
            The LST start date of the observation. This should follow the format: 
            {yyyy}-{mm}-{dd}T{hh}:{mm}:{ss} if provided. Default is `None`.
        - `lst_end_time` : `str`, optional
            The LST end time of the observation. This should follow the format: 
            {hh}:{mm}:{ss} if provided. Default is `None`.
        - `lst_end_date` : `str`, optional
            The LST end date of the observation. This should follow the format: 
            {yyyy}-{mm}-{dd}T{hh}:{mm}:{ss} if provided. Default is `None`.

    Returns
    -------
    None

    Raises
    ------
    :class:`sqlite3.Error`
        If there is an error executing the SQL query.

    Notes
    -----
    - If the observation request is a duplicate, it will not be added to the database.
    - Start and end times/dates are optional and can be provided in either UTC or LST.
    - Date vs Time: If you do not care what day the observation starts but you do care
        what time it starts, please use the UTC/LST start/end time fields. If you care
        about the day as well, please use the UTC/LST start/end date fields.
    - Observation request submission time is automatically added to the database in UTC.
    - Observer codes will be automatically populated in the future when logged in. 
    - Can be set to `save=False` when adding multiple observations in a batch. This is
        useful to reduce machine load and commit all observations at once.
    """
    if is_duplicate_request(cursor, observer_code, **kwargs):
        logging.info("Duplicate observation request detected. Skipping addition.")
        return
    params = {**DEFAULT_VALUES, **kwargs}
    insert_query = """
    INSERT INTO observation_requests (observer_code, target_name, ra, dec, observation_type, filters, nexp,
                                       exposure_time, priority, status, cadence, reposition, reposition_x, reposition_y,
                                       utc_start_time, utc_start_date, utc_end_time, utc_end_date,
                                       lst_start_time, lst_start_date, lst_end_time, lst_end_date)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    cursor.execute(insert_query, (
        observer_code, params["target_name"], params["ra"], params["dec"], params["observation_type"],
        params["filters"], params["nexp"], params["exposure_time"], params["priority"], params["status"],
        params["cadence"], params["reposition"], params["reposition_x"], params["reposition_y"],
        params["utc_start_time"], params["utc_start_date"], params["utc_end_time"], params["utc_end_date"],
        params["lst_start_time"], params["lst_start_date"], params["lst_end_time"], params["lst_end_date"]
    ))
    if save:
        cursor.connection.commit()
        logging.info("Observation request added successfully.")



def add_batch_observations(connection, observer_code, observations):
    """
    Adds multiple observation requests to the database at once.

    Parameters
    ----------
    `connection` : :class:`sqlite3.Connection`
        A connection object to the SQLite database.
    `observer_code` : `str`
        The observer code of the user. Follows the format {institution_code}+{user_id},
        where user_id is a unique identifier for the observer. Will be users initials 
        when possible. This will be automatically populated in the future when logged in.
    `observations` : `list`
        A list of dictionaries, where each dictionary represents an observation request.
        Please see the `add_observation_request` function for the accepted keys in the
        dictionary. Default values will be used for any missing keys.

    Returns
    -------
    None

    Raises
    ------
    :class:`sqlite3.Error`
        If there is an error executing the SQL query.

    Notes
    -----
    - The `add_observation_request` function is used to add each observation request to
        the database. This function is used to add multiple requests at once.
    - If any of the observation requests are duplicates, they will not be added to the
        database. If you would like to edit the duplicate requests, please use the
        `edit_observation_request` function.
    """
    cursor = connection.cursor()
    try:
        for obs in observations:
            add_observation_request(cursor, observer_code, **obs, save=False)
        connection.commit()
        print(f"Batch of {len(observations)} observation(s) added successfully.")
    except sqlite3.Error as e:
        connection.rollback()  # Rollback on failure
        print(f"Error adding batch observations: {e}")
    finally:
        cursor.close()


def list_observation_requests(connection):
    """
    Fetches and displays all observation requests from the database.

    Parameters
    ----------
    `connection` : :class:`sqlite3.Connection`
        A connection object to the SQLite database.

    Returns
    -------
    None

    Raises
    ------
    :class:`sqlite3.Error`
        If there is an error executing the SQL query.
    """
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT * FROM observation_requests;")
        requests = cursor.fetchall()
        if not requests:
            print("No observation requests found.")
        else:
            print("Observation Requests:")
            for request in requests:
                print(request)
    except sqlite3.Error as e:
        print(f"Error retrieving observation requests: {e}")


def is_duplicate_request(cursor, observer_code, **kwargs):
    """
    Checks for duplicate observation requests in the database.

    This function checks if an observation request with the same parameters already exists
    in the database. If a duplicate request is found, it will return `True`, otherwise it
    will return `False`. This is useful to prevent adding duplicate requests to the database,
    as duplicate requests will be rejected and the user will be notified to edit the existing
    request instead.

    Parameters
    ----------
    `cursor` : :class:`sqlite3.Cursor`
        A cursor object to execute SQL queries.
    `observer_code` : `str`
        The observer code of the user.
    `**kwargs` : `dict`
        Keyword arguments for the observation request.

    Returns
    -------
    `bool`
        `True` if a duplicate request is found, `False` otherwise.
    """
    query = """
    SELECT COUNT(*) FROM observation_requests
    WHERE observer_code = ? AND ra = ? AND dec = ? AND target_name = ? AND observation_type = ?
          AND filters = ? AND nexp = ? AND exposure_time = ? AND priority = ? AND status = ?
          AND reposition = ? AND reposition_x = ? AND reposition_y = ?
          AND (cadence IS ? OR cadence = ?) AND
               (utc_start_time IS ? OR utc_start_time = ?) AND
               (utc_start_date IS ? OR utc_start_date = ?) AND
               (utc_end_time IS ? OR utc_end_time = ?) AND
               (utc_end_date IS ? OR utc_end_date = ?) AND
               (lst_start_time IS ? OR lst_start_time = ?) AND
               (lst_start_date IS ? OR lst_start_date = ?) AND
               (lst_end_time IS ? OR lst_end_time = ?) AND
               (lst_end_date IS ? OR lst_end_date = ?)
    """
    # Convert boolean values to integers
    reposition = 1 if kwargs.get("reposition", False) else 0

    params = (
        observer_code, kwargs["ra"], kwargs["dec"],
        kwargs.get("target_name", f"J2000{kwargs['ra']}{kwargs['dec']}"),
        kwargs.get("observation_type", "default"), kwargs["filters"],
        kwargs["nexp"], kwargs["exptime"], kwargs.get("priority", "normal"),
        kwargs.get("status", "pending"), reposition, kwargs.get("reposition_x", 1024),
        kwargs.get("reposition_y", 1024), kwargs.get("cadence"), kwargs.get("cadence"),
        kwargs.get("utc_start_time"), kwargs.get("utc_start_time"), kwargs.get("utc_start_date"),
        kwargs.get("utc_start_date"), kwargs.get("utc_end_time"), kwargs.get("utc_end_time"),
        kwargs.get("utc_end_date"), kwargs.get("utc_end_date"), kwargs.get("lst_start_time"),
        kwargs.get("lst_start_time"), kwargs.get("lst_start_date"), kwargs.get("lst_start_date"),
        kwargs.get("lst_end_time"), kwargs.get("lst_end_time"), kwargs.get("lst_end_date"),
        kwargs.get("lst_end_date")
    )

    cursor.execute(query, params)
    count = cursor.fetchone()[0]
    return count > 0


def edit_observation_request(connection, request_id, **kwargs):
    """
    Edits an existing observation request in the database.
    
    This function allows users to edit an existing observation request in the database.
    Users can provide the request ID and the updated parameters they would like to change.
    In the future the request IDs will be visible to the user when logged in, with the option
    to edit the request directly.

    Parameters
    ----------
    `connection` : :class:`sqlite3.Connection`
        A connection object to the SQLite database.
    `request_id` : `int`
        The ID of the observation request to edit.
    `**kwargs` : `dict`
        Keyword arguments for the observation request. Please see the `add_observation_request`
        function for the accepted keys in the dictionary. Only the keys that need to be updated
        should be provided.

    Returns
    -------
    None

    Raises
    ------
    :class:`sqlite3.Error`
        If there is an error executing the SQL query.
    """

    if not kwargs:
        print("No updates provided. Skipping.")
        return

    cursor = connection.cursor()
    try:
        # Generate the SET clause dynamically
        set_clause = ", ".join(f"{key} = ?" for key in kwargs.keys())
        values = list(kwargs.values())
        values.append(request_id)

        cursor.execute(f"""
        UPDATE observation_requests
        SET {set_clause}
        WHERE request_id = ?
        """, values)
        connection.commit()
        print(f"Observation request {request_id} updated successfully.")
    except sqlite3.Error as e:
        print(f"Error updating observation request: {e}")
    finally:
        cursor.close()


def update_observation_status(connection, request_id, new_status):
    # Placeholder for updating request status
    pass