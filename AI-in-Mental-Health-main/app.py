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
from email.mime.image import MIMEImage
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# Page config must be the first Streamlit command
st.set_page_config(
    page_title="AI Mental Health Assistant",
    page_icon="🧠",
    layout="wide"
)

# Get the absolute path to the current directory
CURRENT_DIR = Path(__file__).parent.absolute()

# Load the trained model
@st.cache_resource
def load_model():
    model_path = CURRENT_DIR / 'voting_gb_dt_model.pkl'
    try:
        if not model_path.exists():
            st.error(f"Model file not found. Please ensure 'voting_gb_dt_model.pkl' is in the correct location.")
            st.info(f"Current directory: {CURRENT_DIR}")
            st.info(f"Files found: {[f.name for f in CURRENT_DIR.iterdir()]}")
            return None
        model = joblib.load(model_path)
        return model
    except Exception as e:
        st.error(f"Error loading model: {str(e)}")
        return None

# Load the model
model = load_model()

# Stop if model didn't load
if model is None:
    st.stop()

# Connect to SQLite database
db_path = CURRENT_DIR / 'new_user_data.db'
conn = sqlite3.connect(str(db_path), check_same_thread=False)
c = conn.cursor()

# Create tables
c.execute('''CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    password TEXT
)''')

c.execute('''CREATE TABLE IF NOT EXISTS predictions (
    username TEXT,
    date DATETIME,
    prediction INTEGER,
    status TEXT,
    time_spent INTEGER,
    FOREIGN KEY (username) REFERENCES users (username)
)''')

c.execute('''CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    message TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)''')

conn.commit()

# Create admin account
def create_admin_account():
    admin_username = "admin"
    admin_password = "admin891"
    c.execute("INSERT OR IGNORE INTO users (username, password) VALUES (?, ?)", (admin_username, admin_password))
    conn.commit()

create_admin_account()

# Authentication functions
def authenticate(username, password):
    c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
    return c.fetchone() is not None

def register(username, password):
    try:
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False

# Prediction functions
def save_prediction(username, date, prediction, status, time_spent):
    c.execute("INSERT INTO predictions (username, date, prediction, status, time_spent) VALUES (?, ?, ?, ?, ?)", 
              (username, date, prediction, status, time_spent))
    conn.commit()

def fetch_predictions(username):
    c.execute("SELECT date, prediction, status FROM predictions WHERE username=? ORDER BY date DESC", (username,))
    rows = c.fetchall()
    return pd.DataFrame(rows, columns=["Date", "Prediction", "Status"])

def fetch_chat_messages():
    c.execute("SELECT id, username, message, timestamp FROM chat_messages ORDER BY timestamp")
    return c.fetchall()

def save_chat_message(username, message):
    c.execute("INSERT INTO chat_messages (username, message) VALUES (?, ?)", (username, message))
    conn.commit()

def delete_chat_message(message_id):
    c.execute("DELETE FROM chat_messages WHERE id=?", (message_id,))
    conn.commit()

def predict(input_data):
    try:
        input_df = pd.DataFrame([input_data])
        prediction = model.predict(input_df)
        if hasattr(model, 'predict_proba'):
            confidence = model.predict_proba(input_df)
            confidence_percentage = np.max(confidence) * 100
        else:
            confidence_percentage = 0.0
        return prediction[0], confidence_percentage
    except Exception as e:
        st.error(f"Prediction error: {str(e)}")
        return 0, 0.0

def map_to_status(yes_count):
    if yes_count <= 3:
        return "Stable or Low Instability"
    elif yes_count == 4:
        return "Moderate Instability"
    elif 5 <= yes_count <= 8:
        return "High Instability or Severe Instability"
    return "Unknown Status"

def update_admin_password(new_password):
    c.execute("UPDATE users SET password=? WHERE username='admin'", (new_password,))
    conn.commit()

# Email functions
def send_email(to_email, subject, body):
    from_email = "chbharath0779@gmail.com"
    from_password = "gnfq orjk evec sdwd"
    
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
        st.error(f"Email error: {str(e)}")
        return False

def send_email_with_attachment(to_email, subject, body, img_file):
    from_email = "chbharath0779@gmail.com"
    from_password = "gnfq orjk evec sdwd"
    
    msg = MIMEMultipart()
    msg['From'] = from_email
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    
    img_file.seek(0)
    msg.attach(MIMEImage(img_file.read(), name='mood_tracking_graph.png'))
    
    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(from_email, from_password)
            server.send_message(msg)
        return True
    except Exception as e:
        st.error(f"Email error: {str(e)}")
        return False

# Initialize session state
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.login_time = None
    st.session_state.admin_logged_in = False
    st.session_state.chat_active = False
    st.session_state.predictions = pd.DataFrame()

# Custom CSS
st.markdown("""
<style>
    .stButton > button {
        width: 100%;
        background-color: #4CAF50;
        color: white;
        font-weight: bold;
    }
    .stTextInput > div > div > input {
        background-color: #f0f2f6;
    }
    .css-1v0mbdj {
        padding: 2rem 1rem;
    }
    .reportview-container {
        background: linear-gradient(to right, #f8f9fa, #e9ecef);
    }
    h1 {
        color: #1e3c72;
        font-size: 2.5rem;
        font-weight: 700;
        margin-bottom: 2rem;
    }
    h2 {
        color: #2a5298;
        font-size: 1.8rem;
        font-weight: 600;
    }
    .stAlert {
        border-radius: 10px;
        padding: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# Navigation
st.markdown("<h1 style='text-align: center;'>🧠 AI Mental Health Assistant</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; font-size: 1.2rem; color: #666; margin-bottom: 2rem;'>Detecting Early Signs of Mental Health Instability</p>", unsafe_allow_html=True)

page = st.sidebar.selectbox(
    "📱 Navigation",
    ["Home", "Mood Tracking", "Personalized Recommendations", "Connect Page", "Admin Dashboard"]
)

# Home Page
if page == "Home":
    if not st.session_state.logged_in:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown("### 🔐 Welcome! Please Login or Register")
            option = st.radio("Select Option", ["Login", "Register"], horizontal=True)
            username = st.text_input("Username", placeholder="Enter your username")
            password = st.text_input("Password", type="password", placeholder="Enter your password")
            
            if option == "Register":
                if st.button("📝 Register", use_container_width=True):
                    if username and password:
                        if register(username, password):
                            st.success("✅ Registration successful! Please login.")
                        else:
                            st.error("❌ Username already exists!")
                    else:
                        st.warning("⚠️ Please fill all fields")
            else:
                if st.button("🔑 Login", use_container_width=True):
                    if username and password:
                        if authenticate(username, password):
                            st.session_state.logged_in = True
                            st.session_state.username = username
                            st.session_state.login_time = time.time()
                            st.success(f"✅ Welcome {username}!")
                            st.rerun()
                        else:
                            st.error("❌ Invalid credentials")
                    else:
                        st.warning("⚠️ Please fill all fields")
    else:
        st.markdown(f"### 👋 Welcome, {st.session_state.username}!")
        
        # Mental Health Assessment Form
        with st.form("assessment_form"):
            st.markdown("#### 📋 Mental Health Assessment")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                gender = st.selectbox("Gender", ["Male", "Female"])
                country = st.selectbox("Country", [
                    'United States', 'United Kingdom', 'India', 'Canada', 'Australia',
                    'Germany', 'France', 'Brazil', 'South Africa', 'Other'
                ])
                occupation = st.selectbox("Occupation", ["Corporate", "Student", "Business", "Housewife", "Others"])
                self_employed = st.selectbox("Self Employed", ["Yes", "No"])
                family_history = st.selectbox("Family History", ["Yes", "No"])
                
            with col2:
                treatment = st.selectbox("Treatment", ["Yes", "No"])
                days_indoors = st.selectbox("Days Indoors", ['1-14 days', 'Go out Every day', 'More than 2 months', '15-30 days', '31-60 days'])
                growing_stress = st.selectbox("Growing Stress", ["Yes", "No", "Maybe"])
                changes_habits = st.selectbox("Changes in Habits", ["Yes", "No", "Maybe"])
                mental_health_history = st.selectbox("Mental Health History", ["Yes", "No", "Maybe"])
                
            with col3:
                mood_swings = st.selectbox("Mood Swings", ["Low", "Medium", "High"])
                coping_struggles = st.selectbox("Coping Struggles", ["Yes", "No"])
                work_interest = st.selectbox("Work Interest", ["Yes", "Maybe", "No"])
                social_weakness = st.selectbox("Social Weakness", ["Yes", "No", "Maybe"])
                mental_health_interview = st.selectbox("Mental Health Interview", ["Yes", "Maybe", "No"])
                care_options = st.selectbox("Care Options", ["Yes", "No", "Not sure"])
            
            submitted = st.form_submit_button("🔮 Predict Mental Health Status", use_container_width=True)
            
            if submitted:
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
                
                with st.spinner("Analyzing your responses..."):
                    prediction, confidence = predict(input_data)
                    status = map_to_status(prediction)
                    
                    # Display results
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Instability Score", f"{prediction}/8")
                    with col2:
                        st.metric("Confidence", f"{confidence:.1f}%")
                    with col3:
                        st.metric("Status", status.split()[0])
                    
                    if "Stable" in status:
                        st.success(f"🟢 **Status: {status}**")
                    elif "Moderate" in status:
                        st.warning(f"🟡 **Status: {status}**")
                    else:
                        st.error(f"🔴 **Status: {status}**")
                    
                    # Save prediction
                    time_spent = int(time.time() - st.session_state.login_time)
                    save_prediction(st.session_state.username, datetime.datetime.now(), prediction, status, time_spent)
        
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.username = ""
            st.rerun()

# Mood Tracking Page
elif page == "Mood Tracking":
    if not st.session_state.logged_in:
        st.warning("⚠️ Please login to access mood tracking")
    else:
        st.markdown("### 📊 Your Mood Tracking History")
        
        predictions = fetch_predictions(st.session_state.username)
        
        if predictions.empty:
            st.info("No predictions recorded yet. Complete an assessment on the Home page!")
        else:
            # Display records
            with st.expander("📋 View Records", expanded=True):
                st.dataframe(predictions, use_container_width=True)
            
            # Visualizations
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### 📈 Status Distribution")
                status_counts = predictions['Status'].value_counts()
                fig, ax = plt.subplots(figsize=(8, 5))
                colors = ['#4CAF50' if 'Stable' in x else '#FFC107' if 'Moderate' in x else '#F44336' for x in status_counts.index]
                ax.bar(status_counts.index, status_counts.values, color=colors)
                ax.set_xlabel('Mental Health Status')
                ax.set_ylabel('Count')
                ax.set_title('Your Mental Health Status Distribution')
                plt.xticks(rotation=45, ha='right')
                plt.tight_layout()
                st.pyplot(fig)
                plt.close()
            
            with col2:
                st.markdown("#### 📅 Timeline")
                predictions['Date'] = pd.to_datetime(predictions['Date'])
                daily_counts = predictions.groupby(predictions['Date'].dt.date).size()
                fig, ax = plt.subplots(figsize=(8, 5))
                ax.plot(daily_counts.index, daily_counts.values, marker='o', color='#2196F3', linewidth=2)
                ax.set_xlabel('Date')
                ax.set_ylabel('Number of Assessments')
                ax.set_title('Your Assessment Timeline')
                plt.xticks(rotation=45, ha='right')
                plt.tight_layout()
                st.pyplot(fig)
                plt.close()
            
            # Email Report
            st.markdown("---")
            st.markdown("### 📧 Get Your Mental Health Report")
            
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input("Your Name", value=st.session_state.username)
            with col2:
                email = st.text_input("Your Email")
            
            if st.button("Send Report", use_container_width=True):
                if name and email and "@" in email and "." in email:
                    latest = predictions.iloc[0]
                    avg_status = predictions['Status'].mode()[0]
                    
                    # Generate recommendations
                    if "Stable" in avg_status:
                        recs = ["Maintain healthy habits", "Share experiences with others", "Stay engaged in joyful activities"]
                    elif "Moderate" in avg_status:
                        recs = ["Consider seeking support", "Practice relaxation techniques", "Connect with loved ones"]
                    else:
                        recs = ["Consult a mental health professional", "Develop a self-care plan", "Reach out to support groups"]
                    
                    report = f"""
                    Dear {name},
                    
                    Here's your mental health report:
                    
                    Latest Status: {latest['Status']}
                    Latest Date: {latest['Date']}
                    Most Common Status: {avg_status}
                    
                    Recommendations:
                    - {recs[0]}
                    - {recs[1]}
                    - {recs[2]}
                    
                    Stay strong! 💪
                    """
                    
                    if send_email(email, "Your Mental Health Report", report):
                        st.success("✅ Report sent successfully!")
                    else:
                        st.error("❌ Failed to send email")
                else:
                    st.warning("⚠️ Please enter valid name and email")

# Personalized Recommendations Page
elif page == "Personalized Recommendations":
    if not st.session_state.logged_in:
        st.warning("⚠️ Please login to get personalized recommendations")
    else:
        st.markdown("### 🎯 Your Personalized Recommendations")
        
        predictions = fetch_predictions(st.session_state.username)
        
        if predictions.empty:
            st.info("Complete an assessment first to get personalized recommendations!")
        else:
            latest_status = predictions['Status'].iloc[0]
            avg_status = predictions['Status'].mode()[0]
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### 📌 Based on Latest Assessment")
                st.info(f"Latest Status: **{latest_status}**")
                
                if "Stable" in latest_status:
                    st.markdown("""
                    ✅ **Recommendations:**
                    - Continue your healthy routine
                    - Practice daily mindfulness
                    - Stay physically active
                    - Connect with positive people
                    """)
                elif "Moderate" in latest_status:
                    st.markdown("""
                    🟡 **Recommendations:**
                    - Talk to someone you trust
                    - Try journaling your thoughts
                    - Practice deep breathing
                    - Maintain a sleep schedule
                    """)
                else:
                    st.markdown("""
                    🔴 **Recommendations:**
                    - Contact a mental health professional
                    - Call a crisis hotline if needed
                    - Practice grounding techniques
                    - Avoid isolation
                    """)
            
            with col2:
                st.markdown("#### 📊 Based on Your History")
                st.info(f"Most Common Status: **{avg_status}**")
                
                if "Stable" in avg_status:
                    st.markdown("""
                    ✅ **Long-term suggestions:**
                    - Build on your strengths
                    - Help others in their journey
                    - Set new personal goals
                    - Maintain work-life balance
                    """)
                elif "Moderate" in avg_status:
                    st.markdown("""
                    🟡 **Long-term suggestions:**
                    - Develop coping strategies
                    - Join support groups
                    - Regular exercise routine
                    - Monitor your triggers
                    """)
                else:
                    st.markdown("""
                    🔴 **Long-term suggestions:**
                    - Regular therapy sessions
                    - Build support network
                    - Create safety plan
                    - Medication management
                    """)
            
            # Resources
            st.markdown("---")
            st.markdown("### 📚 Mental Health Resources")
            
            with st.expander("📞 Crisis Helplines"):
                st.markdown("""
                - **National Suicide Prevention Lifeline:** 1-800-273-8255
                - **Crisis Text Line:** Text HOME to 741741
                - **SAMHSA Helpline:** 1-800-662-4357
                """)
            
            with st.expander("💻 Online Therapy"):
                st.markdown("""
                - [BetterHelp](https://www.betterhelp.com/)
                - [Talkspace](https://www.talkspace.com/)
                - [7 Cups](https://www.7cups.com/)
                """)

# Connect Page
elif page == "Connect Page":
    if not st.session_state.logged_in:
        st.warning("⚠️ Please login to access the connect page")
    else:
        st.markdown("### 💬 Community Chat & Support")
        
        # Chat Room
        with st.expander("💭 Join Community Chat", expanded=True):
            code = st.text_input("Enter Chat Room Code", type="password", placeholder="Enter 123456")
            
            if st.button("Join Chat", use_container_width=True):
                if code == "123456":
                    st.session_state.chat_active = True
                    st.success("✅ You've joined the chat!")
                else:
                    st.error("❌ Invalid code")
            
            if st.session_state.get("chat_active", False):
                st.markdown("---")
                
                # Display messages
                messages = fetch_chat_messages()
                for msg_id, username, msg, timestamp in messages:
                    if username == st.session_state.username:
                        st.markdown(f"""
                        <div style='text-align: right; background: #e3f2fd; padding: 10px; border-radius: 10px; margin: 5px;'>
                            <b>You</b>: {msg}<br>
                            <small>{timestamp}</small>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.markdown(f"""
                        <div style='text-align: left; background: #f5f5f5; padding: 10px; border-radius: 10px; margin: 5px;'>
                            <b>{username}</b>: {msg}<br>
                            <small>{timestamp}</small>
                        </div>
                        """, unsafe_allow_html=True)
                
                # New message
                new_msg = st.text_input("Type your message...")
                col1, col2 = st.columns([5,1])
                with col1:
                    if st.button("Send", use_container_width=True):
                        if new_msg:
                            save_chat_message(st.session_state.username, new_msg)
                            st.rerun()
                with col2:
                    if st.button("Leave", use_container_width=True):
                        st.session_state.chat_active = False
                        st.rerun()
        
        # Professional Support
        st.markdown("### 🤝 Connect with Professionals")
        st.info("Our counselors are available 24/7 to provide support")
        
        support_type = st.selectbox(
            "Select support type",
            ["", "💬 Text Support", "📧 Email Support", "📹 Video Call"]
        )
        
        if support_type == "💬 Text Support":
            with st.form("text_support"):
                name = st.text_input("Your name")
                phone = st.text_input("WhatsApp number")
                if st.form_submit_button("Request Text Support", use_container_width=True):
                    if name and phone:
                        st.success(f"✅ Support request sent! A counselor will contact you on {phone}")
        
        elif support_type == "📧 Email Support":
            with st.form("email_support"):
                name = st.text_input("Your name")
                email = st.text_input("Your email")
                if st.form_submit_button("Request Email Support", use_container_width=True):
                    if name and email:
                        subject = "Mental Health Support Request"
                        body = f"Dear {name},\n\nThank you for reaching out. A counselor will contact you soon."
                        if send_email(email, subject, body):
                            st.success("✅ Check your email for confirmation!")
        
        elif support_type == "📹 Video Call":
            with st.form("video_call"):
                name = st.text_input("Your name")
                email = st.text_input("Your email")
                date = st.date_input("Preferred date")
                time = st.time_input("Preferred time")
                if st.form_submit_button("Schedule Video Call", use_container_width=True):
                    if name and email:
                        subject = "Video Call Confirmation"
                        body = f"Dear {name},\n\nYour video call is scheduled for {date} at {time}."
                        if send_email(email, subject, body):
                            st.success("✅ Check your email for meeting link!")

# Admin Dashboard
elif page == "Admin Dashboard":
    if not st.session_state.get("admin_logged_in", False):
        with st.sidebar:
            st.markdown("### 🔐 Admin Login")
            admin_user = st.text_input("Admin Username")
            admin_pass = st.text_input("Admin Password", type="password")
            if st.button("Login as Admin", use_container_width=True):
                if authenticate(admin_user, admin_pass) and admin_user == "admin":
                    st.session_state.admin_logged_in = True
                    st.rerun()
                else:
                    st.error("❌ Invalid admin credentials")
    else:
        st.markdown("### 👑 Admin Dashboard")
        
        # Stats
        c.execute("SELECT COUNT(*) FROM users")
        total_users = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM predictions")
        total_predictions = c.fetchone()[0]
        c.execute("SELECT COUNT(DISTINCT username) FROM predictions")
        active_users = c.fetchone()[0]
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Users", total_users)
        col2.metric("Active Users", active_users)
        col3.metric("Total Assessments", total_predictions)
        
        # User management
        st.markdown("#### 👥 User Management")
        c.execute("SELECT username FROM users WHERE username != 'admin'")
        users = [row[0] for row in c.fetchall()]
        
        if users:
            selected = st.selectbox("Select User", users)
            
            if st.button("View User Details"):
                user_preds = fetch_predictions(selected)
                if not user_preds.empty:
                    st.dataframe(user_preds)
                    
                    fig, ax = plt.subplots()
                    user_preds['Status'].value_counts().plot(kind='bar', ax=ax, color=['#4CAF50', '#FFC107', '#F44336'])
                    ax.set_title(f"{selected}'s Mental Health Status")
                    st.pyplot(fig)
                    plt.close()
            
            if st.button("Delete User", type="primary"):
                c.execute("DELETE FROM users WHERE username=?", (selected,))
                c.execute("DELETE FROM predictions WHERE username=?", (selected,))
                c.execute("DELETE FROM chat_messages WHERE username=?", (selected,))
                conn.commit()
                st.success(f"✅ User {selected} deleted")
                st.rerun()
        
        # Admin actions
        st.markdown("#### 🔑 Admin Settings")
        new_pass = st.text_input("New Admin Password", type="password")
        confirm_pass = st.text_input("Confirm Password", type="password")
        
        if st.button("Change Admin Password"):
            if new_pass and new_pass == confirm_pass:
                update_admin_password(new_pass)
                st.success("✅ Password updated!")
            else:
                st.error("❌ Passwords don't match")
        
        if st.button("Logout Admin"):
            st.session_state.admin_logged_in = False
            st.rerun()
