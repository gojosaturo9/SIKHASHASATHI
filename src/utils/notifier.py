import streamlit as st
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import threading

# ⚠️ Yahan apni project ki nayi Gmail ID aur "App Password" daalein
SENDER_EMAIL = st.secrets["SENDER_EMAIL"]
SENDER_PASSWORD = st.secrets["SENDER_PASSWORD"]


def send_single_email(student_email, student_name, subject_name, is_present, date):
    status = "PRESENT ✅" if is_present else "ABSENT ❌"

    msg = MIMEMultipart()
    msg["From"] = SENDER_EMAIL
    msg["To"] = student_email
    msg["Subject"] = f"Attendance Update: {subject_name} - {status}"

    body = f"""
    Hello {student_name},

    Your attendance for '{subject_name}' has been marked for {date}.
    Status: {status}

    Regards,
    Smart AI Attendance System
    """

    msg.attach(MIMEText(body, "plain"))

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.send_message(msg)
        server.quit()
    except Exception as e:
        print(f"Failed to send email to {student_email}: {e}")


# Yeh function background me chalega
def _process_emails_in_background(attendance_results, subject_name, date_str):
    for log in attendance_results:
        email = log.get("email_id")
        if email:  # Agar email maujood hai tabhi bhejo
            send_single_email(
                student_email=email,
                student_name=log["Name"],
                subject_name=subject_name,
                is_present=log["is_present"],
                date=date_str,
            )


# Hum is function ko baahar se call karenge
def notify_students_bg(attendance_results, subject_name, date_str):
    thread = threading.Thread(
        target=_process_emails_in_background,
        args=(attendance_results, subject_name, date_str),
    )
    thread.start()  # App ko bina roke background me start kar dega
