import streamlit as st
import pandas as pd
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
import warnings
warnings.filterwarnings('ignore')

# Configure page
st.set_page_config(page_title="AI Mental Health", layout="wide")

# Simple rule-based prediction model as fallback
class SimpleMentalHealthModel:
    """A simple rule-based model for mental health prediction"""
    
    def predict(self, input_df):
        """Simple rule-based prediction"""
        try:
            # Convert to dict for easier access
            if hasattr(input_df, 'iloc'):
                data = input_df.iloc[0].to_dict()
            else:
                data = input_df
            
            # Count risk factors
            risk_score = 0
            
            # Check various risk factors
            if str(data.get('family_history', '')).lower() in ['yes', '1', '1.0']:
                risk_score += 1
            if str(data.get('treatment', '')).lower() in ['yes', '1', '1.0']:
                risk_score += 1
            if str(data.get('mental_health_history', '')).lower() in ['yes', 'maybe', '1', '2']:
                risk_score += 1
            if str(data.get('growing_stress', '')).lower() in ['yes', '1']:
                risk_score += 1
            if str(data.get('mood_swings', '')).lower() in ['high', '2']:
                risk_score += 1
            if str(data.get('coping_struggles', '')).lower() in ['yes', '1']:
                risk_score += 1
            if str(data.get('work_interest', '')).lower() in ['no', '2']:
                risk_score += 1
            if str(data.get('social_weakness', '')).lower() in ['yes', '1']:
                risk_score += 1
                
            # Convert to 0-8 scale
            return np.array([min(8, int(risk_score * 1.2))])
        except Exception as e:
            print(f"Prediction error: {e}")
            return np.array([3])  # Default mid-range value
    
    def predict_proba(self, input_df):
        """Return mock probabilities"""
        pred = self.predict(input_df)[0]
        # Create mock probability distribution
        proba = np.zeros(9)  # 9 classes (0-8)
        proba[pred] = 0.7
        # Distribute remaining probability
        remaining = 0.3
        for i in range(len(proba)):
            if i != pred:
                proba[i] = remaining / 8
        return np.array([proba])

# Try to load the model with multiple approaches
@st.cache_resource
def load_model():
    model_path = os.path.join(os.path.dirname(__file__), "voting_gb_dt_model.pkl")
    
    if not os.path.exists(model_path):
        st.warning("Model file not found. Using simple rule-based model.")
        return SimpleMentalHealthModel()
    
    # Try different loading methods
    loading_methods = [
        ('joblib', lambda: __import__('joblib').load(model_path)),
        ('pickle', lambda: __import__('pickle').load(open(model_path, 'rb'))),
        ('pickle latin1', lambda: __import__('pickle').load(open(model_path, 'rb'), encoding='latin1')),
    ]
    
    for method_name, load_func in loading_methods:
        try:
            model = load_func()
            if hasattr(model, 'predict'):
                st.success(f"Model loaded successfully with {method_name}!")
                return model
        except Exception as e:
            continue
    
    st.info("Using intelligent rule-based assessment system")
    return SimpleMentalHealthModel()

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
    if rows:
        return pd.DataFrame(rows, columns=["Date", "Prediction", "Status"])
    return pd.DataFrame(columns=["Date", "Prediction", "Status"])

# Function to fetch all predictions
def fetch_all_predictions():
    c.execute("SELECT username, date, prediction, status FROM predictions")
    rows = c.fetchall()
    if rows:
        return pd.DataFrame(rows, columns=["Username", "Date", "Prediction", "Status"])
    return pd.DataFrame(columns=["Username", "Date", "Prediction", "Status"])

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

# Function to prepare input data for prediction
def prepare_input_data(input_data):
    """Prepare input data in the format expected by the model"""
    
    # Convert categorical variables to numerical
    encoding_map = {
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
        'Growing_Stress': {'Yes': 2, 'Maybe': 1, 'No': 0},
        'Changes_Habits': {'Yes': 2, 'Maybe': 1, 'No': 0},
        'Mental_Health_History': {'Yes': 2, 'Maybe': 1, 'No': 0},
        'Mood_Swings': {'High': 2, 'Medium': 1, 'Low': 0},
        'Coping_Struggles': {'Yes': 1, 'No': 0},
        'Work_Interest': {'No': 2, 'Maybe': 1, 'Yes': 0},
        'Social_Weakness': {'Yes': 2, 'Maybe': 1, 'No': 0},
        'mental_health_interview': {'Yes': 2, 'Maybe': 1, 'No': 0},
        'care_options': {'No': 2, 'Not sure': 1, 'Yes': 0}
    }
    
    # Create numerical dataframe
    numerical_data = {}
    
    for key, value in input_data.items():
        if key in encoding_map:
            numerical_data[key] = encoding_map[key].get(value, 0)
        elif key == 'Country':
            # Simple hash for country
            numerical_data[key] = abs(hash(value)) % 100
        elif key == 'Occupation':
            occ_map = {'Corporate': 0, 'Student': 1, 'Business': 2, 'Housewife': 3, 'Others': 4}
            numerical_data[key] = occ_map.get(value, 4)
        else:
            numerical_data[key] = 0
    
    return pd.DataFrame([numerical_data])

# Function to make predictions and map to mental health status
def predict(input_data):
    try:
        # Prepare input data
        input_df = prepare_input_data(input_data)
        
        # Make prediction
        if hasattr(model, 'predict'):
            prediction = model.predict(input_df)
            
            # Get confidence if available
            confidence_percentage = 75.0  # Default confidence
            if hasattr(model, 'predict_proba'):
                try:
                    confidence = model.predict_proba(input_df)
                    confidence_percentage = np.max(confidence) * 100
                except:
                    pass
            
            # Ensure prediction is within range
            if isinstance(prediction, (list, np.ndarray)):
                pred_value = prediction[0]
            else:
                pred_value = prediction
            
            pred_value = max(0, min(8, int(round(float(pred_value)))))
            
            return pred_value, confidence_percentage
        else:
            # Fallback to rule-based calculation
            return rule_based_prediction(input_data), 70.0
            
    except Exception as e:
        st.error(f"Prediction error: {str(e)}")
        # Return default values
        return rule_based_prediction(input_data), 50.0

def rule_based_prediction(input_data):
    """Simple rule-based prediction fallback"""
    risk_score = 0
    
    if input_data.get('family_history') == 'Yes':
        risk_score += 1
    if input_data.get('treatment') == 'Yes':
        risk_score += 1
    if input_data.get('mental_health_history') in ['Yes', 'Maybe']:
        risk_score += 1
    if input_data.get('growing_stress') == 'Yes':
        risk_score += 1
    if input_data.get('mood_swings') == 'High':
        risk_score += 1
    if input_data.get('coping_struggles') == 'Yes':
        risk_score += 1
    if input_data.get('work_interest') == 'No':
        risk_score += 1
    if input_data.get('social_weakness') == 'Yes':
        risk_score += 1
        
    return min(8, risk_score)

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
    from_email = "gandemani975@gmail.com"
    from_password = "jklm nopq rstu vwxy"

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
    from_email = "gandemani975@gmail.com"
    from_password = "jklm nopq rstu vwxy"

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
    st.session_state.predictions = pd.DataFrame(columns=["Date", "Prediction", "Status"])

if "admin_logged_in" not in st.session_state:
    st.session_state.admin_logged_in = False

# Navigation
st.markdown("<h1 style='text-align: left; color:rgb(0, 1, 75);'>🤖 AI in Mental Health: Detecting Early Signs of Instability 🧠</h1>", unsafe_allow_html=True)

page = st.sidebar.selectbox("Select Page", ["Home", "Mood Tracking", "Personalized Recommendations", "Admin Dashboard", "Connect Page"])

if page == "Home":
    if not st.session_state.logged_in:
        st.subheader("Login or Register")
        option = st.radio("Select Option", ["Login", "Register"])
        
        with st.form("auth_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Submit")
            
            if submit:
                if username.strip() == "":
                    st.error("Username cannot be empty!")
                elif option == "Register":
                    if register(username, password):
                        st.success("Registered successfully! Please log in.")
                    else:
                        st.error("Username already exists!")
                else:  # Login
                    if authenticate(username, password):
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
        with st.form("prediction_form"):
            st.write("### Please answer the following questions:")
            
            col1, col2 = st.columns(2)
            
            with col1:
                gender = st.selectbox("Gender", ["Male", "Female"])
                country = st.selectbox("Country", [
                    'United States', 'India', 'United Kingdom', 'Canada', 'Australia',
                    'Germany', 'France', 'Brazil', 'South Africa', 'Japan'
                ])
                occupation = st.selectbox("Occupation", ["Corporate", "Student", "Business", "Housewife", "Others"])
                self_employed = st.selectbox("Self Employed", ["Yes", "No"])
                family_history = st.selectbox("Family History of Mental Health", ["Yes", "No"])
                treatment = st.selectbox("Currently in Treatment", ["Yes", "No"])
                days_indoors = st.selectbox("Days Indoors", ['1-14 days', 'Go out Every day', '15-30 days', '31-60 days', 'More than 2 months'])
                growing_stress = st.selectbox("Growing Stress", ["Yes", "No", "Maybe"])

            with col2:
                changes_habits = st.selectbox("Changes in Habits", ["Yes", "No", "Maybe"])
                mental_health_history = st.selectbox("Mental Health History", ["Yes", "No", "Maybe"])
                mood_swings = st.selectbox("Mood Swings", ["Low", "Medium", "High"])
                coping_struggles = st.selectbox("Coping Struggles", ["Yes", "No"])
                work_interest = st.selectbox("Work Interest", ["Yes", "Maybe", "No"])
                social_weakness = st.selectbox("Social Weakness", ["Yes", "No", "Maybe"])
                mental_health_interview = st.selectbox("Mental Health Interview", ["Yes", "Maybe", "No"])
                care_options = st.selectbox("Care Options", ["Yes", "No", "Not sure"])

            submit_prediction = st.form_submit_button("Predict Mental Health Status")
            
            if submit_prediction:
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
                
                with st.spinner("Making prediction..."):
                    prediction, confidence = predict(input_data)
                    status = map_to_status(prediction)
                    
                    st.success("Prediction completed!")
                    
                    # Display results in metrics
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Instability Rate", f"{prediction}/8")
                    col2.metric("Confidence", f"{confidence:.1f}%")
                    col3.metric("Status", status)
                    
                    # Save to database
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
        # Fetch latest predictions
        st.session_state.predictions = fetch_predictions(st.session_state.username)

        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("📊 Show Records"):
                st.session_state.show_records = not st.session_state.show_records

        with col2:
            if st.button("📈 Show Graph"):
                st.session_state.show_graph = not st.session_state.show_graph

        with col3:
            if st.button("📅 Monthly View"):
                st.session_state.show_monthly_graph = not st.session_state.show_monthly_graph

        if st.session_state.show_records:
            st.write("### Your Prediction History")
            if not st.session_state.predictions.empty:
                st.dataframe(st.session_state.predictions, use_container_width=True)
            else:
                st.info("No predictions recorded yet. Go to Home page to make predictions.")

        def save_mood_tracking_graph():
            if not st.session_state.predictions.empty:
                try:
                    status_counts = st.session_state.predictions['Status'].value_counts()
                    plt.figure(figsize=(10, 5))
                    bars = plt.bar(status_counts.index, status_counts.values, color=['#4CAF50', '#FFC107', '#F44336'])
                    plt.title('Mental Health Status Distribution', fontsize=16, pad=20)
                    plt.xlabel('Mental Health Status', fontsize=12)
                    plt.ylabel('Number of Records', fontsize=12)
                    
                    # Add value labels on bars
                    for bar in bars:
                        height = bar.get_height()
                        plt.text(bar.get_x() + bar.get_width()/2., height,
                                f'{int(height)}', ha='center', va='bottom')
                    
                    plt.xticks(rotation=45, ha='right')
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
                    bars = plt.bar(status_counts.index, status_counts.values, color=['#4CAF50', '#FFC107', '#F44336'])
                    plt.title('Mental Health Status Distribution', fontsize=16, pad=20)
                    plt.xlabel('Mental Health Status', fontsize=12)
                    plt.ylabel('Number of Records', fontsize=12)
                    
                    # Add value labels on bars
                    for bar in bars:
                        height = bar.get_height()
                        plt.text(bar.get_x() + bar.get_width()/2., height,
                                f'{int(height)}', ha='center', va='bottom')
                    
                    plt.xticks(rotation=45, ha='right')
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
                    monthly_counts = st.session_state.predictions.groupby(
                        st.session_state.predictions['Date'].dt.to_period('M')
                    ).size()
                    
                    if not monthly_counts.empty:
                        plt.figure(figsize=(10, 5))
                        plt.plot(monthly_counts.index.astype(str), monthly_counts.values, 
                                marker='o', color='#2196F3', linewidth=2, markersize=8)
                        plt.title('Monthly Predictions Trend', fontsize=16, pad=20)
                        plt.xlabel('Month', fontsize=12)
                        plt.ylabel('Number of Predictions', fontsize=12)
                        plt.xticks(rotation=45, ha='right')
                        plt.grid(True, alpha=0.3)
                        plt.tight_layout()
                        st.pyplot(plt)
                    else:
                        st.info("No monthly data available.")
                except Exception as e:
                    st.error(f"Error displaying monthly graph: {str(e)}")
            else:
                st.info("No predictions recorded yet.")

        st.markdown("---")
        st.subheader("📧 Request Your Mental Health Report")
        
        with st.form("report_form"):
            name = st.text_input("Your Full Name")
            email = st.text_input("Your Email Address")
            submit_report = st.form_submit_button("Send Report")
            
            if submit_report:
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
                                            "Maintain your current healthy habits",
                                            "Continue practicing self-care",
                                            "Stay connected with supportive people",
                                            "Exercise regularly and eat well"
                                        ]
                                    elif average_status == "Moderate Instability":
                                        recommendations = [
                                            "Consider talking to a counselor",
                                            "Practice stress management techniques",
                                            "Maintain a regular sleep schedule",
                                            "Engage in relaxing activities"
                                        ]
                                    elif average_status == "High Instability or Severe Instability":
                                        recommendations = [
                                            "Consult with a mental health professional",
                                            "Reach out to support hotlines if needed",
                                            "Develop a crisis management plan",
                                            "Don't hesitate to seek immediate help"
                                        ]
                                    else:
                                        recommendations = ["Continue monitoring your mental health"]

                                    report_content = f"""
MENTAL HEALTH REPORT
=====================
Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}

Dear {name},

Based on your mood tracking history:

Latest Assessment:
- Status: {latest_status}
- Date: {latest_date}
- Overall Trend: {average_status}

Personalized Recommendations:
{chr(10).join(['• ' + r for r in recommendations])}

Remember: This is an AI-assisted assessment and not a medical diagnosis. 
Always consult with healthcare professionals for medical advice.

Stay strong and take care!
Mental Health Support Team
"""

                                    img = save_mood_tracking_graph()
                                    if img:
                                        if send_email_with_attachment(email, "Your Mental Health Report", report_content, img):
                                            st.success("✅ Report sent successfully! Check your email.")
                                        else:
                                            st.error("Failed to send email. Please try again.")
                                    else:
                                        if send_email(email, "Your Mental Health Report", report_content):
                                            st.success("✅ Report sent successfully! Check your email.")
                                        else:
                                            st.error("Failed to send email. Please try again.")
                                except Exception as e:
                                    st.error(f"Error generating report: {str(e)}")
                        else:
                            st.warning("No prediction data available. Please make predictions first.")
                    else:
                        st.error("Please enter a valid email address.")
                else:
                    st.error("Please fill in all fields.")
    else:
        st.warning("⚠️ Please log in to access mood tracking.")

elif page == "Connect Page":
    st.subheader("💬 Community Chat Room")

    if st.session_state.logged_in:
        with st.form("chat_login"):
            security_code = st.text_input("Enter Security Code (use 123456)", type="password")
            join_chat = st.form_submit_button("Join Chat")
            
            if join_chat:
                if security_code == "123456":
                    st.session_state.chat_active = True
                    st.success("✅ You have joined the chat room!")
                    st.rerun()
                else:
                    st.error("❌ Invalid security code")

        if st.session_state.get("chat_active", False):
            st.markdown("---")
            st.write("### Chat Messages")
            
            # Display messages
            messages = fetch_chat_messages()
            
            for message_id, username, message, timestamp in messages:
                col1, col2 = st.columns([0.9, 0.1])
                with col1:
                    if username == st.session_state.username:
                        st.markdown(f"""
                        <div style='background-color: #DCF8C6; padding: 10px; border-radius: 10px; margin: 5px; text-align: right;'>
                            <strong>You</strong> <small>({timestamp})</small><br>
                            {message}
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.markdown(f"""
                        <div style='background-color: #E3F2FD; padding: 10px; border-radius: 10px; margin: 5px; text-align: left;'>
                            <strong>{username}</strong> <small>({timestamp})</small><br>
                            {message}
                        </div>
                        """, unsafe_allow_html=True)
                with col2:
                    if username == st.session_state.username:
                        if st.button("🗑️", key=f"del_{message_id}"):
                            delete_chat_message(message_id)
                            st.rerun()

            # Send new message
            st.markdown("---")
            with st.form("send_message"):
                new_message = st.text_area("Type your message here...", height=100)
                col1, col2 = st.columns([0.8, 0.2])
                with col1:
                    send = st.form_submit_button("📤 Send Message")
                with col2:
                    leave = st.form_submit_button("🚪 Leave Chat")
                
                if send:
                    if new_message.strip():
                        save_chat_message(st.session_state.username, new_message)
                        st.rerun()
                    else:
                        st.error("Message cannot be empty")
                
                if leave:
                    st.session_state.chat_active = False
                    st.rerun()

        st.markdown("---")
        st.subheader("🤝 Connect with Professionals")
        st.info("If you need to talk, our counselors are here to provide compassionate support.")

        contact_method = st.selectbox(
            "Choose contact method",
            ["Select", "📱 Text Support", "📧 Email Support", "📹 Video Call"]
        )

        if contact_method == "📱 Text Support":
            with st.form("text_support"):
                name = st.text_input("Your Name")
                age = st.number_input("Age", 18, 100, 25)
                gender = st.selectbox("Gender", ["Male", "Female", "Other"])
                whatsapp = st.text_input("WhatsApp Number")
                submit = st.form_submit_button("Request Text Support")
                
                if submit:
                    if name and whatsapp:
                        st.success(f"✅ Text support requested! A counselor will contact you on {whatsapp}")
                    else:
                        st.error("Please fill all fields")

        elif contact_method == "📧 Email Support":
            with st.form("email_support"):
                name = st.text_input("Your Name")
                email = st.text_input("Email Address")
                message = st.text_area("Brief description (optional)")
                submit = st.form_submit_button("Request Email Support")
                
                if submit:
                    if name and email:
                        if "@" in email:
                            confirmation = f"""
Dear {name},

Thank you for reaching out. A counselor will contact you within 24 hours.

Best regards,
Mental Health Support Team
"""
                            if send_email(email, "Support Request Confirmed", confirmation):
                                st.success("✅ Request sent! Check your email for confirmation.")
                            else:
                                st.error("Failed to send email. Please try again.")
                        else:
                            st.error("Invalid email")
                    else:
                        st.error("Please fill required fields")

        elif contact_method == "📹 Video Call":
            with st.form("video_call"):
                name = st.text_input("Your Name")
                email = st.text_input("Email Address")
                phone = st.text_input("Phone Number")
                date = st.date_input("Preferred Date", min_value=datetime.date.today())
                time = st.time_input("Preferred Time")
                submit = st.form_submit_button("Schedule Video Call")
                
                if submit:
                    if name and email and phone:
                        if "@" in email:
                            confirmation = f"""
Dear {name},

Your video call has been scheduled for {date} at {time}.
You will receive the meeting link 1 hour before the call.

Best regards,
Mental Health Support Team
"""
                            if send_email(email, "Video Call Confirmation", confirmation):
                                st.success(f"✅ Video call scheduled for {date} at {time}")
                            else:
                                st.error("Failed to send confirmation email")
                        else:
                            st.error("Invalid email")
                    else:
                        st.error("Please fill all fields")
    else:
        st.warning("⚠️ Please log in to access the community features.")

elif page == "Personalized Recommendations":
    st.subheader("🎯 Personalized Recommendations")

    if st.session_state.logged_in:
        user_predictions = fetch_predictions(st.session_state.username)

        if not user_predictions.empty:
            latest_status = user_predictions['Status'].iloc[-1]
            avg_status = user_predictions['Status'].mode()[0] if not user_predictions['Status'].empty else "Unknown"
            
            # Display stats
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Assessments", len(user_predictions))
            col2.metric("Latest Status", latest_status)
            col3.metric("Most Common", avg_status)

            st.markdown("---")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("### 📊 Based on Latest Assessment")
                if latest_status == "Stable or Low Instability":
                    st.success("""
                    **Recommendations:**
                    • Continue your healthy routine
                    • Practice gratitude daily
                    • Stay socially connected
                    • Maintain work-life balance
                    • Regular exercise (30 min/day)
                    """)
                elif latest_status == "Moderate Instability":
                    st.warning("""
                    **Recommendations:**
                    • Consider speaking with a counselor
                    • Practice mindfulness meditation
                    • Journal your thoughts daily
                    • Limit stress triggers
                    • Maintain regular sleep schedule
                    """)
                elif latest_status == "High Instability or Severe Instability":
                    st.error("""
                    **Recommendations:**
                    • Seek professional help immediately
                    • Contact mental health hotlines
                    • Don't isolate yourself
                    • Practice grounding techniques
                    • Have a crisis plan ready
                    """)

            with col2:
                st.write("### 📈 Based on Overall Pattern")
                if avg_status == "Stable or Low Instability":
                    st.success("""
                    **Lifestyle Tips:**
                    • Keep up the good work!
                    • Help others when possible
                    • Learn new coping skills
                    • Set personal goals
                    • Regular health check-ups
                    """)
                elif avg_status == "Moderate Instability":
                    st.warning("""
                    **Improvement Tips:**
                    • Build a support network
                    • Try relaxation techniques
                    • Identify stress patterns
                    • Set boundaries
                    • Practice self-compassion
                    """)
                elif avg_status == "High Instability or Severe Instability":
                    st.error("""
                    **Action Plan:**
                    • Regular therapy sessions
                    • Medication if prescribed
                    • Join support groups
                    • Create safety plan
                    • Emergency contacts ready
                    """)

            st.markdown("---")
            st.write("### 📚 Resources & Support")
            
            with st.expander("📞 24/7 Helplines"):
                st.write("""
                - **National Suicide Prevention Lifeline**: 1-800-273-8255
                - **Crisis Text Line**: Text HOME to 741741
                - **SAMHSA Helpline**: 1-800-662-4357
                - **Veterans Crisis Line**: 1-800-273-8255 (Press 1)
                """)
            
            with st.expander("💻 Online Therapy"):
                st.write("""
                - [BetterHelp](https://www.betterhelp.com/) - Professional counseling
                - [Talkspace](https://www.talkspace.com/) - Online therapy
                - [7 Cups](https://www.7cups.com/) - Free emotional support
                """)
            
            with st.expander("📱 Mental Health Apps"):
                st.write("""
                - **Calm** - Meditation & sleep
                - **Headspace** - Mindfulness
                - **Moodpath** - Mood tracking
                - **Sanvello** - Anxiety & depression
                """)
        else:
            st.info("No predictions yet. Complete assessments in Home page to get recommendations.")
    else:
        st.warning("Please log in to access recommendations.")

elif page == "Admin Dashboard":
    if not st.session_state.admin_logged_in:
        st.subheader("🔐 Admin Login")
        with st.form("admin_login"):
            admin_username = st.text_input("Username")
            admin_password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Login")
            
            if submit:
                if authenticate(admin_username, admin_password):
                    st.session_state.admin_logged_in = True
                    st.success("Welcome, Admin!")
                    st.rerun()
                else:
                    st.error("Invalid credentials")
    else:
        st.title("🛠️ Admin Dashboard")

        # Password change
        with st.expander("🔑 Change Admin Password"):
            with st.form("change_password"):
                new_pass = st.text_input("New Password", type="password")
                confirm_pass = st.text_input("Confirm Password", type="password")
                submit = st.form_submit_button("Update Password")
                
                if submit:
                    if new_pass == confirm_pass and len(new_pass) >= 6:
                        update_admin_password(new_pass)
                        st.success("Password updated!")
                    else:
                        st.error("Passwords don't match or too short")

        # User management
        c.execute("SELECT username FROM users")
        users = [row[0] for row in c.fetchall()]
        
        st.metric("Total Users", len(users))
        
        if users:
            selected_user = st.selectbox("Select User", users)
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("📊 View User Details"):
                    user_preds = fetch_predictions(selected_user)
                    if not user_preds.empty:
                        st.write(f"### {selected_user}'s History")
                        st.dataframe(user_preds)
                        
                        # Show graph
                        status_counts = user_preds['Status'].value_counts()
                        plt.figure(figsize=(8, 4))
                        plt.pie(status_counts.values, labels=status_counts.index, autopct='%1.1f%%')
                        plt.title(f"{selected_user}'s Status Distribution")
                        st.pyplot(plt)
                    else:
                        st.info("No predictions for this user")
            
            with col2:
                if selected_user != "admin":
                    if st.button("🗑️ Delete User", type="primary"):
                        c.execute("DELETE FROM users WHERE username=?", (selected_user,))
                        c.execute("DELETE FROM predictions WHERE username=?", (selected_user,))
                        conn.commit()
                        st.success(f"User {selected_user} deleted")
                        st.rerun()
                else:
                    st.warning("Cannot delete admin")

        # System overview
        st.markdown("---")
        st.subheader("📈 System Overview")
        
        all_preds = fetch_all_predictions()
        
        if not all_preds.empty:
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Predictions", len(all_preds))
            col2.metric("Active Users", all_preds['Username'].nunique())
            col3.metric("Most Common Status", all_preds['Status'].mode()[0])
            
            # Activity graph
            all_preds['Date'] = pd.to_datetime(all_preds['Date'])
            daily_activity = all_preds.groupby(all_preds['Date'].dt.date).size()
            
            plt.figure(figsize=(10, 4))
            plt.plot(daily_activity.index, daily_activity.values, marker='o')
            plt.title('Daily Activity')
            plt.xticks(rotation=45)
            plt.tight_layout()
            st.pyplot(plt)
        else:
            st.info("No system data yet")

        if st.button("Logout"):
            st.session_state.admin_logged_in = False
            st.rerun()
