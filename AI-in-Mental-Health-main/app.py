# ====================== FIXED EMAIL FUNCTIONS ======================
# Replace your existing send_email and send_email_with_attachment functions with these

def send_email(to_email, subject, body):
    # !!! IMPORTANT: Replace these with YOUR ACTUAL details !!!
    from_email = "gandemani975@gmail.com"  # Your Gmail address
    # Replace this with the REAL 16-character App Password you get from Google
    from_password = "jklm nopq rstu vwxy"  # <-- YOU MUST GENERATE THIS!

    if not to_email or '@' not in to_email:
        st.error("Invalid recipient email address.")
        return False

    # Debug: Check if password is still the placeholder (Remove after testing)
    if from_password == "jklm nopq rstu vwxy":
        st.error("❌ YOU ARE USING THE EXAMPLE PASSWORD! Generate a real App Password from Google.")
        st.info("Go to: https://myaccount.google.com/apppasswords")
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
    except smtplib.SMTPAuthenticationError as e:
        st.error(f"❌ Gmail Authentication Failed: {str(e)}")
        st.info("🔑 This usually means you are not using a valid App Password. Please follow the steps below:")
        st.markdown("""
        1. Go to your Google Account: [https://myaccount.google.com/](https://myaccount.google.com/)
        2. Navigate to **Security** → **2-Step Verification** and turn it **ON**.
        3. After enabling 2-Step, go back to **Security** and click on **App passwords**.
        4. Select 'Other' as the app, give it a name (e.g., 'Mental Health App'), and click **Generate**.
        5. **Copy the 16-character password** that appears and paste it into the `from_password` variable in your code.
        """)
        return False
    except Exception as e:
        st.error(f"An unexpected email error occurred: {str(e)}")
        return False


def send_email_with_attachment(to_email, subject, body, img_file):
    # !!! IMPORTANT: Replace these with YOUR ACTUAL details !!!
    from_email = "gandemani975@gmail.com"  # Your Gmail address
    # Replace this with the REAL 16-character App Password you get from Google
    from_password = "jklm nopq rstu vwxy"  # <-- YOU MUST GENERATE THIS!

    if not to_email or '@' not in to_email:
        st.error("Invalid recipient email address.")
        return False

    # Debug: Check if password is still the placeholder (Remove after testing)
    if from_password == "jklm nopq rstu vwxy":
        st.error("❌ YOU ARE USING THE EXAMPLE PASSWORD! Generate a real App Password from Google.")
        st.info("Go to: https://myaccount.google.com/apppasswords")
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
    except smtplib.SMTPAuthenticationError as e:
        st.error(f"❌ Gmail Authentication Failed: {str(e)}")
        st.info("🔑 This usually means you are not using a valid App Password. Please follow the steps below:")
        st.markdown("""
        1. Go to your Google Account: [https://myaccount.google.com/](https://myaccount.google.com/)
        2. Navigate to **Security** → **2-Step Verification** and turn it **ON**.
        3. After enabling 2-Step, go back to **Security** and click on **App passwords**.
        4. Select 'Other' as the app, give it a name (e.g., 'Mental Health App'), and click **Generate**.
        5. **Copy the 16-character password** that appears and paste it into the `from_password` variable in your code.
        """)
        return False
    except Exception as e:
        st.error(f"An unexpected email error occurred: {str(e)}")
        return False
# ====================== END OF FIXED EMAIL FUNCTIONS ======================
