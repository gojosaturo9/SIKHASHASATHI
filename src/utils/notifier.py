import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import threading
import os
import streamlit as st

# ⚠️ Yahan apni project ki nayi Gmail ID aur "App Password" daalein
SENDER_EMAIL = st.secrets["SENDER_EMAIL"]
SENDER_PASSWORD = st.secrets["SENDER_PASSWORD"]

# --- STUDENT ATTENDANCE EMAILS (Purana code, same rahega) ---


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


def notify_students_bg(attendance_results, subject_name, date_str):
    thread = threading.Thread(
        target=_process_emails_in_background,
        args=(attendance_results, subject_name, date_str),
    )
    thread.start()  # App ko bina roke background me start kar dega


# --- 🚀 NAYA FIX: TEACHER CREDENTIALS EMAIL (Purana verification function hata diya) ---


def send_teacher_credentials_email(target_email, teacher_name, username, password):
    msg = MIMEMultipart()
    msg["From"] = SENDER_EMAIL
    msg["To"] = target_email
    msg["Subject"] = "🔐 Welcome to Sageathon - Your Teacher Account Details"

    html_content = f"""
    <html>
        <body style="font-family: Arial, sans-serif; color: #333; line-height: 1.6;">
            <div style="max-width: 600px; margin: auto; border: 1px solid #ddd; border-radius: 10px; overflow: hidden;">
                <div style="background-color: #5865F2; padding: 20px; text-align: center; color: white;">
                    <h2>Welcome to Sageathon! 🎉</h2>
                </div>
                <div style="padding: 20px;">
                    <p>Dear <b>{teacher_name}</b>,</p>
                    <p>Your Teacher account has been successfully created by the Administrator.</p>
                    <p>Here are your secure login credentials:</p>
                    
                    <div style="background-color: #f4f4f9; padding: 15px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #5865F2;">
                        <p style="margin: 5px 0;"><b>👤 Username:</b> {username}</p>
                        <p style="margin: 5px 0;"><b>🔑 Password:</b> {password}</p>
                    </div>
                    
                    <p><i>Note: For your security, please log in and change this auto-generated password from your dashboard as soon as possible.</i></p>
                    
                    <br>
                    <p>Best Regards,</p>
                    <p><b>The Sageathon Admin Team</b></p>
                </div>
            </div>
        </body>
    </html>
    """

    msg.attach(MIMEText(html_content, "html"))

    def send_email_thread():
        try:
            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)
            server.quit()
            print(f"Credentials successfully sent to {target_email}")
        except Exception as e:
            print(f"Failed to send credentials to {target_email}: {e}")

    threading.Thread(target=send_email_thread).start()
    return True
