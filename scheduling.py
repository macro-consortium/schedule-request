import sqlite3, logging, csv, os
import pandas as pd

# Configure logging
logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
    )

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
        return sqlite3.connect("./observations.db")
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
    CREATE TABLE IF NOT EXISTS observations (
        request_id INTEGER PRIMARY KEY AUTOINCREMENT,
        observer_code TEXT NOT NULL,
        target_name TEXT NOT NULL,
        batch_id TEXT,
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
    SELECT COUNT(*) FROM observations
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

def add_observation_request(cursor, session, save=True, **kwargs):
    """
    Adds an individual observation request to the database.

    This function takes a user submitted observation request and adds it to the database.
    In addition, it checks for duplicate requests before adding the observation to the database.
    See the Notes section for more useful information.


    Parameters
    ----------
    `cursor` : :class:`sqlite3.Cursor`
        A cursor object to execute SQL queries.
    `session` : `dict`
        A dictionary containing the user's session information. This should include the
        observer code of the user.        
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
        - `exposure_time` : `int`, optional
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
    `observer_code` : `str`
                The observer code of the user. Follows the format {institution_code}+{user_id},
                where user_id is a unique identifier for the observer. Will be users initials 
                when possible. This will be automatically populated in the future when logged in.

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
    # Validate session
    if not session or "observer_code" not in session:
        logging.error("Invalid session: Observer code is missing.")
        raise ValueError("Invalid session or unauthorized user.")
        return 0

    observer_code = session["observer_code"]
    logging.info(f"Adding observation request for observer code: {observer_code}")


    params = {**DEFAULT_VALUES, **kwargs}

    try:
        params["ra"], params["dec"] = ra_dec_check(params["ra"], params["dec"])
    except ValueError as e:
        logging.error(f"Invalid RA/Dec values: {e}")
        raise ValueError("Invalid RA/Dec values.")
    
    if is_duplicate_request(cursor, observer_code, **kwargs):
        logging.info("Duplicate observation request detected. Skipping addition.")
        return 0

    params["batch_id"] = kwargs.get("batch_id", batch_idgen())
        
    insert_query = """
    INSERT INTO observations (observer_code, target_name, batch_id, ra, dec, observation_type, filters, nexp,
                                       exposure_time, priority, status, cadence, reposition, reposition_x, reposition_y,
                                       utc_start_time, utc_start_date, utc_end_time, utc_end_date,
                                       lst_start_time, lst_start_date, lst_end_time, lst_end_date)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    cursor.execute(insert_query, (
        observer_code, params["target_name"], params["batch_id"], params["ra"], params["dec"], 
        params["observation_type"], params["filters"], params["nexp"], params["exposure_time"], 
        params["priority"], params["status"], params["cadence"], params["reposition"], 
        params["reposition_x"], params["reposition_y"], params["utc_start_time"], params["utc_start_date"], 
        params["utc_end_time"], params["utc_end_date"], params["lst_start_time"], params["lst_start_date"], 
        params["lst_end_time"], params["lst_end_date"]))
    if save:
        cursor.connection.commit()
        logging.info("Observation request added successfully.")
    return 1

def add_batch_observations(connection, session, observations):
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
    successful = 0
    try:
        for obs in observations:
            state = add_observation_request(cursor, session, **obs, save=False)
            successful += state
        connection.commit()
        logging.info(f"{successful} observation(s) added successfully.")
        logging.info(f"{len(observations) - successful} observations failed to add.")
    except sqlite3.Error as e:
        connection.rollback() 
        logging.error(f"Error adding batch observations: {e}")
    finally:
        cursor.close()

def list_observation_requests(connection):
    """
    Fetches and displays all observation requests from the database in tabular format.

    Parameters
    ----------
    connection : sqlite3.Connection
        A connection object to the SQLite database.

    Returns
    -------
    None
    """
    try:
        query = "SELECT * FROM observations;"
        df = pd.read_sql_query(query, connection)

        if df.empty:
            logging.info("No observation requests found.")
        else:
            print("\nObservation Requests:")
            print(df.to_string(index=False))
    except sqlite3.Error as e:
        logging.error(f"Error retrieving observation requests: {e}")

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
        logging.warning("No updates provided. Skipping.")
        return

    cursor = connection.cursor()
    try:
        # Generate the SET clause dynamically
        set_clause = ", ".join(f"{key} = ?" for key in kwargs.keys())
        values = list(kwargs.values())
        values.append(request_id)

        cursor.execute(f"""
        UPDATE observations
        SET {set_clause}
        WHERE request_id = ?
        """, values)
        connection.commit()
        logging.info(f"Observation request {request_id} updated successfully.")
    except sqlite3.Error as e:
        logging.error(f"Error updating observation request: {e}")
    finally:
        cursor.close()

def update_observation_status(connection, request_id, new_status):
    # Placeholder for updating request status
    pass

def process_schedule_file(file_path, connection, session):
    """
    Processes a schedule file and adds its contents as observation requests in the database.

    Parameters
    ----------
    file_path : str
        The path to the schedule file.
    connection : sqlite3.Connection
        Database connection object.
    session : dict
        User session information, including `observer_code`.

    Returns
    -------
    None
    """
    observations = []
    current_obs = {}

    try:
        with open(file_path, 'r') as f:
            for line in f:
                # Ignore empty lines or comments
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                
                # Split the line into keyword and value
                parts = line.split(maxsplit=1)
                if len(parts) != 2:
                    raise ValueError(f"Invalid line format: {line}")
                key, value = parts

                # Check if a new observation starts (assuming a convention)
                if key.lower() == "new_observation":
                    if current_obs:
                        observations.append(current_obs)
                        current_obs = {}
                else:
                    current_obs[key] = value
            
            # Add the last observation if present
            if current_obs:
                observations.append(current_obs)

        # Add observations to the database
        if observations:
            add_batch_observations(connection, session, observations)
            print(f"Successfully added {len(observations)} observations.")
        else:
            print("No valid observations found in the file.")

    except Exception as e:
        print(f"Error processing schedule file: {e}")

def parse_schedule_file(file_path):

    observations = []
    with open(file_path, 'r') as f:
        file_extension = os.path.splitext(file_path)[1].lower()
        observations = []
        
        if file_extension in {'.csv', '.ecsv'}:
            try:
                df = pd.read_csv(file_path)
                observations = df.to_dict(orient='records')
            except Exception as e:
                logging.error(f"Error reading CSV file: {e}")
                raise ValueError(f"Failed to parse schedule file: {e}")
        elif file_extension in {'.sch', '.txt'}:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("source") or line.startswith("target") or line.startswith("target_name"):
                    try:
                        parts = line.split('"')
                        target_name = parts[1] if len(parts) > 1 else None
                        if not target_name:
                            raise ValueError(f"Missing target name in line: {line}")

                        params = line.split()
                        obs = {"target_name": target_name}
                        for i, param in enumerate(params):
                            if param in {"ra", "dec", "nexp", "exposure_time", "filters", "readout", "cadence", "utstart"}:
                                key = param.lower()
                                value = params[i + 1]
                                obs[key] = value
                            
                            # group by batch_id
                            if param == "group":
                                group_num = params[i + 1]
                                obs["batch_id"] = batch_idgen() + group_num 
                                
                        if not {"ra", "dec"}.issubset(obs):
                            raise ValueError(f"Missing required fields in line: {line}")

                        obs["nexp"] = int(obs.get("nexp", 1))
                        obs["exposure_time"] = int(obs.get("exposure_time", 1))
                        observations.append(obs)
                    except Exception as e:
                        logging.warning(f"Skipping invalid line: {line} ({e})")
                        continue
        else:
            raise ValueError(f"Unsupported file format: {file_extension}. Supported formats: .csv, .ecsv, .sch, .txt")

    if not observations:
        raise ValueError("No valid observations found in the file.")
    return observations

def ra_dec_check(ra, dec):
    """
    Parses RA and Dec strings into the appropriate formats.
    RA is converted to hours if given in degrees.
    Dec remains in degrees.

    Parameters:
    ----------
    ra : str
        Right Ascension in HH:MM:SS, decimal degrees, or hours.
    dec : str
        Declination in ±DD:MM:SS or decimal degrees.

    Returns:
    -------
    tuple:
        (ra_hours, dec_degrees)
    """

    def hms_to_hours(hms):
        parts = list(map(float, hms.split(":")))
        return parts[0] + parts[1] / 60 + (parts[2] / 3600 if len(parts) > 2 else 0)

    def dms_to_degrees(dms):
        parts = list(map(float, dms.split(":")))
        sign = -1 if parts[0] < 0 else 1
        return sign * (abs(parts[0]) + parts[1] / 60 + (parts[2] / 3600 if len(parts) > 2 else 0))

    # Parse RA
    if ":" in ra:  # HH:MM:SS
        ra_hours = hms_to_hours(ra)
    else:  # Decimal degrees
        ra_hours = float(ra) / 15  # Convert degrees to hours

    # Parse Dec
    if ":" in dec:  # ±DD:MM:SS
        dec_degrees = dms_to_degrees(dec)
    else:  # Decimal degrees
        dec_degrees = float(dec)

    # Validation
    if not (0 <= ra_hours < 24):
        raise ValueError(f"RA must be between 0 and 24 hours: {ra_hours}")
    if not (-90 <= dec_degrees <= 90):
        raise ValueError(f"Dec must be between -90 and 90 degrees: {dec_degrees}")

    return ra_hours, dec_degrees

def batch_idgen():
    """
    Generates a unique batch ID for a group of observation requests.
    """
    cursor = connection.cursor()
    cursor.execute(""""
        SELECT batch_id FROM observations ORDER BY batch_id DESC LIMIT 1;""")
    last_batch_id = cursor.fetchone()
    if last_batch_id:
        return last_batch_id + 1
    return 1

##### TESTING #####
##### Please delete this section #####

if __name__ == "__main__":
    connection = connect_observation_db()
    # list_observation_requests(connection)
    # Path to your sample file
    
    # file_path = "sample_schedule.csv"  # or .txt, .sch based on your format

    # # Parse the file
    # try:
    #     observations = parse_schedule_file(file_path)
    #     print("Parsed Observations:")
    #     for obs in observations:
    #         print(obs)
    # except Exception as e:
    #     print(f"Error: {e}")
    # # Mock session with observer code
    # session = {"observer_code": "irm"}  # Replace "IRM" with your actual observer code if needed.

    # # Adding parsed observations to the database
    # try:
    #     add_batch_observations(connection, session, observations)
    #     print("All observations added successfully.")
    # except Exception as e:
    #     print(f"Error adding observations: {e}")

    list_observation_requests(connection)

#### Thoughts ####
# - Add function to deal with sequential observations
## - Schedule files that are submitted with observations in the same line will be sequential 
## - Observations that are submitted on different lines will not be sequential
# - Add submit by file to the submit webpage
# - Fix visuals on submit page