import streamlit as st
import pandas as pd
import joblib
import datetime
import matplotlib.pyplot as plt
import sqlite3
import time
import numpy as np
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# Page config
st.set_page_config(
    page_title="Mental Health AI Assistant",
    page_icon="🧠",
    layout="wide"
)

# Get the current directory
CURRENT_DIR = Path(__file__).parent.absolute()

# Load the model
@st.cache_resource
def load_model():
    try:
        model_path = CURRENT_DIR / 'voting_gb_dt_model.pkl'
        if not model_path.exists():
            st.error(f"Model file not found at: {model_path}")
            st.info("Please ensure voting_gb_dt_model.pkl is in the same directory as app.py")
            return None
        model = joblib.load(model_path)
        return model
    except Exception as e:
        st.error(f"Error loading model: {str(e)}")
        return None

# Initialize database
@st.cache_resource
def init_database():
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
        time_spent INTEGER
    )''')
    
    # Create admin account
    c.execute("INSERT OR IGNORE INTO users (username, password) VALUES (?, ?)", ("admin", "admin891"))
    
    conn.commit()
    return conn, c

# Load model and database
model = load_model()
conn, c = init_database()

if model is None:
    st.stop()

# Authentication functions
def authenticate(username, password):
    c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
    return c.fetchone() is not None

def register(username, password):
    try:
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
        conn.commit()
        return True
    except:
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

def predict_mental_health(input_data):
    try:
        input_df = pd.DataFrame([input_data])
        prediction = model.predict(input_df)[0]
        
        # Map to status
        if prediction <= 3:
            status = "Stable or Low Instability"
        elif prediction == 4:
            status = "Moderate Instability"
        else:
            status = "High Instability or Severe Instability"
        
        # Get confidence if available
        confidence = 0
        if hasattr(model, 'predict_proba'):
            proba = model.predict_proba(input_df)
            confidence = np.max(proba) * 100
        
        return prediction, status, confidence
    except Exception as e:
        st.error(f"Prediction error: {str(e)}")
        return 0, "Unknown", 0

# Initialize session state
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ''
    st.session_state.login_time = None
    st.session_state.admin_logged_in = False

# Sidebar navigation
st.sidebar.title("🧠 Navigation")
if not st.session_state.logged_in:
    page = st.sidebar.radio("Go to", ["Login", "Register"])
else:
    page = st.sidebar.radio("Go to", ["Home", "My Reports", "Admin Panel"] if st.session_state.username == "admin" else ["Home", "My Reports"])

# Login Page
if page == "Login" and not st.session_state.logged_in:
    st.title("🔐 Login")
    
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        
        if st.button("Login", use_container_width=True):
            if authenticate(username, password):
                st.session_state.logged_in = True
                st.session_state.username = username
                st.session_state.login_time = time.time()
                st.success(f"Welcome {username}!")
                st.rerun()
            else:
                st.error("Invalid username or password")

# Register Page
elif page == "Register" and not st.session_state.logged_in:
    st.title("📝 Register")
    
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        confirm_password = st.text_input("Confirm Password", type="password")
        
        if st.button("Register", use_container_width=True):
            if username and password:
                if password == confirm_password:
                    if register(username, password):
                        st.success("Registration successful! Please login.")
                    else:
                        st.error("Username already exists!")
                else:
                    st.error("Passwords do not match!")
            else:
                st.error("Please fill all fields")

# Home Page (Assessment)
elif page == "Home" and st.session_state.logged_in:
    st.title(f"👋 Welcome, {st.session_state.username}!")
    st.markdown("### 📋 Mental Health Assessment")
    
    with st.form("assessment_form"):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            gender = st.selectbox("Gender", ["Male", "Female"])
            country = st.selectbox("Country", ["United States", "United Kingdom", "India", "Canada", "Australia", "Other"])
            occupation = st.selectbox("Occupation", ["Corporate", "Student", "Business", "Housewife", "Others"])
            self_employed = st.selectbox("Self Employed", ["Yes", "No"])
            
        with col2:
            family_history = st.selectbox("Family History", ["Yes", "No"])
            treatment = st.selectbox("Treatment", ["Yes", "No"])
            days_indoors = st.selectbox("Days Indoors", ['1-14 days', 'Go out Every day', 'More than 2 months', '15-30 days', '31-60 days'])
            growing_stress = st.selectbox("Growing Stress", ["Yes", "No", "Maybe"])
            
        with col3:
            changes_habits = st.selectbox("Changes in Habits", ["Yes", "No", "Maybe"])
            mental_health_history = st.selectbox("Mental Health History", ["Yes", "No", "Maybe"])
            mood_swings = st.selectbox("Mood Swings", ["Low", "Medium", "High"])
            coping_struggles = st.selectbox("Coping Struggles", ["Yes", "No"])
        
        col4, col5, col6 = st.columns(3)
        with col4:
            work_interest = st.selectbox("Work Interest", ["Yes", "Maybe", "No"])
        with col5:
            social_weakness = st.selectbox("Social Weakness", ["Yes", "No", "Maybe"])
        with col6:
            mental_health_interview = st.selectbox("Mental Health Interview", ["Yes", "Maybe", "No"])
        
        care_options = st.selectbox("Care Options", ["Yes", "No", "Not sure"])
        
        submitted = st.form_submit_button("🔮 Predict My Mental Health Status", use_container_width=True)
        
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
                prediction, status, confidence = predict_mental_health(input_data)
                
                # Display results
                st.markdown("---")
                st.markdown("### 📊 Your Results")
                
                col1, col2, col3 = st.columns(3)
                col1.metric("Instability Score", f"{prediction}/8")
                col2.metric("Confidence", f"{confidence:.1f}%" if confidence > 0 else "N/A")
                col3.metric("Status", status.split()[0])
                
                if "Stable" in status:
                    st.success(f"🟢 **{status}**")
                    st.info("You're doing well! Keep maintaining your healthy habits.")
                elif "Moderate" in status:
                    st.warning(f"🟡 **{status}**")
                    st.info("Consider talking to someone you trust about your feelings.")
                else:
                    st.error(f"🔴 **{status}**")
                    st.info("Please consider reaching out to a mental health professional.")
                
                # Save prediction
                time_spent = int(time.time() - st.session_state.login_time)
                save_prediction(st.session_state.username, datetime.datetime.now(), prediction, status, time_spent)
    
    if st.button("🚪 Logout"):
        st.session_state.logged_in = False
        st.session_state.username = ''
        st.rerun()

# My Reports Page
elif page == "My Reports" and st.session_state.logged_in:
    st.title("📊 My Mental Health Reports")
    
    predictions = fetch_predictions(st.session_state.username)
    
    if predictions.empty:
        st.info("No predictions yet. Complete an assessment on the Home page!")
    else:
        # Summary metrics
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Assessments", len(predictions))
        col2.metric("Latest Score", f"{predictions['Prediction'].iloc[0]}/8")
        col3.metric("Most Common Status", predictions['Status'].mode()[0])
        
        # Display table
        with st.expander("📋 View All Records", expanded=True):
            st.dataframe(predictions, use_container_width=True)
        
        # Charts
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 📈 Status Distribution")
            status_counts = predictions['Status'].value_counts()
            fig, ax = plt.subplots(figsize=(8, 5))
            colors = ['green' if 'Stable' in x else 'orange' if 'Moderate' in x else 'red' for x in status_counts.index]
            ax.bar(status_counts.index, status_counts.values, color=colors)
            ax.set_xlabel('Status')
            ax.set_ylabel('Count')
            plt.xticks(rotation=45, ha='right')
            plt.tight_layout()
            st.pyplot(fig)
            plt.close()
        
        with col2:
            st.markdown("#### 📅 Score Trend")
            fig, ax = plt.subplots(figsize=(8, 5))
            ax.plot(range(len(predictions)), predictions['Prediction'].values, marker='o', color='blue', linewidth=2)
            ax.set_xlabel('Assessment Number')
            ax.set_ylabel('Score (0-8)')
            ax.set_ylim(0, 8)
            ax.grid(True, alpha=0.3)
            plt.tight_layout()
            st.pyplot(fig)
            plt.close()

# Admin Panel
elif page == "Admin Panel" and st.session_state.logged_in and st.session_state.username == "admin":
    st.title("👑 Admin Panel")
    
    # Statistics
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM predictions")
    total_predictions = c.fetchone()[0]
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Users", total_users)
    col2.metric("Total Predictions", total_predictions)
    col3.metric("Active Users", len(fetch_predictions('admin')['Username'].unique()) if not fetch_predictions('admin').empty else 0)
    
    # User list
    st.markdown("### 👥 User Management")
    c.execute("SELECT username FROM users WHERE username != 'admin'")
    users = [row[0] for row in c.fetchall()]
    
    if users:
        selected_user = st.selectbox("Select User", users)
        
        if st.button("View User Reports"):
            user_preds = fetch_predictions(selected_user)
            if not user_preds.empty:
                st.dataframe(user_preds)
                
                # Chart
                fig, ax = plt.subplots()
                user_preds['Status'].value_counts().plot(kind='bar', ax=ax, color=['green', 'orange', 'red'])
                ax.set_title(f"{selected_user}'s Status Distribution")
                st.pyplot(fig)
                plt.close()
            else:
                st.info("No predictions for this user")
    
    # Change admin password
    st.markdown("### 🔑 Admin Settings")
    new_pass = st.text_input("New Admin Password", type="password")
    confirm_pass = st.text_input("Confirm Password", type="password")
    
    if st.button("Update Password"):
        if new_pass and new_pass == confirm_pass:
            c.execute("UPDATE users SET password=? WHERE username='admin'", (new_pass,))
            conn.commit()
            st.success("Password updated!")
        else:
            st.error("Passwords don't match")

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown("### 🧠 Mental Health AI Assistant")
st.sidebar.markdown("Your privacy and well-being matter")
