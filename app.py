from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import firebase_admin
from firebase_admin import credentials, firestore
from functools import wraps 
import smtplib
import random 
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ==========================================
# 1. FIREBASE CONNECTION SETUP
# ==========================================
# Initialize Firebase only if it hasn't been initialized yet
if not firebase_admin._apps:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)

# Initialize Firestore database client
db = firestore.client()

# ==========================================
# 2. FLASK APP CONFIGURATION
# ==========================================
app = Flask(__name__)
# Secret key is required to manage secure user sessions
app.secret_key = "AIzaSyAPWfrqJGY5ls79pbw5RKMKdPSkQqFZUy8"

# ==========================================
# 3. GMAIL CONFIGURATION (For sending OTPs)
# ==========================================
MY_EMAIL = "kingstarkoti5566@gmail.com"  
APP_PASSWORD = "yzkj uphj wqrm opqb" # Google 16-digit App Password

# ==========================================
# 4. SECURITY LOGIC (Custom Decorator)
# ==========================================
# This function restricts access to specific pages, forcing users to login first
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash("Please login to access this page.") 
            return redirect(url_for('login_page')) 
        return f(*args, **kwargs)
    return decorated_function

# ==========================================
# 5. HOME PAGE
# ==========================================
@app.route('/', methods=['GET']) 
def home():
    # Fetch user details from session if logged in
    user_name = session.get('user') 
    return render_template('index.html', name=user_name)

# ==========================================
# 6. MANUAL LOGIN ROUTE
# ==========================================
@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        # Query the database to find the user by email
        users_ref = db.collection('users')
        query = users_ref.where('email', '==', email).stream()

        user_found = False
        for user in query:
            user_found = True
            data = user.to_dict()
            
            # Verify if the entered password matches the database record
            if data.get('password') == password:
                # Store user data in active session
                session['user'] = data.get('username')
                session['email'] = data.get('email') 
                return redirect(url_for('home'))
            else:
                flash("Error: Wrong Password!")
                return redirect(url_for('login_page'))
        
        # If the loop finishes and no user is found
        if not user_found:
            flash("Error: No Account found. Please Sign up.")
            return redirect(url_for('login_page'))

    return render_template('login.html')
@app.route('/servicesinformation')
def services_information():
    # లాగిన్ అయిన యూజర్ పేరుని హెడర్ లో చూపించడానికి
    user_name = session.get('user') 
    return render_template('servicesinformation.html', name=user_name)
@app.route('/about')
def about_page():
    user_name = session.get('user') 
    return render_template('about.html', name=user_name)

# ==========================================
# 7. GOOGLE SIGN-IN ROUTE (API Endpoint)
# ==========================================
@app.route('/google-login', methods=['POST'])
def google_login():
    # Retrieve JSON data sent from frontend JavaScript
    data = request.get_json()
    email = data.get('email')
    username = data.get('name')

    # Create session for the Google user
    session['user'] = username
    session['email'] = email

    # Check if this Google user already exists in our database
    users_ref = db.collection('users')
    query = users_ref.where('email', '==', email).get()
    
    # If the user does not exist, register them automatically
    if len(query) == 0:
        db.collection('users').add({
            'fullname': username,
            'username': username,
            'email': email,
            'password': 'google_signed_in' # No actual password needed for Google Auth
        })

    # Send success response back to frontend to trigger redirection
    return jsonify({"status": "success", "redirect": url_for('home')})

# ==========================================
# 8. REGISTRATION (SIGNUP & OTP ON SAME PAGE)
# ==========================================
@app.route('/signup', methods=['GET', 'POST'])
def register_page():
    if request.method == 'POST':
        
        # --- STEP 2: IF USER SUBMITTED THE OTP ---
        if 'otp' in request.form:
            user_otp = request.form.get('otp')
            
            # Check if the entered OTP matches the one stored in session
            if user_otp == session.get('signup_otp'):
                user_data = session.get('signup_user_data')
                try:
                    # Save the new user to the Firebase database permanently
                    db.collection('users').add(user_data)
                    
                    # Clear temporary data from session for security
                    session.pop('signup_otp', None)
                    session.pop('signup_user_data', None)
                    
                    flash("Success: Registration Complete! Please Login.")
                    return redirect(url_for('login_page'))
                except Exception as e:
                    flash(f"Error saving to database: {e}")
                    # Show OTP box again if database error occurs
                    return render_template('signup.html', show_otp=True)
            else:
                flash("Error: Invalid OTP! Please try again.")
                # Show OTP box again for retry
                return render_template('signup.html', show_otp=True)

        # --- STEP 1: IF USER SUBMITTED SIGNUP DETAILS ---
        fullname = request.form.get('fullname')
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        # Prevent duplicate email registrations
        users_ref = db.collection('users')
        existing_users = users_ref.where('email', '==', email).get()
        
        if len(existing_users) > 0:
            flash("Error: Account already exists with this Email! Please Login.")
            return redirect(url_for('register_page'))
        else:
            # Generate a random 6-digit OTP
            otp = str(random.randint(100000, 999999))
            
            # Temporarily store form data and OTP in session until verified
            session['signup_user_data'] = {
                'fullname': fullname,
                'username': username,
                'email': email,
                'password': password
            }
            session['signup_otp'] = otp

            try:
                # Prepare and send OTP email
                msg = MIMEMultipart()
                msg['From'] = MY_EMAIL
                msg['To'] = email
                msg['Subject'] = "Verify your email - DigitalGrowth Hub"
                body = f"Hello {fullname}, \n\nWelcome to DigitalGrowth Hub! \nYour OTP for email verification is: {otp}\n\nDo not share this with anyone."
                msg.attach(MIMEText(body, 'plain'))

                server = smtplib.SMTP('smtp.gmail.com', 587)
                server.starttls()
                server.login(MY_EMAIL, APP_PASSWORD)
                server.send_message(msg)
                server.quit()

                flash("Success: Verification OTP sent to your email!")
                # Render the SAME page, but tell HTML to show the OTP input box
                return render_template('signup.html', show_otp=True)
            except Exception as e:
                flash(f"Error sending email: {e}")
                return redirect(url_for('register_page'))

    # Default GET request (Normal page load)
    return render_template('signup.html', show_otp=False)

# ==========================================
# 9. FORGOT PASSWORD - STEP 1: SEND OTP
# ==========================================
@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        
        # Check if the provided email exists in our database
        users_ref = db.collection('users')
        query = users_ref.where('email', '==', email).get()

        if len(query) > 0:
            # Generate OTP and store in session
            otp = str(random.randint(100000, 999999))
            session['reset_otp'] = otp
            session['reset_email'] = email

            try:
                # Prepare and send password reset email
                msg = MIMEMultipart()
                msg['From'] = MY_EMAIL
                msg['To'] = email
                msg['Subject'] = "Password Reset OTP - DigitalGrowth Hub"
                body = f"Hello, \n\nYour OTP for password reset is: {otp}\n\nDo not share this with anyone."
                msg.attach(MIMEText(body, 'plain'))

                server = smtplib.SMTP('smtp.gmail.com', 587)
                server.starttls()
                server.login(MY_EMAIL, APP_PASSWORD)
                server.send_message(msg)
                server.quit()

                flash("Success: OTP sent to your email!")
                return redirect(url_for('verify_otp_page'))
            except Exception as e:
                flash(f"Email Error: {e}")
        else:
            flash("Error: No account found with this email. Please check spelling or Sign up.")
            return redirect(url_for('forgot_password'))
            
    return render_template('forgot_password.html')

# ==========================================
# 9.1 FORGOT PASSWORD - STEP 2: VERIFY & RESET
# ==========================================
@app.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp_page():
    # Prevent direct URL access
    if 'reset_otp' not in session:
        flash("Please request an OTP first.")
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        user_otp = request.form.get('otp')
        new_password = request.form.get('new_password')

        # Validate OTP
        if user_otp == session.get('reset_otp'):
            email = session.get('reset_email')
            users_ref = db.collection('users')
            query = users_ref.where('email', '==', email).get()
            
            # Find the user's document ID and update the password field
            for doc in query:
                db.collection('users').document(doc.id).update({'password': new_password})

            # Clear session data
            session.pop('reset_otp', None)
            session.pop('reset_email', None)

            flash("Success: Password updated! Please login.")
            return redirect(url_for('login_page'))
        else:
            flash("Error: Invalid OTP! Please try again.")

    return render_template('verify_otp.html')

# ==========================================
# 10. BOOK SERVICE ROUTE (Protected)
# ==========================================
@app.route('/book', methods=['GET', 'POST'])
@login_required 
def book_service():
    if request.method == 'POST':
        name = request.form.get('name')
        phone = request.form.get('phone')
        service_name = request.form.get('serviceName') 
        date = request.form.get('date')
        message = request.form.get('message')
        
        # Prepare booking payload
        booking_data = {
            'username': session.get('user'),
            'email': session.get('email'), 
            'name': name, 
            'phone': phone, 
            'serviceName': service_name,
            'date': date, 
            'message': message, 
            'status': 'Pending' # Default status for new bookings
        }
        try:
            # Save booking to Firebase
            db.collection('bookings').add(booking_data)
            flash("Success: Booking confirmed!")
            return redirect(url_for('historydetails')) 
        except Exception as e:
            flash(f"Error: {e}")
            
    # Pre-fill the service name if passed in the URL parameters
    selected_service = request.args.get('service', 'General Consultation')
    return render_template('booking.html', service_name=selected_service)

# ==========================================
# 11. USER DASHBOARD / HISTORY (Protected)
# ==========================================
@app.route('/historydetails')
@login_required
def historydetails():
    user_name = session.get('user') 
    user_bookings = []
    
    # Fetch all bookings associated with the logged-in username
    bookings_ref = db.collection('bookings')
    query = bookings_ref.where('username', '==', user_name).stream()
    
    for doc in query:
        user_bookings.append(doc.to_dict())
        
    return render_template('historydetails.html', name=user_name, bookings=user_bookings)

# ==========================================
# 12. LOGOUT ROUTE
# ==========================================
@app.route('/logout')
def logout():
    # Remove all data from the active session
    session.clear() 
    flash("You have been logged out.")
    return redirect(url_for('home')) 

# Run the Flask application
if __name__ == '__main__':
    app.run(debug=True)