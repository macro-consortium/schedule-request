from flask import Flask, render_template, request, redirect, url_for, flash, session
import scheduling as s
import user_db as u

app = Flask(__name__)
app.secret_key = "your_secret_key"  # Replace with a strong secret key

# Route to display the home page
@app.route("/")
def home():
    return render_template('home.html')

# Route to display the scheduling form
@app.route('/schedule', methods=['GET', 'POST'])
def schedule_observation():
    if request.method == 'POST':
        # Extract form data
        ra = request.form.get('ra')
        dec = request.form.get('dec')
        nexp = request.form.get('nexp')
        exposure_time = request.form.get('exposure_time')
        filters = request.form.get('filters')
        target_name = request.form.get('target_name')

        # Validation (basic example)
        if not (ra and dec and nexp and exposure_time):
            flash("RA, Dec, number of exposures, and exposure time are required fields.")
            return redirect(url_for('schedule_observation'))

        try:
            # Connect to database and add observation
            connection = s.connect_observation_db()
            cursor = connection.cursor()
            
            # Mock session data (replace with real session in production)
            session = {"observer_code": "abc123"}
            
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

        return redirect("http://127.0.0.1:5000")
    
    return render_template('schedule_form.html')

# Route to display the login form
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            flash("Please provide both username and password.")
            return redirect(url_for('login'))

        connection = s.connect_observation_db()  # Assuming this handles connection to user database
        try:
            user = u.validate_user_by_identifier(connection, username)
            if user:
                user_id, stored_hash = user[0], user[2]
                if u.check_password(password, stored_hash):
                    session['user_id'] = user_id
                    session['username'] = username
                    flash("Login successful!")
                    return redirect(url_for('profile'))
                else:
                    flash("Invalid password. Please try again.")
            else:
                flash("Invalid username. Please try again.")
        except Exception as e:
            flash(f"An error occurred during login: {e}")
        finally:
            connection.close()

    return render_template('login.html')


# Route to display the registration form
@app.route('/register', methods=['GET', 'POST'])
def register():
    return render_template('register.html')

# Route to display the user profile page
@app.route('/profile')
def profile():
    if 'user_id' not in session:
        flash("Please log in to access your profile.")
        return redirect(url_for('login'))
    return render_template('profile.html', username=session.get('username'))

# Route to handle user logout
@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.")
    return redirect(url_for('home'))

# Route to display the schedule editing form
@app.route('/edit_schedule', methods=['GET', 'POST'])
def edit_schedule():
    return render_template('edit_schedule.html')

# Route to display the user schedule viewing page
@app.route('/view_schedule')
def view_schedule():
    return render_template('view_schedule.html')

if __name__ == "__main__":
    app.run(debug=True)
