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
import os
from pathlib import Path

# Get the absolute path to the current directory
CURRENT_DIR = Path(__file__).parent.absolute()

# Load the trained model with proper path handling
@st.cache_resource
def load_model():
    model_path = CURRENT_DIR / 'voting_gb_dt_model.pkl'
    try:
        model = joblib.load(model_path)
        return model
    except FileNotFoundError:
        st.error(f"Model file not found at: {model_path}")
        st.error("Please ensure 'voting_gb_dt_model.pkl' is in the same directory as app.py")
        st.stop()
    except Exception as e:
        st.error(f"Error loading model: {str(e)}")
        st.stop()

# Load the model
model = load_model()

# Connect to SQLite database with proper path
db_path = CURRENT_DIR / 'new_user_data.db'
conn = sqlite3.connect(str(db_path))
c = conn.cursor()

# Create tables if they don't exist
c.execute('''
    CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password TEXT
    )
''')

# Create a new predictions table with the time_spent column if it doesn't exist
c.execute('''
    CREATE TABLE IF NOT EXISTS predictions_new (
        username TEXT,
        date DATETIME,
        prediction INTEGER,
        status TEXT,
        time_spent INTEGER,
        FOREIGN KEY (username) REFERENCES users (username)
    )
''')

# Create a new chat messages table if it doesn't exist
c.execute('''
    CREATE TABLE IF NOT EXISTS chat_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        message TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
''')

conn.commit()

# Check if the old predictions table exists and migrate data if necessary
c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='predictions'")
if c.fetchone() is not None:
    # Copy data from the old predictions table to the new one
    c.execute('''
        INSERT INTO predictions_new (username, date, prediction, status)
        SELECT username, date, prediction, status FROM predictions
    ''')
    conn.commit()
    
    # Drop the old predictions table
    c.execute('DROP TABLE predictions')
    conn.commit()

# Rename the new table to the original table name
c.execute('ALTER TABLE predictions_new RENAME TO predictions')
conn.commit()

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
              (username, date, prediction, status, time_spent))
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
    input_df = pd.DataFrame([input_data])
    prediction = model.predict(input_df)
    confidence = model.predict_proba(input_df)
    confidence_percentage = np.max(confidence) * 100

    return prediction[0], confidence_percentage

def map_to_status(yes_count):
    if yes_count <= 3:
        return "Stable or Low Instability"
    elif yes_count == 4:
        return "Moderate Instability"
    elif 5 <= yes_count <= 8:
        return "High Instability or Severe Instability"
    return "Unknown Status"

# Function to update admin password
def update_admin_password(new_password):
    c.execute("UPDATE users SET password=? WHERE username='admin'", (new_password,))
    conn.commit()

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
        print(f"Failed to send email: {e}")
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
        print(f"Failed to send email: {e}")
        return False

# Initialize session state for authentication and mood tracking
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.login_time = None

if "admin_logged_in" not in st.session_state:
    st.session_state.admin_logged_in = False

if "predictions" not in st.session_state:
    st.session_state.predictions = pd.DataFrame(columns=["Date", "Prediction", "Status", "Time Spent"])

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
            prediction, confidence_percentage = predict(input_data)
            status = map_to_status(prediction)
            st.write(f"Predicted Instability Rate (0 to 8): {prediction}")
            st.write(f"Confidence: {confidence_percentage:.2f}%")
            st.write(f"Mental Health Status: {status}")
            
            time_spent = int(time.time() - st.session_state.login_time)

            save_prediction(st.session_state.username, datetime.datetime.now(), prediction, status, time_spent)
            st.session_state.predictions = fetch_predictions(st.session_state.username)

        if st.button("Logout"):
            time_spent = int(time.time() - st.session_state.login_time)
            save_prediction(st.session_state.username, datetime.datetime.now(), 0, "Logged Out", time_spent)
            st.session_state.logged_in = False
            st.session_state.username = ""
            st.session_state.login_time = None
            st.session_state.predictions = pd.DataFrame(columns=["Date", "Prediction", "Status", "Time Spent"])
            st.rerun()

elif page == "Mood Tracking":
    st.subheader("Mood Tracking Records")

    if st.session_state.logged_in:
        st.session_state.predictions = fetch_predictions(st.session_state.username)

        if "show_records" not in st.session_state:
            st.session_state.show_records = False
        if "show_graph" not in st.session_state:
            st.session_state.show_graph = False
        if "show_monthly_graph" not in st.session_state:
            st.session_state.show_monthly_graph = False

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
                st.write(st.session_state.predictions)
            else:
                st.write("No predictions recorded yet.")

        def save_mood_tracking_graph():
            if not st.session_state.predictions.empty:
                status_counts = st.session_state.predictions['Status'].value_counts()
                plt.figure(figsize=(10, 5))
                plt.bar(status_counts.index, status_counts.values, color='skyblue', alpha=0.7)
                plt.title('Mental Health Status Distribution', fontsize=16)
                plt.xlabel('Mental Health Status', fontsize=12)
                plt.ylabel('Count', fontsize=12)
                
                img = io.BytesIO()
                plt.savefig(img, format='png')
                img.seek(0)
                plt.close()
                return img
            return None

        if st.session_state.show_graph:
            if not st.session_state.predictions.empty:
                status_counts = st.session_state.predictions['Status'].value_counts()
                plt.figure(figsize=(10, 5))
                plt.bar(status_counts.index, status_counts.values, color='skyblue', alpha=0.7)
                plt.title('Mental Health Status Distribution', fontsize=16)
                plt.xlabel('Mental Health Status', fontsize=12)
                plt.ylabel('Count', fontsize=12)
                st.pyplot(plt)
            else:
                st.write("No predictions recorded yet.")

        monthly_counts = None
        if not st.session_state.predictions.empty:
            st.session_state.predictions['Date'] = pd.to_datetime(st.session_state.predictions['Date'])
            monthly_counts = st.session_state.predictions.groupby(st.session_state.predictions['Date'].dt.to_period('M')).count()

        if st.session_state.show_monthly_graph:
            if monthly_counts is not None and not monthly_counts.empty:
                plt.figure(figsize=(10, 5))
                plt.plot(monthly_counts.index.astype(str), monthly_counts['Prediction'], marker='o', color='orange', alpha=0.7)
                plt.title('Monthly Predictions Count', fontsize=16)
                plt.xlabel('Month', fontsize=12)
                plt.ylabel('Count of Predictions', fontsize=12)
                plt.xticks(rotation=45)
                st.pyplot(plt)
            else:
                st.write("No predictions recorded yet.")

        st.subheader("Request Your Mental Health Report")

        name = st.text_input("Your Name")
        email = st.text_input("Your Email")

        if st.button("Send Report"):
            if name and email:
                if "@" in email and "." in email:
                    latest_prediction = st.session_state.predictions.iloc[-1] if not st.session_state.predictions.empty else None
                    latest_status = latest_prediction['Status'] if latest_prediction is not None else "N/A"
                    latest_date = latest_prediction['Date'] if latest_prediction is not None else "N/A"
                    average_status = st.session_state.predictions['Status'].value_counts().idxmax() if not st.session_state.predictions.empty else "N/A"

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

                    report_content = f"""
Dear {name},

We hope this message finds you well. Below is your mental health report based on your recent mood tracking data.

Latest Prediction Status: {latest_status}
Latest Prediction Date: {latest_date}
Average Prediction Status: {average_status}

Personalized Recommendations:
{"\n- ".join(recommendations)}

Thank you for using our service. If you have any questions or need further assistance, please do not hesitate to reach out.

Best regards,
Mental Health Support Team
"""

                    img = save_mood_tracking_graph()
                    if img:
                        img_file = io.BytesIO(img.getvalue())
                        img_file.seek(0)

                        if send_email_with_attachment(email, "Your Mental Health Report", report_content, img_file):
                            st.success("Report sent successfully!")
                        else:
                            st.error("Failed to send the report. Please try again later.")
                    else:
                        st.error("Failed to generate the mood tracking graph.")
                else:
                    st.error("Please enter a valid email address.")
            else:
                st.error("Please enter both your name and email.")
    else:
        st.warning("Please log in to access mood tracking.")

elif page == "Connect Page":
    st.subheader("Chat Room")

    if st.session_state.logged_in:
        security_code = st.text_input("Enter Security Code", type="password")
        if st.button("Join Chat"):
            if security_code == "123456":
                st.session_state.chat_active = True
                st.success("You have joined the chat room!")
            else:
                st.error("Invalid security code. Please try again.")

        if "chat_active" in st.session_state and st.session_state.chat_active:
            messages = fetch_chat_messages()
            
            last_sender = None

            for message_id, username, message, timestamp in messages:
                if username == last_sender:
                    st.markdown(f"<div style='text-align: left;'><span style='color: gray;'>{timestamp}</span> - {message}</div>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<div style='text-align: right;'><strong>{username}</strong>: {message} <span style='color: gray;'>{timestamp}</span></div>", unsafe_allow_html=True)
                    last_sender = username

                if username == st.session_state.username:
                    if st.button("Delete", key=message_id):
                        delete_chat_message(message_id)
                        st.success("Message deleted successfully.")
                        st.rerun()

            new_message = st.text_input("Type your message here...")
            if st.button("Send"):
                if new_message.strip() != "":
                    save_chat_message(st.session_state.username, new_message)
                    st.rerun()
                else:
                    st.error("Message cannot be empty.")

            if st.button("Leave Chat"):
                st.session_state.chat_active = False
                st.success("You have left the chat room.")

        st.subheader("Connect with a Psychologist or Consultant")
        st.write("If you need to talk, our skilled, judgment-free counselors are here to provide compassionate support. You deserve to feel heard and cared about anytime, anywhere, 24/7/365.")

        contact_method = st.selectbox("Select a contact method", ["Select", "Text", "Email", "Video Call"])

        if contact_method == "Text":
            name = st.text_input("Enter your name:")
            age = st.number_input("Enter your age:", min_value=1)
            gender = st.selectbox("Select your gender:", ["Male", "Female", "Other"])
            whatsapp_number = st.text_input("Enter your WhatsApp number:")
            if st.button("Request Text Support"):
                if name and whatsapp_number:
                    st.success(f"Text support request received from {name}. A counselor will reach out to you shortly via WhatsApp.")
                else:
                    st.error("Please fill in all fields.")

        elif contact_method == "Email":
            name = st.text_input("Enter your name:")
            email_address = st.text_input("Enter your email address:")
            if st.button("Request Email Support"):
                if name and email_address:
                    subject = "Support Request Received"
                    body = f"""\
Dear {name},

Thank you for reaching out to us. We have received your request for support via email. A counselor will contact you shortly to provide the assistance you need.

If you have any immediate concerns, please do not hesitate to let us know.

Best regards,
Mental Health Support Team
"""
                    if send_email(email_address, subject, body):
                        st.success(f"Email support request received from {name}.")
                    else:
                        st.error("Failed to send email. Please try again later.")
                else:
                    st.error("Please fill in all fields.")

        elif contact_method == "Video Call":
            name = st.text_input("Enter your name:")
            email = st.text_input("Enter your email:")
            phone = st.text_input("Enter your phone number:")
            date = st.date_input("Select a date for the video call:")
            time_val = st.time_input("Select a time for the video call:")
            if st.button("Request Video Call"):
                if name and email and phone and date and time_val:
                    subject = "Video Call Request Confirmation"
                    body = f"""\
Dear {name},

We have received your request for a video call. You have scheduled a call on {date} at {time_val}. 

Please join the call using the following link: [Video Call Link](https://www.example.com/video-call).

If you have any questions or need to reschedule, feel free to reach out.

Best regards,
Mental Health Support Team
"""
                    if send_email(email, subject, body):
                        st.success(f"Video call request received from {name}.")
                    else:
                        st.error("Failed to send email. Please try again later.")
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

            if "show_latest_rec" not in st.session_state:
                st.session_state.show_latest_rec = False
            if "show_average_rec" not in st.session_state:
                st.session_state.show_average_rec = False

            with col1:
                if st.button("Recommendation based on Latest Prediction"):
                    st.session_state.show_latest_rec = not st.session_state.show_latest_rec

                if st.session_state.show_latest_rec:
                    st.write(f"Your latest mental health status: **{latest_status}**")
                    
                    if latest_status == "Stable or Low Instability":
                        recommendations = [
                            "Continue your daily routine and maintain healthy habits.",
                            "Engage in physical activities like walking or yoga.",
                            "Practice mindfulness or meditation for relaxation."
                        ]
                    elif latest_status == "Moderate Instability":
                        recommendations = [
                            "Consider talking to a friend or family member about your feelings.",
                            "Try journaling to express your thoughts and emotions.",
                            "Engage in creative activities like drawing or music."
                        ]
                    elif latest_status == "High Instability or Severe Instability":
                        recommendations = [
                            "Reach out to a mental health professional for support.",
                            "Practice deep breathing exercises to manage anxiety.",
                            "Limit exposure to stressful situations and take breaks."
                        ]
                    else:
                        recommendations = ["No specific recommendations available."]
                    
                    st.write("### Recommendations:")
                    for rec in recommendations:
                        st.write(f"- {rec}")

            with col2:
                if st.button("Recommendation based on Average Mental Health Status"):
                    st.session_state.show_average_rec = not st.session_state.show_average_rec

                if st.session_state.show_average_rec:
                    st.write(f"Your average mental health status: **{average_status}**")
                    
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
                        recommendations = ["No specific recommendations available."]
                    
                    st.write("### Recommendations:")
                    for rec in recommendations:
                        st.write(f"- {rec}")

            st.markdown("<h2 style='text-align: center;'>Mental Health Resources and Support</h2>", unsafe_allow_html=True)

            if "show_resources" not in st.session_state:
                st.session_state.show_resources = False

            if st.button("Toggle Mental Health Resources"):
                st.session_state.show_resources = not st.session_state.show_resources

            if st.session_state.show_resources:
                st.write("### Hotlines")
                st.write("[National Suicide Prevention Lifeline](https://suicidepreventionlifeline.org/) - Call 1-800-273-TALK (1-800-273-8255)")
                st.write("[Crisis Text Line](https://www.crisistextline.org/) - Text HOME to 741741")
                st.write("[SAMHSA National Helpline](https://www.samhsa.gov/find-help/national-helpline) - Call 1-800-662-HELP (1-800-662-4357)")

                st.write("### Online Therapy Options")
                st.write("[BetterHelp](https://www.betterhelp.com/) - Online therapy with licensed professionals.")
                st.write("[Talkspace](https://www.talkspace.com/) - Therapy via text, audio, and video messaging.")

                st.write("### Articles and Educational Materials")  
                st.write("[Mental Health America](https://www.mhanational.org/) - Resources and information on mental health.")
                st.write("[NAMI (National Alliance on Mental Illness)](https://www.nami.org/) - Information and support for mental health conditions.")

                st.write("### Local Mental Health Services")
                st.write("Find local mental health services in your area by visiting [Psychology Today](https://www.psychologytoday.com/us/therapists).")
        else:
            st.write("No mood tracking data available. Please make predictions first.")
    else:
        st.warning("Please log in to access personalized recommendations.")

elif page == "Admin Dashboard":
    if not st.session_state.admin_logged_in:
        admin_username = st.sidebar.text_input("Admin Username")
        admin_password = st.sidebar.text_input("Admin Password", type="password")
        if st.sidebar.button("Admin Login"):
            if authenticate(admin_username, admin_password):
                st.session_state.admin_logged_in = True
                st.success("Admin logged in successfully!")
            else:
                st.error("Invalid admin username or password")
    else:
        st.title("Admin Dashboard")

        st.subheader("Change Admin Password")
        new_password = st.text_input("New Admin Password", type="password")
        confirm_password = st.text_input("Confirm New Admin Password", type="password")
        
        if st.button("Change Password"):
            if new_password == confirm_password:
                update_admin_password(new_password)
                st.success("Admin password updated successfully!")
            else:
                st.error("Passwords do not match!")

        c.execute("SELECT username FROM users")
        users = c.fetchall()
        user_list = [user[0] for user in users]

        st.markdown("<h2 style='text-align: center;'>Total Users</h2>", unsafe_allow_html=True)
        st.markdown(f"<h1 style='text-align: center;'>{len(user_list)}</h1>", unsafe_allow_html=True)

        selected_user = st.selectbox("Select a user to view details", user_list)

        if "show_user_details" not in st.session_state:
            st.session_state.show_user_details = False
        if "show_user_deletion" not in st.session_state:
            st.session_state.show_user_deletion = False

        if st.button("Toggle User Details"):
            st.session_state.show_user_details = not st.session_state.show_user_details

        if st.session_state.show_user_details and selected_user:
            user_predictions = fetch_predictions(selected_user)

            if not user_predictions.empty:
                st.subheader(f"Details for {selected_user}")

                total_predictions = len(user_predictions)
                average_status = user_predictions['Status'].value_counts().idxmax()
                last_prediction_date = user_predictions['Date'].max() if not user_predictions.empty else "N/A"
                last_prediction_weekday = pd.to_datetime(last_prediction_date).day_name() if last_prediction_date != "N/A" else "N/A"

                user_details_data = {
                    "Metric": [
                        "Total Predictions",
                        "Average Status",
                        "Last Prediction Date",
                        "Last Prediction Weekday"
                    ],
                    "Value": [
                        total_predictions,
                        average_status,
                        last_prediction_date,
                        last_prediction_weekday
                    ]
                }

                user_details_df = pd.DataFrame(user_details_data)
                st.table(user_details_df)

                status_counts = user_predictions['Status'].value_counts()
                plt.figure(figsize=(10, 5))
                plt.bar(status_counts.index, status_counts.values, color='blue', alpha=0.7)
                plt.title(f'Mental Health Status Distribution for {selected_user}', fontsize=16)
                plt.xlabel('Mental Health Status', fontsize=12)
                plt.ylabel('Count', fontsize=12)
                st.pyplot(plt)
            else:
                st.write(f"No mood history recorded for {selected_user}.")

        st.subheader("Delete User")
        delete_user = st.selectbox("Select a user to delete", user_list, key="delete_user")
        
        if st.button("Toggle User Deletion"):
            st.session_state.show_user_deletion = not st.session_state.show_user_deletion

        if st.session_state.show_user_deletion:
            if st.button("Delete User", key="confirm_delete"):
                if delete_user:
                    c.execute("DELETE FROM users WHERE username=?", (delete_user,))
                    conn.commit()
                    st.success(f"User '{delete_user}' has been deleted successfully.")
                    c.execute("SELECT username FROM users")
                    users = c.fetchall()
                    user_list = [user[0] for user in users]
                    st.rerun()
                else:
                    st.error("Please select a user to delete.")

        st.subheader("Overall User Activity Monitoring")

        c.execute("SELECT username, date, prediction, status FROM predictions")
        predictions = c.fetchall()
        predictions_df = pd.DataFrame(predictions, columns=["Username", "Date", "Prediction", "Status"])

        if not predictions_df.empty and 'Date' in predictions_df.columns:
            predictions_df['Date'] = pd.to_datetime(predictions_df['Date'], errors='coerce')
            predictions_df = predictions_df.dropna(subset=['Date'])

            if not predictions_df.empty:
                total_users_active = predictions_df['Username'].nunique()
                most_active_weekday = predictions_df['Date'].dt.day_name().value_counts().idxmax() if not predictions_df.empty else "N/A"
                filtered_predictions_df = predictions_df[predictions_df['Status'] != "Logged Out"]
                most_predicted_status = filtered_predictions_df['Status'].value_counts().idxmax() if not filtered_predictions_df.empty else "N/A"

                overall_activity_data = {
                    "Metric": [
                        "Total Active Users",
                        "Most Active Weekday",
                        "Most Predicted Status"
                    ],
                    "Value": [
                        total_users_active,
                        most_active_weekday,
                        most_predicted_status
                    ]
                }

                overall_activity_df = pd.DataFrame(overall_activity_data)
                st.table(overall_activity_df)

                if st.button("Show Total Active Users by Weekday Graph"):
                    active_users_by_weekday = predictions_df.groupby(predictions_df['Date'].dt.day_name())['Username'].nunique().reindex(
                        ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'], fill_value=0)
                    plt.figure(figsize=(10, 5))
                    plt.bar(active_users_by_weekday.index, active_users_by_weekday.values, color='blue', alpha=0.7)
                    plt.title('Total Active Users by Weekday', fontsize=16)
                    plt.ylabel('Count of Active Users', fontsize=12)
                    plt.xlabel('Weekday', fontsize=12)
                    plt.xticks(rotation=45)
                    st.pyplot(plt)

                if st.button("Show Most Active Weekday Graph"):
                    weekday_counts = predictions_df['Date'].dt.day_name().value_counts()
                    plt.figure(figsize=(10, 5))
                    plt.plot(weekday_counts.index, weekday_counts.values, marker='o', color='blue', alpha=0.7)
                    plt.title('Most Active Weekday', fontsize=16)
                    plt.xlabel('Weekday', fontsize=12)
                    plt.ylabel('Count', fontsize=12)
                    plt.xticks(rotation=45)
                    st.pyplot(plt)

                if st.button("Show Most Predicted Status Graph"):
                    status_counts = predictions_df['Status'].value_counts()
                    plt.figure(figsize=(10, 5))
                    plt.plot(status_counts.index, status_counts.values, marker='o', color='blue', alpha=0.7)
                    plt.title('Most Predicted Status', fontsize=16)
                    plt.xlabel('Status', fontsize=12)
                    plt.ylabel('Count', fontsize=12)
                    plt.xticks(rotation=45)
                    st.pyplot(plt)
            else:
                st.write("No valid date data available.")
        else:
            st.write("No predictions recorded yet.")
