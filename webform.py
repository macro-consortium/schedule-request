from flask import Flask, render_template, request, redirect, flash, session, g
import scheduling as s
import user_db as u
import sqlite3, os

app = Flask(__name__)
app.secret_key = "secret_key"  # Replace with a strong secret key

### This function removes redundant code by setting the logged_in and user_level variables for each request ###
### This is required code ###
@app.before_request
def user_values():
    g.logged_in = 'user_id' in session
    g.user_level = session.get('user_level', '')
    g.observer_code = session.get('observer_code', '')
    
# Default pages for the website(Home, Login, Register, FAQ, Logout)
@app.route("/")
def home():
    return render_template('home.html', logged_in=g.logged_in, user_level=g.user_level)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Extract form data
        email = request.form.get('email')
        password = request.form.get('password')

        # Basic validation
        if not (email and password):
            flash("Please provide both email and password.")
            return redirect("/login")

        try:
            # Connect to the user database
            connection = u.connect_db()
            cursor = connection.cursor()

            # Validate user by email
            cursor.execute("SELECT user_id, password_hash, first_name FROM users WHERE email = ?", (email,))
            user = cursor.fetchone()

            if not user:
                flash("Invalid email or password.")
                return redirect("/login")

            user_id, hashed_password, first_name = user

            # Check password
            if not u.check_password(password, hashed_password):
                flash("Invalid email or password.")
                return redirect("/login")

            # Start session
            session['user_id'] = user_id
            session['email'] = email
            session['first_name'] = first_name
            session['user_level'] = cursor.execute("SELECT user_level FROM users WHERE email = ?", (email,)).fetchone()[0]

            flash(f"Welcome back, {first_name}!")
            return redirect("/")

        except Exception as e:
            flash(f"An error occurred during login: {e}")
            print(f"Error during login: {e}")
        finally:
            if 'connection' in locals():
                connection.close()

    return render_template('login.html', logged_in=g.logged_in, user_level=g.user_level)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Extract form data
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        institution = request.form.get('institution')
        user_level = request.form.get('user_level') # Defaults to novice, needs to be updated by an admin? Or should I add a code to the form?

        # Basic validation
        if not (first_name and last_name and email and password and confirm_password):
            flash("All fields are required.")
            return redirect("/register")

        if password != confirm_password:
            flash("Passwords do not match.")
            return redirect("/register")

        try:
            # Connect to the user database
            connection = u.connect_db()
            cursor = connection.cursor()

            # Check for duplicate email
            cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
            if cursor.fetchone():
                flash("Email is already registered.")
                return redirect("/register")

            # Hash the password
            hashed_password = u.hash_password(password)

            # Generate observer code
            cursor.execute("SELECT code FROM institutions WHERE name = ?", ("The University of Iowa",))  # Replace with dynamic selection if needed
            institution_code = cursor.fetchone()[0]
            cursor.execute("SELECT observer_code FROM users;")
            existing_codes = {row[0] for row in cursor.fetchall() if row[0]}  # Collect existing observer codes
            observer_code = u.generate_observer_code(institution_code, first_name, last_name, existing_codes)

            # Insert user into the database
            u.add_user(connection, first_name, last_name, email, hashed_password, observer_code, institution, user_level)

            flash("Registration successful! You can now log in.")
            return redirect("/login")

        except sqlite3.IntegrityError:
            flash("An error occurred. Please try again.")
        except Exception as e:
            flash(f"Unexpected error: {e}")
        finally:
            connection.close()

    return render_template('register.html', logged_in=g.logged_in, user_level=g.user_level)

@app.route('/faq', methods=['GET', 'POST'])
def faq():
    return render_template('faq.html', logged_in=g.logged_in, user_level=g.user_level)

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.")
    return redirect("/")


# Observation and observation management pages
@app.route('/submit', methods=['GET', 'POST'])
def schedule_observation():
    if 'user_id' not in session:
        flash("Please log in to access the scheduling form.")
        return redirect('/login')

    form_type = 'single'  # Default form type
    if request.method == 'POST':
        form_type = request.form.get('form_type')
        
        if form_type == 'single':
            ra = request.form.get('ra')
            dec = request.form.get('dec')
            nexp = request.form.get('nexp')
            exposure_time = request.form.get('exposure_time')
            filters = request.form.get('filters')
            target_name = request.form.get('target_name')

            if not (ra and dec and nexp and exposure_time):
                flash("RA, Dec, number of exposures, and exposure time are required fields.")
                return render_template('submit.html', logged_in=g.logged_in, user_level=g.user_level, form_type=form_type)
            try:
                connection = s.connect_observation_db()
                cursor = connection.cursor()
                s.add_observation_request(
                    cursor,
                    session,
                    ra=ra,
                    dec=dec,
                    nexp=int(nexp),
                    exposure_time=int(exposure_time),
                    filters=filters,
                    target_name=target_name
                )
                connection.commit()
                flash("Observation scheduled successfully!")
            except Exception as e:
                flash(f"Error scheduling observation: {e}")
            finally:
                connection.close()

        elif form_type == 'file':
            if 'schedule_file' not in request.files:
                flash("No file uploaded.")
                return render_template('submit.html', logged_in=g.logged_in, user_level=g.user_level, form_type=form_type)

            file = request.files['schedule_file']
            if file.filename == '':
                flash("No file selected.")
                return render_template('submit.html', logged_in=g.logged_in, user_level=g.user_level, form_type=form_type)

            upload_folder = os.path.join(os.getcwd(), 'uploads')
            os.makedirs(upload_folder, exist_ok=True)
            file_path = os.path.join(upload_folder, file.filename)
            file.save(file_path)

            try:
                observations = s.parse_schedule_file(file_path)
                connection = s.connect_observation_db()
                s.add_batch_observations(connection, {"observer_code": g.observer_code}, observations)
                flash(f"Successfully added {len(observations)} observations.")
            except Exception as e:
                flash(f"Error processing file: {e}")
                app.logger.error(f"File processing error: {e}")
            finally:
                if os.path.exists(file_path):
                    os.remove(file_path)

    return render_template('submit.html', logged_in=g.logged_in, user_level=g.user_level, form_type=form_type)

@app.route('/observations', methods=['GET', 'POST'])
def view_edit_schedule():
    return render_template('observations.html', logged_in=g.logged_in, user_level=g.user_level)


# @app.route('/upload_schedule', methods=['GET', 'POST'])
# def upload_schedule():
    if not g.logged_in:
        flash("Please log in to upload a schedule.")
        return redirect('/login')

    if g.user_level not in ['intermediate', 'advanced', 'admin']:
        flash("You do not have permission to upload schedules.")
        return redirect('/')

    if request.method == 'POST':
        if 'schedule_file' not in request.files:
            flash("No file uploaded.")
            return redirect('/upload_schedule')

        file = request.files['schedule_file']
        if file.filename == '':
            flash("No file selected.")
            return redirect('/upload_schedule')

        allowed_extensions = {'.sch', '.txt', '.csv', '.ecsv'}
        file_extension = os.path.splitext(file.filename)[1].lower()
        if file_extension not in allowed_extensions:
            flash("Invalid file type. Allowed types: .sch, .txt, .csv, .ecsv.")
            return redirect('/upload_schedule')

        # Save and parse the file
        upload_folder = os.path.join(os.getcwd(), 'uploads')
        os.makedirs(upload_folder, exist_ok=True)
        file_path = os.path.join(upload_folder, file.filename)
        file.save(file_path)

        try:
            # Parse the file into observations
            observations = s.parse_schedule_file(file_path)
            connection = s.connect_observation_db()
            s.add_batch_observations(connection, {"observer_code": g.observer_code}, observations)
            flash(f"Successfully added {len(observations)} observations.")
            return redirect('/observations')
        except Exception as e:
            flash(f"Error processing file: {e}")
            app.logger.error(f"File processing error: {e}")
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)

    return render_template('schedule_file.html', logged_in=g.logged_in, user_level=g.user_level)

# @app.route('/review_schedule', methods=['GET', 'POST'])
# def review_schedule():
#     if 'observations' not in session:
#         flash("No observations to review.")
#         return redirect('/upload_schedule')

#     observations = session['observations']

#     if request.method == 'POST':
#         # Handle edits or submission
#         action = request.form.get('action')
#         if action == 'edit':
#             # Update session with new observation data
#             observation_index = int(request.form.get('observation_index'))
#             observations[observation_index] = {
#                 'target_name': request.form.get('target_name'),
#                 'ra': request.form.get('ra'),
#                 'dec': request.form.get('dec'),
#                 'nexp': int(request.form.get('nexp')),
#                 'exposure_time': int(request.form.get('exposure_time')),
#                 'filters': request.form.get('filters')
#             }
#             session['observations'] = observations
#             flash("Observation updated.")
#         elif action == 'commit':
#             try:
#                 # Add all observations to the database
#                 connection = s.connect_observation_db()
#                 cursor = connection.cursor()
#                 observer_code = session.get('observer_code')
#                 for obs in observations:
#                     s.add_observation_request(cursor, session, **obs)
#                 connection.commit()
#                 session.pop('observations')  # Clear session
#                 flash("Observations committed successfully.")
#                 return redirect('/')
#             except Exception as e:
#                 flash(f"Error committing observations: {e}")
#             finally:
#                 connection.close()

#     return render_template('review_schedule.html', observations=observations, logged_in=g.logged_in, user_level=g.user_level)

# @app.route('/manage_observations', methods=['GET', 'POST'])
# def manage_observations():
    if 'user_id' not in session:
        flash("Please log in to manage observations.")
        return redirect('/login')

    return render_template('manage_observations.html', logged_in=g.logged_in, user_level=g.user_level)

# Account management pages (account details, admin dashboard)
@app.route('/account', methods=['GET', 'POST'])
def account():
    if 'user_id' not in session:
        flash("Please log in to view account details.")
        return redirect('/login')

    return render_template('account.html', logged_in=g.logged_in, user_level=g.user_level)

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    user_level=g.user_level
    if user_level != 'admin':
        flash("You do not have permission to access the admin dashboard.")
        return redirect('/')

    return render_template('admin.html', logged_in=g.logged_in, user_level=g.user_level)



if __name__ == "__main__":

    app.run(debug=True)
