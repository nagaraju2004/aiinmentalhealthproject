import streamlit as st
import pandas as pd
import joblib
import datetime
import matplotlib.pyplot as plt
import sqlite3
import time
import numpy as np
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import io
import os
from email.mime.image import MIMEImage
import pickle
import warnings
warnings.filterwarnings('ignore')
from sklearn.ensemble import RandomForestClassifier

# Configure page
st.set_page_config(page_title="AI Mental Health", layout="wide")

# Function to create a dummy model for fallback
def create_dummy_model():
    """Create a simple dummy model for when the real model can't be loaded"""
    dummy_model = RandomForestClassifier(n_estimators=10, random_state=42)
    # Generate dummy training data (16 features as per your input)
    X_dummy = np.random.rand(100, 16)
    y_dummy = np.random.randint(0, 9, 100)
    dummy_model.fit(X_dummy, y_dummy)
    return dummy_model

# Function to encode input features
def encode_input_features(input_df):
    """Encode categorical variables to match model training"""
    # This is a simplified encoding - you need to match your actual encoding
    encoding_maps = {
        'Gender': {'Male': 0, 'Female': 1},
        'self_employed': {'Yes': 1, 'No': 0},
        'family_history': {'Yes': 1, 'No': 0},
        'treatment': {'Yes': 1, 'No': 0},
        'Days_Indoors': {
            '1-14 days': 0, 
            'Go out Every day': 1, 
            '15-30 days': 2, 
            '31-60 days': 3, 
            'More than 2 months': 4
        },
        'Growing_Stress': {'Yes': 1, 'No': 0, 'Maybe': 2},
        'Changes_Habits': {'Yes': 1, 'No': 0, 'Maybe': 2},
        'Mental_Health_History': {'Yes': 1, 'No': 0, 'Maybe': 2},
        'Mood_Swings': {'Low': 0, 'Medium': 1, 'High': 2},
        'Coping_Struggles': {'Yes': 1, 'No': 0},
        'Work_Interest': {'Yes': 0, 'Maybe': 1, 'No': 2},
        'Social_Weakness': {'Yes': 1, 'No': 0, 'Maybe': 2},
        'mental_health_interview': {'Yes': 1, 'No': 0, 'Maybe': 2},
        'care_options': {'Yes': 1, 'No': 0, 'Not sure': 2}
    }
    
    # Create encoded dataframe
    encoded_df = pd.DataFrame()
    
    for col in input_df.columns:
        if col in encoding_maps:
            encoded_df[col] = input_df[col].map(encoding_maps[col]).fillna(0)
        elif col == 'Country':
            # Simple country encoding (you might need a more sophisticated approach)
            encoded_df[col] = hash(input_df[col].iloc[0]) % 100
        elif col == 'Occupation':
            occupation_map = {'Corporate': 0, 'Student': 1, 'Business': 2, 'Housewife': 3, 'Others': 4}
            encoded_df[col] = input_df[col].map(occupation_map).fillna(4)
        else:
            encoded_df[col] = 0
    
    return encoded_df

# Load the trained model with error handling
@st.cache_resource
def load_model():
    try:
        model_path = os.path.join(os.path.dirname(__file__), "voting_gb_dt_model.pkl")
        if os.path.exists(model_path):
            # Try loading with joblib first
            try:
                model = joblib.load(model_path)
                # Check if it's a proper model with predict method
                if hasattr(model, 'predict'):
                    st.success("Model loaded successfully!")
                    return model
                else:
                    st.warning("Loaded object doesn't have predict method. Using dummy model.")
                    return create_dummy_model()
            except Exception as e:
                st.warning(f"Joblib loading failed: {str(e)}. Trying pickle...")
                # Fall back to pickle
                try:
                    with open(model_path, 'rb') as f:
                        model = pickle.load(f)
                    if hasattr(model, 'predict'):
                        st.success("Model loaded successfully with pickle!")
                        return model
                    else:
                        return create_dummy_model()
                except:
                    return create_dummy_model()
        else:
            st.warning(f"Model file not found. Using dummy model for testing.")
            return create_dummy_model()
    except Exception as e:
        st.error(f"Error loading model: {str(e)}")
        return create_dummy_model()

# Load model
model = load_model()

# Connect to SQLite database
@st.cache_resource
def init_database():
    conn = sqlite3.connect('new_user_data.db', check_same_thread=False)
    c = conn.cursor()
    
    # Create tables if they don't exist
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT
        )
    ''')
    
    # Create predictions table
    c.execute('''
        CREATE TABLE IF NOT EXISTS predictions (
            username TEXT,
            date DATETIME,
            prediction INTEGER,
            status TEXT,
            time_spent INTEGER,
            FOREIGN KEY (username) REFERENCES users (username)
        )
    ''')
    
    # Create chat messages table
    c.execute('''
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            message TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    return conn, c

conn, c = init_database()

# Create admin account if it doesn't exist
def create_admin_account():
    admin_username = "admin"
    admin_password = "admin891"
    c.execute("INSERT OR IGNORE INTO users (username, password) VALUES (?, ?)", (admin_username, admin_password))
    conn.commit()

create_admin_account()

# Function to authenticate user
def authenticate(username, password):
    c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
    return c.fetchone() is not None

# Function to register user
def register(username, password):
    try:
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False

# Function to save prediction to the database
def save_prediction(username, date, prediction, status, time_spent):
    c.execute("INSERT INTO predictions (username, date, prediction, status, time_spent) VALUES (?, ?, ?, ?, ?)", 
              (username, date, int(prediction), status, time_spent))
    conn.commit()

# Function to fetch predictions for a user
def fetch_predictions(username):
    c.execute("SELECT date, prediction, status FROM predictions WHERE username=?", (username,))
    rows = c.fetchall()
    return pd.DataFrame(rows, columns=["Date", "Prediction", "Status"])

# Function to fetch chat messages with IDs
def fetch_chat_messages():
    c.execute("SELECT id, username, message, timestamp FROM chat_messages ORDER BY timestamp")
    return c.fetchall()

# Function to save a chat message
def save_chat_message(username, message):
    c.execute("INSERT INTO chat_messages (username, message) VALUES (?, ?)", (username, message))
    conn.commit()

# Function to delete a chat message
def delete_chat_message(message_id):
    c.execute("DELETE FROM chat_messages WHERE id=?", (message_id,))
    conn.commit()

# Function to make predictions and map to mental health status
def predict(input_data):
    if model is None:
        st.warning("Model not loaded. Using default prediction.")
        return 3, 50.0
    
    try:
        # Convert input data to DataFrame
        input_df = pd.DataFrame([input_data])
        
        # Encode categorical variables
        input_encoded = encode_input_features(input_df)
        
        # Make prediction
        if hasattr(model, 'predict'):
            prediction = model.predict(input_encoded)
            if hasattr(model, 'predict_proba'):
                confidence = model.predict_proba(input_encoded)
                confidence_percentage = np.max(confidence) * 100
            else:
                confidence_percentage = 75.0  # Default confidence
            
            return prediction[0], confidence_percentage
        else:
            st.error("Model doesn't have predict method")
            return 3, 50.0
    except Exception as e:
        st.error(f"Prediction error: {str(e)}")
        # Return default values
        return 3, 50.0

def map_to_status(yes_count):
    try:
        yes_count = int(yes_count)
        if yes_count <= 3:
            return "Stable or Low Instability"
        elif yes_count == 4:
            return "Moderate Instability"
        elif 5 <= yes_count <= 8:
            return "High Instability or Severe Instability"
        else:
            return "Unknown"
    except:
        return "Unknown"

# Function to update admin password
def update_admin_password(new_password):
    c.execute("UPDATE users SET password=? WHERE username='admin'", (new_password,))
    conn.commit()

def send_email(to_email, subject, body):
    from_email = "chbharath0779@gmail.com"
    from_password = "gnfq orjk evec sdwd"

    if not to_email or '@' not in to_email:
        return False

    msg = MIMEMultipart()
    msg['From'] = from_email
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(from_email, from_password)
            server.send_message(msg)
        return True
    except Exception as e:
        st.error(f"Email sending failed: {str(e)}")
        return False

def send_email_with_attachment(to_email, subject, body, img_file):
    from_email = "chbharath0779@gmail.com"
    from_password = "gnfq orjk evec sdwd"

    if not to_email or '@' not in to_email:
        return False

    msg = MIMEMultipart()
    msg['From'] = from_email
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        img_file.seek(0)
        msg.attach(MIMEImage(img_file.read(), name='mood_tracking_graph.png'))

        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(from_email, from_password)
            server.send_message(msg)
        return True
    except Exception as e:
        st.error(f"Email sending failed: {str(e)}")
        return False

# Initialize session state
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.login_time = None
    st.session_state.chat_active = False
    st.session_state.show_records = False
    st.session_state.show_graph = False
    st.session_state.show_monthly_graph = False

if "admin_logged_in" not in st.session_state:
    st.session_state.admin_logged_in = False

if "predictions" not in st.session_state:
    st.session_state.predictions = pd.DataFrame(columns=["Date", "Prediction", "Status"])

# Navigation
st.markdown("<h1 style='text-align: left; color:rgb(0, 1, 75);'>🤖 AI in Mental Health: Detecting Early Signs of Instability 🧠</h1>", unsafe_allow_html=True)

page = st.sidebar.selectbox("Select Page", ["Home", "Mood Tracking", "Personalized Recommendations", "Admin Dashboard", "Connect Page"])

if page == "Home":
    if not st.session_state.logged_in:
        option = st.radio("Login or Register", ["Login", "Register"])
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")

        if option == "Register":
            if st.button("Register"):
                if username.strip() == "":
                    st.error("Username cannot be empty!")
                elif register(username, password):
                    st.success("Registered successfully! Please log in.")
                else:
                    st.error("Username already exists!")

        else:  # Login
            if st.button("Login"):
                if username.strip() == "":
                    st.error("Username cannot be empty!")
                elif authenticate(username, password):
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.session_state.login_time = time.time()
                    st.success(f"Logged in successfully as {username}!")
                    st.rerun()
                else:
                    st.error("Invalid username or password")
    else:
        st.subheader(f"Welcome, {st.session_state.username}!")

        # Mental Health Prediction Section
        col1, col2 = st.columns(2)
        
        with col1:
            gender = st.selectbox("Gender", ["Male", "Female"])
            country = st.selectbox("Country", [
                'United States', 'Poland', 'Australia', 'Canada', 'United Kingdom',
                'South Africa', 'Sweden', 'New Zealand', 'Netherlands', 'India', 
                'Belgium', 'Ireland', 'France', 'Portugal', 'Brazil', 'Costa Rica', 
                'Russia', 'Germany', 'Switzerland', 'Finland', 'Israel', 'Italy', 
                'Bosnia and Herzegovina', 'Singapore', 'Nigeria', 'Croatia', 
                'Thailand', 'Denmark', 'Mexico', 'Greece', 'Moldova', 'Colombia', 
                'Georgia', 'Czech Republic', 'Philippines'
            ])
            occupation = st.selectbox("Occupation", ["Corporate", "Student", "Business", "Housewife", "Others"])
            self_employed = st.selectbox("Self Employed", ["Yes", "No"])
            family_history = st.selectbox("Family History", ["Yes", "No"])
            treatment = st.selectbox("Treatment", ["Yes", "No"])
            days_indoors = st.selectbox("Days Indoors", ['1-14 days', 'Go out Every day', 'More than 2 months', '15-30 days', '31-60 days'])
            growing_stress = st.selectbox("Growing Stress", ["Yes", "No", "Maybe"])
            changes_habits = st.selectbox("Changes in Habits", ["Yes", "No", "Maybe"])

        with col2:
            mental_health_history = st.selectbox("Mental Health History", ["Yes", "No", "Maybe"])
            mood_swings = st.selectbox("Mood Swings", ["Low", "Medium", "High"])
            coping_struggles = st.selectbox("Coping Struggles", ["Yes", "No"])
            work_interest = st.selectbox("Work Interest", ["Yes", "Maybe", "No"])
            social_weakness = st.selectbox("Social Weakness", ["Yes", "No", "Maybe"])
            mental_health_interview = st.selectbox("Mental Health Interview", ["Yes", "Maybe", "No"])
            care_options = st.selectbox("Care Options", ["Yes", "No", "Not sure"])

        input_data = {
            "Gender": gender,
            "Country": country,
            "Occupation": occupation,
            "self_employed": self_employed,
            "family_history": family_history,
            "treatment": treatment,
            "Days_Indoors": days_indoors,
            "Growing_Stress": growing_stress,
            "Changes_Habits": changes_habits,
            "Mental_Health_History": mental_health_history,
            "Mood_Swings": mood_swings,
            "Coping_Struggles": coping_struggles,
            "Work_Interest": work_interest,
            "Social_Weakness": social_weakness,
            "mental_health_interview": mental_health_interview,
            "care_options": care_options
        }

        if st.button("Predict"):
            with st.spinner("Making prediction..."):
                prediction, confidence_percentage = predict(input_data)
                status = map_to_status(prediction)
                
                st.success("Prediction completed!")
                st.write(f"**Predicted Instability Rate (0 to 8):** {prediction}")
                st.write(f"**Confidence:** {confidence_percentage:.2f}%")
                st.write(f"**Mental Health Status:** {status}")
                
                time_spent = int(time.time() - st.session_state.login_time) if st.session_state.login_time else 0
                save_prediction(st.session_state.username, datetime.datetime.now(), prediction, status, time_spent)
                st.session_state.predictions = fetch_predictions(st.session_state.username)

        if st.button("Logout"):
            if st.session_state.login_time:
                time_spent = int(time.time() - st.session_state.login_time)
                save_prediction(st.session_state.username, datetime.datetime.now(), 0, "Logged Out", time_spent)
            st.session_state.logged_in = False
            st.session_state.username = ""
            st.session_state.login_time = None
            st.session_state.predictions = pd.DataFrame(columns=["Date", "Prediction", "Status"])
            st.session_state.chat_active = False
            st.rerun()

elif page == "Mood Tracking":
    st.subheader("Mood Tracking Records")

    if st.session_state.logged_in:
        st.session_state.predictions = fetch_predictions(st.session_state.username)

        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("Show Mood Tracking Records"):
                st.session_state.show_records = not st.session_state.show_records

        with col2:
            if st.button("Show Mood Tracking Graph"):
                st.session_state.show_graph = not st.session_state.show_graph

        with col3:
            if st.button("Show Monthly Predictions Graph"):
                st.session_state.show_monthly_graph = not st.session_state.show_monthly_graph

        if st.session_state.show_records:
            if not st.session_state.predictions.empty:
                st.dataframe(st.session_state.predictions)
            else:
                st.info("No predictions recorded yet.")

        def save_mood_tracking_graph():
            if not st.session_state.predictions.empty:
                try:
                    status_counts = st.session_state.predictions['Status'].value_counts()
                    plt.figure(figsize=(10, 5))
                    plt.bar(status_counts.index, status_counts.values, color='skyblue', alpha=0.7)
                    plt.title('Mental Health Status Distribution', fontsize=16)
                    plt.xlabel('Mental Health Status', fontsize=12)
                    plt.ylabel('Count', fontsize=12)
                    plt.xticks(rotation=45)
                    plt.tight_layout()
                    img = io.BytesIO()
                    plt.savefig(img, format='png', dpi=100, bbox_inches='tight')
                    img.seek(0)
                    plt.close()
                    return img
                except Exception as e:
                    st.error(f"Error creating graph: {str(e)}")
                    return None
            return None

        if st.session_state.show_graph:
            if not st.session_state.predictions.empty:
                try:
                    status_counts = st.session_state.predictions['Status'].value_counts()
                    plt.figure(figsize=(10, 5))
                    plt.bar(status_counts.index, status_counts.values, color='skyblue', alpha=0.7)
                    plt.title('Mental Health Status Distribution', fontsize=16)
                    plt.xlabel('Mental Health Status', fontsize=12)
                    plt.ylabel('Count', fontsize=12)
                    plt.xticks(rotation=45)
                    plt.tight_layout()
                    st.pyplot(plt)
                except Exception as e:
                    st.error(f"Error displaying graph: {str(e)}")
            else:
                st.info("No predictions recorded yet.")

        if st.session_state.show_monthly_graph:
            if not st.session_state.predictions.empty:
                try:
                    st.session_state.predictions['Date'] = pd.to_datetime(st.session_state.predictions['Date'])
                    monthly_counts = st.session_state.predictions.groupby(st.session_state.predictions['Date'].dt.to_period('M')).size()
                    
                    if not monthly_counts.empty:
                        plt.figure(figsize=(10, 5))
                        plt.plot(monthly_counts.index.astype(str), monthly_counts.values, marker='o', color='orange', alpha=0.7)
                        plt.title('Monthly Predictions Count', fontsize=16)
                        plt.xlabel('Month', fontsize=12)
                        plt.ylabel('Count of Predictions', fontsize=12)
                        plt.xticks(rotation=45)
                        plt.tight_layout()
                        st.pyplot(plt)
                    else:
                        st.info("No monthly data available.")
                except Exception as e:
                    st.error(f"Error displaying monthly graph: {str(e)}")
            else:
                st.info("No predictions recorded yet.")

        st.subheader("Request Your Mental Health Report")
        name = st.text_input("Your Name")
        email = st.text_input("Your Email")

        if st.button("Send Report"):
            if name and email:
                if "@" in email and "." in email:
                    if not st.session_state.predictions.empty:
                        with st.spinner("Generating and sending report..."):
                            try:
                                latest_prediction = st.session_state.predictions.iloc[-1]
                                latest_status = latest_prediction['Status']
                                latest_date = latest_prediction['Date']

                                average_status = st.session_state.predictions['Status'].value_counts().idxmax()

                                recommendations = []
                                if average_status == "Stable or Low Instability":
                                    recommendations = [
                                        "Maintain your current healthy habits.",
                                        "Consider sharing your positive experiences with others.",
                                        "Stay engaged in activities that bring you joy."
                                    ]
                                elif average_status == "Moderate Instability":
                                    recommendations = [
                                        "Reflect on your feelings and consider seeking support.",
                                        "Engage in activities that promote relaxation and well-being.",
                                        "Stay connected with friends and family."
                                    ]
                                elif average_status == "High Instability or Severe Instability":
                                    recommendations = [
                                        "It may be beneficial to consult with a mental health professional.",
                                        "Consider developing a self-care plan to manage stress.",
                                        "Reach out to support groups or community resources."
                                    ]
                                else:
                                    recommendations = ["Continue monitoring your mental health regularly."]

                                report_content = f"""
Dear {name},

We hope this message finds you well. Below is your mental health report based on your recent mood tracking data.

Latest Prediction Status: {latest_status}
Latest Prediction Date: {latest_date}
Average Prediction Status: {average_status}

Personalized Recommendations:
- {chr(10).join(['- ' + r for r in recommendations])}

Thank you for using our service. If you have any questions or need further assistance, please do not hesitate to reach out.

Best regards,
Mental Health Support Team
"""

                                img = save_mood_tracking_graph()
                                if img:
                                    if send_email_with_attachment(email, "Your Mental Health Report", report_content, img):
                                        st.success("Report sent successfully!")
                                    else:
                                        st.error("Failed to send the report. Please check your email and try again.")
                                else:
                                    # Send without attachment
                                    if send_email(email, "Your Mental Health Report", report_content):
                                        st.success("Report sent successfully (without graph)!")
                                    else:
                                        st.error("Failed to send the report. Please try again later.")
                            except Exception as e:
                                st.error(f"Error generating report: {str(e)}")
                    else:
                        st.warning("No prediction data available to generate report. Please make some predictions first.")
                else:
                    st.error("Please enter a valid email address.")
            else:
                st.error("Please enter both your name and email.")
    else:
        st.warning("Please log in to access mood tracking.")

elif page == "Connect Page":
    st.subheader("Chat Room")

    if st.session_state.logged_in:
        security_code = st.text_input("Enter Security Code (use 123456)", type="password")
        if st.button("Join Chat"):
            if security_code == "123456":
                st.session_state.chat_active = True
                st.success("You have joined the chat room!")
            else:
                st.error("Invalid security code. Please try again.")

        if "chat_active" in st.session_state and st.session_state.chat_active:
            st.markdown("---")
            messages = fetch_chat_messages()
            
            # Display messages
            for message_id, username, message, timestamp in messages:
                col1, col2 = st.columns([0.9, 0.1])
                with col1:
                    if username == st.session_state.username:
                        st.markdown(f"<div style='text-align: right; background-color: #e3f2fd; padding: 10px; border-radius: 10px; margin: 5px;'><strong>You</strong> ({timestamp}):<br>{message}</div>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"<div style='text-align: left; background-color: #f5f5f5; padding: 10px; border-radius: 10px; margin: 5px;'><strong>{username}</strong> ({timestamp}):<br>{message}</div>", unsafe_allow_html=True)
                with col2:
                    if username == st.session_state.username:
                        if st.button("🗑️", key=f"del_{message_id}"):
                            delete_chat_message(message_id)
                            st.rerun()

            st.markdown("---")
            new_message = st.text_input("Type your message here...")
            col1, col2 = st.columns([0.8, 0.2])
            with col1:
                if st.button("Send Message"):
                    if new_message.strip() != "":
                        save_chat_message(st.session_state.username, new_message)
                        st.rerun()
                    else:
                        st.error("Message cannot be empty.")
            with col2:
                if st.button("Leave Chat"):
                    st.session_state.chat_active = False
                    st.success("You have left the chat room.")
                    st.rerun()

        st.markdown("---")
        st.subheader("Connect with a Psychologist or Consultant")
        st.info("If you need to talk, our skilled, judgment-free counselors are here to provide compassionate support.")

        contact_method = st.selectbox("Select a contact method", ["Select", "Text", "Email", "Video Call"])

        if contact_method == "Text":
            with st.form("text_support_form"):
                name = st.text_input("Enter your name:")
                age = st.number_input("Enter your age:", min_value=1, max_value=120, value=25)
                gender = st.selectbox("Select your gender:", ["Male", "Female", "Other"])
                whatsapp_number = st.text_input("Enter your WhatsApp number:")
                submit = st.form_submit_button("Request Text Support")
                
                if submit:
                    if name and whatsapp_number:
                        st.success(f"Text support request received from {name}. A counselor will reach out to you shortly via WhatsApp.")
                    else:
                        st.error("Please fill in all fields.")

        elif contact_method == "Email":
            with st.form("email_support_form"):
                name = st.text_input("Enter your name:")
                email_address = st.text_input("Enter your email address:")
                submit = st.form_submit_button("Request Email Support")
                
                if submit:
                    if name and email_address:
                        if "@" in email_address and "." in email_address:
                            subject = "Support Request Received"
                            body = f"""\
Dear {name},

Thank you for reaching out to us. We have received your request for support via email. A counselor will contact you shortly to provide the assistance you need.

Best regards,
Mental Health Support Team
"""
                            with st.spinner("Sending email..."):
                                if send_email(email_address, subject, body):
                                    st.success(f"Email support request received from {name}.")
                                else:
                                    st.error("Failed to send email. Please try again later.")
                        else:
                            st.error("Please enter a valid email address.")
                    else:
                        st.error("Please fill in all fields.")

        elif contact_method == "Video Call":
            with st.form("video_call_form"):
                name = st.text_input("Enter your name:")
                email = st.text_input("Enter your email:")
                phone = st.text_input("Enter your phone number:")
                date = st.date_input("Select a date for the video call:", min_value=datetime.date.today())
                time_slot = st.time_input("Select a time for the video call:")
                submit = st.form_submit_button("Request Video Call")
                
                if submit:
                    if name and email and phone and date and time_slot:
                        if "@" in email and "." in email:
                            subject = "Video Call Request Confirmation"
                            body = f"""\
Dear {name},

We have received your request for a video call. You have scheduled a call on {date} at {time_slot}. 

A counselor will contact you with the video call link shortly before your scheduled time.

Best regards,
Mental Health Support Team
"""
                            with st.spinner("Sending confirmation..."):
                                if send_email(email, subject, body):
                                    st.success(f"Video call request received from {name}. Confirmation sent to {email}")
                                else:
                                    st.error("Failed to send email. Please try again later.")
                        else:
                            st.error("Please enter a valid email address.")
                    else:
                        st.error("Please fill in all fields.")
    else:
        st.warning("Please log in to access the chat room.")

elif page == "Personalized Recommendations":
    st.subheader("Personalized Recommendations")

    if st.session_state.logged_in:
        user_predictions = fetch_predictions(st.session_state.username)

        if not user_predictions.empty:
            latest_status = user_predictions['Status'].iloc[-1]
            average_status = user_predictions['Status'].value_counts().idxmax()

            col1, col2 = st.columns(2)

            with col1:
                if st.button("Recommendation based on Latest Prediction"):
                    st.write(f"Your latest mental health status: **{latest_status}**")
                    
                    if latest_status == "Stable or Low Instability":
                        recommendations = [
                            "Continue your daily routine and maintain healthy habits.",
                            "Engage in physical activities like walking or yoga.",
                            "Practice mindfulness or meditation for relaxation.",
                            "Stay connected with friends and family."
                        ]
                    elif latest_status == "Moderate Instability":
                        recommendations = [
                            "Consider talking to a friend or family member about your feelings.",
                            "Try journaling to express your thoughts and emotions.",
                            "Engage in creative activities like drawing or music.",
                            "Practice deep breathing exercises when feeling stressed."
                        ]
                    elif latest_status == "High Instability or Severe Instability":
                        recommendations = [
                            "Reach out to a mental health professional for support.",
                            "Practice deep breathing exercises to manage anxiety.",
                            "Limit exposure to stressful situations and take breaks.",
                            "Consider joining a support group for additional help."
                        ]
                    else:
                        recommendations = ["Continue monitoring your mental health regularly."]
                    
                    st.write("### Recommendations:")
                    for i, rec in enumerate(recommendations, 1):
                        st.write(f"{i}. {rec}")

            with col2:
                if st.button("Recommendation based on Average Mental Health Status"):
                    st.write(f"Your average mental health status: **{average_status}**")
                    
                    if average_status == "Stable or Low Instability":
                        recommendations = [
                            "Maintain your current healthy habits.",
                            "Consider sharing your positive experiences with others.",
                            "Stay engaged in activities that bring you joy.",
                            "Regular exercise and proper sleep are important."
                        ]
                    elif average_status == "Moderate Instability":
                        recommendations = [
                            "Reflect on your feelings and consider seeking support.",
                            "Engage in activities that promote relaxation and well-being.",
                            "Stay connected with friends and family.",
                            "Consider mindfulness or meditation practices."
                        ]
                    elif average_status == "High Instability or Severe Instability":
                        recommendations = [
                            "It may be beneficial to consult with a mental health professional.",
                            "Consider developing a self-care plan to manage stress.",
                            "Reach out to support groups or community resources.",
                            "Practice stress management techniques daily."
                        ]
                    else:
                        recommendations = ["Continue monitoring your mental health regularly."]
                    
                    st.write("### Recommendations:")
                    for i, rec in enumerate(recommendations, 1):
                        st.write(f"{i}. {rec}")

            st.markdown("---")
            st.markdown("<h2 style='text-align: center;'>Mental Health Resources and Support</h2>", unsafe_allow_html=True)

            if st.button("Show Mental Health Resources"):
                with st.expander("📞 Hotlines", expanded=True):
                    st.write("• **National Suicide Prevention Lifeline**: Call 1-800-273-TALK (1-800-273-8255)")
                    st.write("• **Crisis Text Line**: Text HOME to 741741")
                    st.write("• **SAMHSA National Helpline**: Call 1-800-662-HELP (1-800-662-4357)")
                
                with st.expander("💻 Online Therapy Options"):
                    st.write("• [BetterHelp](https://www.betterhelp.com/) - Online therapy with licensed professionals.")
                    st.write("• [Talkspace](https://www.talkspace.com/) - Therapy via text, audio, and video messaging.")
                
                with st.expander("📚 Articles and Educational Materials"):
                    st.write("• [Mental Health America](https://www.mhanational.org/) - Resources and information on mental health.")
                    st.write("• [NAMI](https://www.nami.org/) - Information and support for mental health conditions.")
                
                with st.expander("📍 Local Mental Health Services"):
                    st.write("Find local mental health services in your area by visiting [Psychology Today](https://www.psychologytoday.com/us/therapists)")
        else:
            st.info("No mood tracking data available. Please make predictions first to get personalized recommendations.")
    else:
        st.warning("Please log in to access personalized recommendations.")

elif page == "Admin Dashboard":
    if not st.session_state.admin_logged_in:
        st.subheader("Admin Login")
        with st.form("admin_login_form"):
            admin_username = st.text_input("Admin Username")
            admin_password = st.text_input("Admin Password", type="password")
            submit = st.form_submit_button("Admin Login")
            
            if submit:
                if authenticate(admin_username, admin_password):
                    st.session_state.admin_logged_in = True
                    st.success("Admin logged in successfully!")
                    st.rerun()
                else:
                    st.error("Invalid admin username or password")
    else:
        st.title("Admin Dashboard")

        # Password change section
        with st.expander("Change Admin Password", expanded=False):
            with st.form("change_password_form"):
                new_password = st.text_input("New Admin Password", type="password")
                confirm_password = st.text_input("Confirm New Admin Password", type="password")
                
                if st.form_submit_button("Change Password"):
                    if new_password == confirm_password:
                        if len(new_password) >= 6:
                            update_admin_password(new_password)
                            st.success("Admin password updated successfully!")
                        else:
                            st.error("Password must be at least 6 characters long!")
                    else:
                        st.error("Passwords do not match!")

        # Fetch all users
        c.execute("SELECT username FROM users")
        users = c.fetchall()
        user_list = [user[0] for user in users]

        # Display total users
        col1, col2, col3 = st.columns(3)
        with col2:
            st.metric("Total Users", len(user_list))

        if user_list:
            selected_user = st.selectbox("Select a user to view details", user_list)

            if st.button("View User Details"):
                user_predictions = fetch_predictions(selected_user)

                if not user_predictions.empty:
                    st.subheader(f"Details for {selected_user}")

                    total_predictions = len(user_predictions)
                    average_status = user_predictions['Status'].value_counts().idxmax()
                    last_prediction_date = user_predictions['Date'].max()

                    # Display metrics
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Total Predictions", total_predictions)
                    col2.metric("Average Status", average_status)
                    col3.metric("Last Prediction", last_prediction_date.split()[0] if ' ' in str(last_prediction_date) else last_prediction_date)

                    # Display graph
                    try:
                        status_counts = user_predictions['Status'].value_counts()
                        plt.figure(figsize=(10, 5))
                        plt.bar(status_counts.index, status_counts.values, color='blue', alpha=0.7)
                        plt.title(f'Mental Health Status Distribution for {selected_user}', fontsize=16)
                        plt.xlabel('Mental Health Status', fontsize=12)
                        plt.ylabel('Count', fontsize=12)
                        plt.xticks(rotation=45)
                        plt.tight_layout()
                        st.pyplot(plt)
                    except Exception as e:
                        st.error(f"Error displaying graph: {str(e)}")
                else:
                    st.info(f"No mood history recorded for {selected_user}.")

            # User Deletion Section
            with st.expander("Delete User", expanded=False):
                if selected_user != "admin":
                    if st.button(f"Delete User '{selected_user}'", type="primary"):
                        c.execute("DELETE FROM users WHERE username=?", (selected_user,))
                        c.execute("DELETE FROM predictions WHERE username=?", (selected_user,))
                        conn.commit()
                        st.success(f"User '{selected_user}' has been deleted successfully.")
                        st.rerun()
                else:
                    st.warning("Admin user cannot be deleted!")

            # Overall Activity Monitoring
            st.subheader("Overall User Activity Monitoring")
            
            c.execute("SELECT username, date, prediction, status FROM predictions")
            predictions = c.fetchall()
            
            if predictions:
                predictions_df = pd.DataFrame(predictions, columns=["Username", "Date", "Prediction", "Status"])
                predictions_df['Date'] = pd.to_datetime(predictions_df['Date'], errors='coerce')

                # Calculate metrics
                total_users_active = predictions_df['Username'].nunique()
                weekday_counts = predictions_df['Date'].dt.day_name().value_counts()
                most_active_weekday = weekday_counts.idxmax() if not weekday_counts.empty else "N/A"
                
                filtered_predictions_df = predictions_df[predictions_df['Status'] != "Logged Out"]
                most_predicted_status = filtered_predictions_df['Status'].value_counts().idxmax() if not filtered_predictions_df.empty else "N/A"

                # Display metrics
                col1, col2, col3 = st.columns(3)
                col1.metric("Total Active Users", total_users_active)
                col2.metric("Most Active Weekday", most_active_weekday)
                col3.metric("Most Predicted Status", most_predicted_status)

                # Graphs
                col1, col2 = st.columns(2)
                
                with col1:
                    if st.button("Show Active Users by Weekday"):
                        try:
                            active_users_by_weekday = predictions_df.groupby(predictions_df['Date'].dt.day_name())['Username'].nunique().reindex(
                                ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'], fill_value=0)
                            plt.figure(figsize=(10, 5))
                            plt.bar(active_users_by_weekday.index, active_users_by_weekday.values, color='blue', alpha=0.7)
                            plt.title('Total Active Users by Weekday', fontsize=16)
                            plt.ylabel('Count of Active Users', fontsize=12)
                            plt.xlabel('Weekday', fontsize=12)
                            plt.xticks(rotation=45)
                            plt.tight_layout()
                            st.pyplot(plt)
                        except Exception as e:
                            st.error(f"Error displaying graph: {str(e)}")

                with col2:
                    if st.button("Show Most Predicted Status"):
                        try:
                            status_counts = filtered_predictions_df['Status'].value_counts()
                            plt.figure(figsize=(10, 5))
                            plt.bar(status_counts.index, status_counts.values, color='green', alpha=0.7)
                            plt.title('Most Predicted Status', fontsize=16)
                            plt.xlabel('Status', fontsize=12)
                            plt.ylabel('Count', fontsize=12)
                            plt.xticks(rotation=45)
                            plt.tight_layout()
                            st.pyplot(plt)
                        except Exception as e:
                            st.error(f"Error displaying graph: {str(e)}")
            else:
                st.info("No predictions recorded yet in the database.")
        else:
            st.info("No users found in the database.")

        if st.button("Logout from Admin"):
            st.session_state.admin_logged_in = False
            st.rerun()
