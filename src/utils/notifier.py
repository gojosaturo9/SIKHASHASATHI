import smtplib
import threading
import re
import time
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

from src.utils.secrets import get_secret

# Use: Internal helper for secret str.
# Linked with: _from_email
def _secret_str(name, default=None):
    value = get_secret(name, default)
    return str(value).strip() if value not in (None, "") else default


# Use: Internal helper for secret int.
# Linked with: Streamlit UI, decorators, tests, or external runtime calls.
def _secret_int(name, default):
    try:
        return int(str(get_secret(name, default)).strip())
    except (TypeError, ValueError):
        return default


SMTP_HOST = _secret_str("SMTP_HOST", "smtp.gmail.com")
SMTP_TLS_PORT = _secret_int("SMTP_TLS_PORT", 587)
SMTP_SSL_PORT = _secret_int("SMTP_SSL_PORT", 465)
SMTP_SEND_MODE = _secret_str("SMTP_SEND_MODE", "tls").lower()
SMTP_MAX_RETRIES = _secret_int("SMTP_MAX_RETRIES", 3)


# Use: Internal helper for email credentials.
# Linked with: _send_message
def _email_credentials():
    sender_email = get_secret("SMTP_USER") or get_secret("SENDER_EMAIL")
    sender_password = get_secret("SMTP_PASS") or get_secret("SENDER_PASSWORD")

    if not sender_email or not sender_password:
        raise RuntimeError(
            "Email not configured. Add SENDER_EMAIL and SENDER_PASSWORD in .streamlit/secrets.toml"
        )

    return str(sender_email).strip(), str(sender_password).replace(" ", "").strip()


# Use: Internal helper for from email.
# Linked with: _build_message
def _from_email(sender_email):
    return _secret_str("SMTP_FROM", sender_email) or sender_email


# Use: Internal helper for is valid email.
# Linked with: _send_message
def _is_valid_email(email):
    if not email:
        return False
    return re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", str(email)) is not None


# Use: Internal helper for build message.
# Linked with: _send_message
def _build_message(sender_email, to_email, subject, body, html_body=None):
    msg = MIMEMultipart()
    msg["From"] = _from_email(sender_email)
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))
    if html_body:
        msg.attach(MIMEText(html_body, "html"))
    return msg


# Use: Internal helper for send message tls.
# Linked with: Streamlit UI, decorators, tests, or external runtime calls.
def _send_message_tls(sender_email, sender_password, msg):
    with smtplib.SMTP(SMTP_HOST, SMTP_TLS_PORT, timeout=30) as server:
        server.ehlo()
        server.starttls(context=tls.create_default_context())
        server.ehlo()
        server.login(sender_email, sender_password)
        server.send_message(msg)


# Use: Internal helper for send message tls.
# Linked with: Streamlit UI, decorators, tests, or external runtime calls.
def _send_message_ssl(sender_email, sender_password, msg):
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_SSL_PORT, timeout=30) as server:
        server.login(sender_email, sender_password)
        server.send_message(msg)


# Use: Internal helper for send message.
# Linked with: _send_email_job, handle_inbound_email_reply, send_low_attendance_email, send_single_email, send_student_registration_email, send_teacher_credentials_email_now
def _send_message(to_email, subject, body, html_body=None):
    if not _is_valid_email(to_email):
        raise ValueError(f"Invalid email address: {to_email}")

    sender_email, sender_password = _email_credentials()

    first_sender = _send_message_ssl if SMTP_SEND_MODE != "tls" else _send_message_tls
    second_sender = _send_message_tls if first_sender is _send_message_ssl else _send_message_ssl
    first_name = "SSL" if first_sender is _send_message_ssl else "TLS"
    second_name = "TLS" if second_sender is _send_message_tls else "SSL"

    last_first_error = None
    last_second_error = None
    for attempt in range(1, SMTP_MAX_RETRIES + 1):
        try:
            msg = _build_message(sender_email, to_email, subject, body, html_body)
            first_sender(sender_email, sender_password, msg)
            return True
        except Exception as first_error:
            last_first_error = first_error
            try:
                msg = _build_message(sender_email, to_email, subject, body, html_body)
                second_sender(sender_email, sender_password, msg)
                return True
            except Exception as second_error:
                last_second_error = second_error
                if attempt < SMTP_MAX_RETRIES:
                    time.sleep(attempt * 2)

    raise RuntimeError(
        f"SMTP send failed after {SMTP_MAX_RETRIES} attempt(s). "
        f"{first_name} error: {last_first_error}; {second_name} error: {last_second_error}"
    )


# Use: Internal helper for first value.
# Linked with: _student_email, _student_name, _student_present
def _first_value(row, *keys):
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None


# Use: Internal helper for student name.
# Linked with: notify_students
def _student_name(row):
    return _first_value(row, "Name", "name", "Student Name", "student_name") or "Student"


# Use: Internal helper for student email.
# Linked with: notify_students
def _student_email(row):
    return _first_value(row, "email_id", "Email", "email", "student_email")


# Use: Internal helper for student present.
# Linked with: notify_students
def _student_present(row):
    value = _first_value(row, "is_present", "present", "Present")

    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "present", "p", "✅ present"}

    return bool(value)


# Use: Sends single email notification or message.
# Linked with: notify_students
def send_single_email(student_email, student_name, subject_name, is_present, date):
    status = "PRESENT" if is_present else "ABSENT"

    body = f"""
Hello {student_name},

Your attendance for "{subject_name}" has been marked on {date}.

Status: {status}

Regards,
TRUEPRESENCE AI Attendance System
"""

    return _send_message(
        to_email=student_email,
        subject=f"Attendance Update: {subject_name} - {status}",
        body=body,
    )


# Use: Triggers students notifications.
# Linked with: notify_students_bg.worker
def notify_students(attendance_results, subject_name, date_str=None):
    """
    Direct send version.
    Use this when you want confirmation immediately.
    """

    if date_str is None:
        date_str = datetime.now().strftime("%d-%m-%Y %I:%M %p")

    results = []

    for row in attendance_results or []:
        email = _student_email(row)

        if not email:
            results.append({
                "ok": False,
                "email": None,
                "student": _student_name(row),
                "error": "Email missing",
            })
            continue

        try:
            send_single_email(
                student_email=email,
                student_name=_student_name(row),
                subject_name=subject_name,
                is_present=_student_present(row),
                date=date_str,
            )

            results.append({
                "ok": True,
                "email": email,
                "student": _student_name(row),
                "error": None,
            })

            print(f"Attendance email sent to {email}")

        except Exception as exc:
            results.append({
                "ok": False,
                "email": email,
                "student": _student_name(row),
                "error": str(exc),
            })

            print(f"Failed to send attendance email to {email}: {exc}")

    sent = sum(1 for r in results if r["ok"])
    failed = [r for r in results if not r["ok"]]

    return {
        "queued": False,
        "sent": sent,
        "failed_count": len(failed),
        "failed": failed,
        "results": results,
    }


# Use: Triggers students bg notifications.
# Linked with: Streamlit UI, decorators, tests, or external runtime calls.
def notify_students_bg(attendance_results, subject_name, date_str=None):
    """
    Background send version.
    This only starts thread. Result will be visible in terminal logs.
    """

    # Use: Handles worker behavior in this module.
    # Linked with: Streamlit UI, decorators, tests, or external runtime calls.
    def worker():
        result = notify_students(attendance_results, subject_name, date_str)
        print("Background attendance mail result:", result)

    thread = threading.Thread(target=worker, daemon=False)
    thread.start()

    return {
        "queued": True,
        "count": len(attendance_results or []),
        "message": "Emails are being sent in background. Check terminal logs.",
    }


# Use: Sends low attendance email notification or message.
# Linked with: notify_low_attendance
def send_low_attendance_email(
    student_email,
    student_name,
    subject_name,
    attendance_percent,
    present_days,
    total_days,
):
    body = f"""
Hello {student_name},

Your attendance in "{subject_name}" is below the required 75%.

Current attendance: {attendance_percent:.1f}%
Present days: {present_days}
Total classes: {total_days}

Please contact your teacher and improve attendance.

Regards,
TRUEPRESENCE AI Attendance System
"""

    return _send_message(
        to_email=student_email,
        subject=f"Low Attendance Alert: {subject_name}",
        body=body,
    )


# Use: Triggers low attendance notifications.
# Linked with: notify_low_attendance_bg.worker
def notify_low_attendance(alerts):
    results = []

    for alert in alerts or []:
        email = alert.get("email_id") or alert.get("email")

        if not email:
            results.append({
                "ok": False,
                "email": None,
                "student": alert.get("name", "Student"),
                "error": "Email missing",
            })
            continue

        try:
            send_low_attendance_email(
                student_email=email,
                student_name=alert.get("name", "Student"),
                subject_name=alert.get("subject_name", "Subject"),
                attendance_percent=float(alert.get("attendance_percent", 0)),
                present_days=int(alert.get("present_days", 0)),
                total_days=int(alert.get("total_days", 0)),
            )

            results.append({
                "ok": True,
                "email": email,
                "student": alert.get("name", "Student"),
                "error": None,
            })

            print(f"Low attendance email sent to {email}")

        except Exception as exc:
            results.append({
                "ok": False,
                "email": email,
                "student": alert.get("name", "Student"),
                "error": str(exc),
            })

            print(f"Failed low attendance email to {email}: {exc}")

    sent = sum(1 for r in results if r["ok"])
    failed = [r for r in results if not r["ok"]]

    return {
        "queued": False,
        "sent": sent,
        "failed_count": len(failed),
        "failed": failed,
        "results": results,
    }


# Use: Triggers low attendance bg notifications.
# Linked with: show_attendance_result
def notify_low_attendance_bg(alerts):
    # Use: Handles worker behavior in this module.
    # Linked with: Streamlit UI, decorators, tests, or external runtime calls.
    def worker():
        result = notify_low_attendance(alerts)
        print("Background low attendance mail result:", result)

    thread = threading.Thread(target=worker, daemon=False)
    thread.start()

    return {
        "queued": True,
        "count": len(alerts or []),
        "message": "Low attendance emails are being sent in background.",
    }


# Use: Sends student registration email notification or message.
# Linked with: notify_student_registration
def send_student_registration_email(student_email, student_name, enrollment_no):
    body = f"""
Hello {student_name},

Your student profile has been registered successfully.

Enrollment No.: {enrollment_no}

You can now use face scan login and attendance features.

Regards,
TRUEPRESENCE AI Attendance System
"""

    return _send_message(
        to_email=student_email,
        subject="Registration Complete - TRUEPRESENCE AI Attendance",
        body=body,
    )


# Use: Triggers student registration notifications.
# Linked with: add_student_tab, notify_student_registration_bg.worker, student_screen
def notify_student_registration(student_email, student_name, enrollment_no):
    try:
        send_student_registration_email(student_email, student_name, enrollment_no)
        return {
            "ok": True,
            "email": student_email,
            "error": None,
        }
    except Exception as exc:
        print(f"Failed registration email to {student_email}: {exc}")
        return {
            "ok": False,
            "email": student_email,
            "error": str(exc),
        }


# Use: Triggers student registration bg notifications.
# Linked with: Streamlit UI, decorators, tests, or external runtime calls.
def notify_student_registration_bg(student_email, student_name, enrollment_no):
    # Use: Handles worker behavior in this module.
    # Linked with: Streamlit UI, decorators, tests, or external runtime calls.
    def worker():
        result = notify_student_registration(student_email, student_name, enrollment_no)
        print("Background registration mail result:", result)

    thread = threading.Thread(target=worker, daemon=False)
    thread.start()

    return {
        "queued": True,
        "email": student_email,
    }


# Use: Sends teacher credentials email now notification or message.
# Linked with: add_teacher_tab, send_teacher_credentials_email
def send_teacher_credentials_email_now(target_email, teacher_name, username, password):
    body = f"""
Hello {teacher_name},

Your teacher account has been created.

Username: {username}
Password: {password}

Please log in and change your password.

Regards,
TRUEPRESENCE Admin Team
"""

    return _send_message(
        to_email=target_email,
        subject="Teacher Account Details - TRUEPRESENCE",
        body=body,
    )


# Use: Sends teacher credentials email notification or message.
# Linked with: send_teacher_credentials_email_bg.worker
def send_teacher_credentials_email(target_email, teacher_name, username, password):
    try:
        send_teacher_credentials_email_now(
            target_email,
            teacher_name,
            username,
            password,
        )

        print(f"Teacher credentials sent to {target_email}")

        return {
            "ok": True,
            "email": target_email,
            "error": None,
        }

    except Exception as exc:
        print(f"Failed teacher credentials email to {target_email}: {exc}")

        return {
            "ok": False,
            "email": target_email,
            "error": str(exc),
        }


# Use: Sends teacher credentials email bg notification or message.
# Linked with: Streamlit UI, decorators, tests, or external runtime calls.
def send_teacher_credentials_email_bg(target_email, teacher_name, username, password):
    # Use: Handles worker behavior in this module.
    # Linked with: Streamlit UI, decorators, tests, or external runtime calls.
    def worker():
        result = send_teacher_credentials_email(
            target_email,
            teacher_name,
            username,
            password,
        )
        print("Background teacher mail result:", result)

    thread = threading.Thread(target=worker, daemon=False)
    thread.start()

    return {
        "queued": True,
        "email": target_email,
    }
