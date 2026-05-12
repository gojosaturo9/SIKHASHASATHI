from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from email import policy
from email.parser import BytesParser
from email.utils import parseaddr
import hashlib
import html
import imaplib
import re
import threading
import time
import uuid

from src.database.config import require_supabase
from src.utils.notifier import _send_message
from src.utils.secrets import get_secret


LOW_ATTENDANCE_THRESHOLD = 75.0
HIGH_ATTENDANCE_THRESHOLD = 90.0
MAX_EMAIL_WORKERS = 8
MAX_RETRIES = 3
INBOUND_POLL_INTERVAL_SECONDS = 30
INBOUND_POLL_DEBUG_LOGS = str(get_secret("DEBUG_INBOUND_EMAIL_POLLER", "false")).lower() in {
    "1",
    "true",
    "yes",
    "on",
}
STRICT_REPLY_CATEGORIES = {
    "Attendance Correction Request",
    "Leave Application",
    "Medical Leave",
    "Emergency Leave",
    "Low Attendance Warning",
    "Attendance Inquiry",
    "Parent Concern",
    "Technical Issue",
    "Attendance Approval Request",
    "Faculty Report Request",
    "Proxy Attendance Complaint",
    "Timetable Query",
    "Attendance Dispute",
    "Report Download Issue",
    "General Inquiry",
    "Unknown",
}
MEDIUM_PRIORITY_CATEGORIES = {
    "Attendance Correction Request",
    "Leave Application",
    "Medical Leave",
    "Low Attendance Warning",
    "Attendance Inquiry",
    "Parent Concern",
    "Attendance Approval Request",
    "Faculty Report Request",
    "Attendance Dispute",
    "Report Download Issue",
}
HIGH_PRIORITY_CATEGORIES = {
    "Emergency Leave",
    "Proxy Attendance Complaint",
}

_EXECUTOR = ThreadPoolExecutor(max_workers=MAX_EMAIL_WORKERS)
_INBOUND_POLLER_THREAD = None
_INBOUND_POLLER_STOP = threading.Event()
_INBOUND_POLLER_LOCK = threading.Lock()
_PROCESSED_INBOUND_MESSAGE_IDS = set()


# Use: Internal helper for now iso.
# Linked with: _insert_thread_message, _send_email_job, _upsert_thread, dispatch_attendance_emails, process_delivery_webhook
def _now_iso():
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


# Use: Internal helper for table missing.
# Linked with: _insert_email_log, _insert_thread_message, _safe_table_select, _update_email_log, process_delivery_webhook
def _table_missing(exc):
    text = str(exc).lower()
    return (
        "42p01" in text
        or "42703" in text
        or "pgrst205" in text
        or "does not exist" in text
        or "could not find the table" in text
        or "email_logs" in text
        or "column" in text and "not found" in text
    )


# Use: Internal helper for safe table select.
# Linked with: _message_already_processed, _optional_leave_context, _recent_email_complaint_count, _student_attendance_context, _student_by_email, _student_by_enrollment_text, _teacher_by_email
def _safe_table_select(table_name, select_fields="*", **filters):
    try:
        query = require_supabase().table(table_name).select(select_fields)
        for field, value in filters.items():
            query = query.eq(field, value)
        return query.execute().data or []
    except Exception as exc:
        if not _table_missing(exc):
            print(f"Optional email automation lookup failed for {table_name}: {exc}")
        return []


# Use: Internal helper for safe email id.
# Linked with: dispatch_attendance_emails
def _safe_email_id(student_id, subject_id, timestamp):
    raw = f"{student_id}:{subject_id}:{timestamp}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:24]


# Use: Internal helper for insert email log.
# Linked with: dispatch_attendance_emails
def _insert_email_log(log):
    try:
        response = require_supabase().table("email_logs").insert(log).execute()
        return response.data[0] if response.data else log
    except Exception as exc:
        if _table_missing(exc):
            print(f"email_logs table missing; email log kept in console only: {log}")
            return log
        print(f"Email log insert failed: {exc}")
        return log


# Use: Internal helper for update email log.
# Linked with: _send_email_job
def _update_email_log(log_id, patch):
    if not log_id:
        return
    try:
        require_supabase().table("email_logs").update(patch).eq("id", log_id).execute()
    except Exception as exc:
        if not _table_missing(exc):
            print(f"Email log update failed: {exc}")


# Use: Builds subject analytics data used by another workflow.
# Linked with: _latest_subject_context, dispatch_attendance_emails
def build_subject_analytics(subject_id):
    if subject_id is None:
        return {}
    try:
        rows = (
            require_supabase()
            .table("attendance_logs")
            .select("student_id, is_present, timestamp")
            .eq("subject_id", subject_id)
            .execute()
            .data
        )
    except Exception as exc:
        print(f"Attendance analytics lookup failed; using current records only: {exc}")
        return {}
    stats = {}
    for row in rows or []:
        student_id = row.get("student_id")
        if student_id is None:
            continue
        item = stats.setdefault(
            int(student_id),
            {
                "total": 0,
                "present": 0,
                "recent": [],
            },
        )
        item["total"] += 1
        if row.get("is_present"):
            item["present"] += 1
        item["recent"].append(bool(row.get("is_present")))

    for item in stats.values():
        item["attendance_percent"] = (
            round(item["present"] / item["total"] * 100, 1) if item["total"] else 0.0
        )
        recent = item["recent"][-5:]
        item["recent_present"] = sum(1 for value in recent if value)
        item["trend"] = _trend_label(recent)
    return stats


# Use: Internal helper for trend label.
# Linked with: build_subject_analytics
def _trend_label(recent):
    if len(recent) < 3:
        return "new"
    present_count = sum(1 for value in recent if value)
    if present_count == len(recent):
        return "excellent"
    if present_count <= max(1, len(recent) // 2):
        return "needs_attention"
    return "steady"


# Use: Internal helper for email category.
# Linked with: _plain_template, build_attendance_email
def _email_category(is_present, analytics):
    percent = float(analytics.get("attendance_percent", 0.0))
    if percent < LOW_ATTENDANCE_THRESHOLD:
        return "low_attendance"
    if percent >= HIGH_ATTENDANCE_THRESHOLD and is_present:
        return "high_performance"
    return "present" if is_present else "absent"


# Use: Internal helper for subject for category.
# Linked with: build_attendance_email
def _subject_for_category(category):
    if category == "present":
        return "Attendance Confirmed for Today"
    if category == "absent":
        return "Absence Notice - Explanation and Application Required"
    if category == "low_attendance":
        return "Attendance Risk Alert - Improvement Required"
    return "Excellent Attendance Consistency"


# Use: Internal helper for plain template.
# Linked with: build_attendance_email
def _plain_template(student_name, subject_name, is_present, analytics, marked_date):
    percent = float(analytics.get("attendance_percent", 0.0))
    present = int(analytics.get("present", 0))
    total = int(analytics.get("total", 0))
    trend = analytics.get("trend", "steady")
    status = "Present" if is_present else "Absent"
    category = _email_category(is_present, analytics)

    if category == "low_attendance":
        if is_present:
            message = (
                f"You were marked present today. Your current attendance in "
                f"{subject_name} is {percent:.1f}%, which is below the required "
                f"{LOW_ATTENDANCE_THRESHOLD:.0f}% benchmark. Please attend upcoming "
                "classes consistently to improve your attendance."
            )
        else:
            message = (
                f"According to the attendance record, you were marked absent in "
                f"{subject_name} on {marked_date}. Your current attendance is "
                f"{percent:.1f}%, which is below the required "
                f"{LOW_ATTENDANCE_THRESHOLD:.0f}% benchmark. Please reply with the "
                "reason you did not attend college/classes and submit a leave "
                "application to the concerned faculty or office if your absence was "
                "due to a valid reason."
            )
    elif category == "high_performance":
        message = (
            f"Great job. Your attendance has been recorded successfully today, and "
            f"your current attendance in {subject_name} is {percent:.1f}%. Your "
            "consistent participation is helping maintain a strong academic record."
        )
    elif is_present:
        message = (
            f"Your attendance has been recorded successfully today. Your current "
            f"attendance in {subject_name} is {percent:.1f}%. Keep this consistency "
            "going; regular attendance supports stronger academic performance."
        )
    else:
        message = (
            f"According to the attendance record, you were marked absent in "
            f"{subject_name} on {marked_date}. Please reply with the reason you did "
            "not attend college/classes and submit a leave application to the "
            "concerned faculty or office if your absence was due to a valid reason. "
            "If you attended the class and believe this record is incorrect, please "
            "share supporting proof in the same email thread for verification."
        )

    return (
        f"Hello {student_name},\n\n"
        f"{message}\n\n"
        f"Attendance proof\n"
        f"Subject: {subject_name}\n"
        f"Date: {marked_date}\n"
        f"Status: {status}\n"
        f"Current analytics: {present}/{total} classes attended ({percent:.1f}%)\n"
        f"Recent trend: {trend.replace('_', ' ').title()}\n\n"
        "Regards,\n"
        "TRUEPRESENCE AI Attendance Assistant"
    )


# Use: Internal helper for html template.
# Linked with: build_attendance_email
def _html_template(student_name, subject_name, is_present, analytics, marked_date, body):
    percent = float(analytics.get("attendance_percent", 0.0))
    present = int(analytics.get("present", 0))
    total = int(analytics.get("total", 0))
    status = "Present" if is_present else "Absent"
    accent = "#15803d" if is_present else "#b91c1c"
    warning = "#ca8a04" if percent < LOW_ATTENDANCE_THRESHOLD else accent
    safe_body = html.escape(body).replace("\n", "<br>")
    return f"""<!doctype html>
<html>
<body style="margin:0;background:#f6f8fb;font-family:Arial,sans-serif;color:#172033;">
  <div style="max-width:640px;margin:0 auto;padding:24px;">
    <div style="background:#0f172a;color:white;padding:20px;border-radius:12px 12px 0 0;">
      <div style="font-size:13px;letter-spacing:.08em;text-transform:uppercase;">TRUEPRESENCE</div>
      <h2 style="margin:8px 0 0;font-size:24px;">AI Attendance Proof</h2>
    </div>
    <div style="background:white;border:1px solid #e5e7eb;border-top:0;padding:22px;border-radius:0 0 12px 12px;">
      <p style="font-size:16px;line-height:1.55;margin-top:0;">{safe_body}</p>
      <div style="display:block;margin:20px 0;padding:16px;border:1px solid #e5e7eb;border-radius:10px;background:#fafafa;">
        <div style="font-size:13px;color:#64748b;">Subject</div>
        <div style="font-size:18px;font-weight:700;">{html.escape(subject_name)}</div>
        <div style="height:12px;"></div>
        <div style="font-size:13px;color:#64748b;">Status</div>
        <div style="font-size:18px;font-weight:700;color:{accent};">{status}</div>
        <div style="height:12px;"></div>
        <div style="font-size:13px;color:#64748b;">Attendance</div>
        <div style="font-size:18px;font-weight:700;color:{warning};">{percent:.1f}%</div>
        <div style="font-size:13px;color:#64748b;">{present}/{total} classes attended</div>
      </div>
      <p style="font-size:12px;color:#64748b;margin-bottom:0;">Generated by TRUEPRESENCE AI Attendance Assistant on {html.escape(marked_date)}.</p>
    </div>
  </div>
</body>
</html>"""


# Use: Internal helper for generate with gemini.
# Linked with: build_attendance_email
def _generate_with_gemini(student_name, subject_name, is_present, analytics, marked_date):
    ai_email_mode = str(get_secret("AI_EMAIL_GENERATION", "fast")).lower()
    if ai_email_mode not in {"gemini", "llm", "true"}:
        return None

    api_key = get_secret("AIzaSyCQ6Ssto_Ks59-vJFm5jLoJf4xc5HqZpwY") or get_secret("AIzaSyCQ6Ssto_Ks59-vJFm5jLoJf4xc5HqZpwY")
    if not api_key:
        return None
    try:
        from src.voice_rag.llm import generate_gemini_content

        status = "present" if is_present else "absent"
        prompt = (
            "Write one concise institutional attendance proof email body. "
            "Use only this supplied data. Do not invent facts. Tone must be warm, "
            "professional, and authoritative. Keep it under 130 words.\n\n"
            f"Student: {student_name}\n"
            f"Subject: {subject_name}\n"
            f"Date: {marked_date}\n"
            f"Today status: {status}\n"
            f"Attendance percent: {analytics.get('attendance_percent', 0)}\n"
            f"Present classes: {analytics.get('present', 0)}\n"
            f"Total classes: {analytics.get('total', 0)}\n"
            f"Recent trend: {analytics.get('trend', 'steady')}\n"
            f"Policy threshold: {LOW_ATTENDANCE_THRESHOLD}%"
        )
        model_name = get_secret("GEMINI_MODEL", "gemini-2.5-flash")
        text, _ = generate_gemini_content(api_key, model_name, prompt, temperature=0.25)
        return text
    except Exception as exc:
        print(f"AI email generation failed; using deterministic template: {exc}")
        return None


# Use: Builds attendance email data used by another workflow.
# Linked with: dispatch_attendance_emails
def build_attendance_email(student_row, subject_name, subject_id, marked_date, analytics):
    student_name = (
        student_row.get("Name")
        or student_row.get("name")
        or student_row.get("Student Name")
        or "Student"
    )
    is_present = bool(student_row.get("is_present"))
    category = _email_category(is_present, analytics)
    subject = _subject_for_category(category)
    ai_body = _generate_with_gemini(student_name, subject_name, is_present, analytics, marked_date)
    body = ai_body or _plain_template(
        student_name, subject_name, is_present, analytics, marked_date
    )
    html_body = _html_template(
        student_name, subject_name, is_present, analytics, marked_date, body
    )
    return {
        "subject": subject,
        "body": body,
        "html_body": html_body,
        "category": category,
        "student_name": student_name,
        "subject_id": subject_id,
    }


# Use: Internal helper for send email job.
# Linked with: dispatch_attendance_emails
def _send_email_job(log_id, to_email, email_payload):
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            _update_email_log(
                log_id,
                {
                    "status": "sending",
                    "attempt_count": attempt,
                    "last_attempt_at": _now_iso(),
                },
            )
            _send_message(
                to_email=to_email,
                subject=email_payload["subject"],
                body=email_payload["body"],
                html_body=email_payload["html_body"],
            )
            _update_email_log(
                log_id,
                {
                    "status": "sent",
                    "sent_at": _now_iso(),
                    "error_message": None,
                    "attempt_count": attempt,
                },
            )
            return {"ok": True, "email": to_email, "attempts": attempt}
        except Exception as exc:
            last_error = str(exc)
            _update_email_log(
                log_id,
                {
                    "status": "retrying" if attempt < MAX_RETRIES else "failed",
                    "error_message": last_error,
                    "attempt_count": attempt,
                    "last_attempt_at": _now_iso(),
                },
            )
            if attempt < MAX_RETRIES:
                time.sleep(min(2 ** attempt, 8))
    return {"ok": False, "email": to_email, "error": last_error}


# Use: Handles dispatch attendance emails behavior in this module.
# Linked with: show_attendance_result
def dispatch_attendance_emails(records, subject_name, subject_id, marked_date):
    analytics_by_student = build_subject_analytics(subject_id)
    queued = 0
    sent_now = 0
    failed = []
    skipped = 0
    jobs = []

    for row in records or []:
        to_email = row.get("email_id") or row.get("Email") or row.get("email")
        student_id = row.get("ID") or row.get("student_id")
        if not to_email or student_id is None:
            skipped += 1
            continue

        student_id = int(student_id)
        analytics = analytics_by_student.get(
            student_id,
            {"total": 1, "present": 1 if row.get("is_present") else 0, "attendance_percent": 100.0 if row.get("is_present") else 0.0, "trend": "new"},
        )
        payload = build_attendance_email(
            row,
            subject_name=subject_name,
            subject_id=subject_id,
            marked_date=marked_date,
            analytics=analytics,
        )
        message_id = _safe_email_id(student_id, subject_id, row.get("timestamp") or marked_date)
        log = _insert_email_log(
            {
                "message_id": message_id,
                "student_id": student_id,
                "subject_id": subject_id,
                "to_email": to_email,
                "email_type": "attendance_proof",
                "status": "queued",
                "subject": payload["subject"],
                "body_preview": payload["body"][:500],
                "created_at": _now_iso(),
                "metadata": {
                    "category": payload["category"],
                    "attendance_percent": analytics.get("attendance_percent"),
                    "present": analytics.get("present"),
                    "total": analytics.get("total"),
                },
            }
        )
        log_id = log.get("id")
        if bool(row.get("is_present")):
            jobs.append(_EXECUTOR.submit(_send_email_job, log_id, to_email, payload))
            queued += 1
        else:
            result = _send_email_job(log_id, to_email, payload)
            if result.get("ok"):
                sent_now += 1
            else:
                failed.append(
                    {
                        "email": to_email,
                        "student": payload["student_name"],
                        "error": result.get("error", "Email send failed"),
                    }
                )

    return {
        "queued": queued,
        "sent_now": sent_now,
        "failed_count": len(failed),
        "failed": failed,
        "skipped": skipped,
        "jobs": jobs,
        "message": (
            f"{queued} present-attendance email(s) started. "
            f"{sent_now} absent-student follow-up email(s) sent immediately."
        ),
    }


# Use: Handles classify student reply behavior in this module.
# Linked with: analyze_incoming_email_reply
def classify_student_reply(reply_text):
    text = (reply_text or "").lower()
    if any(word in text for word in ["proxy", "fake", "fraud", "someone else"]):
        return "Proxy Attendance Complaint"
    if any(word in text for word in ["hospital", "hospitalized", "medical", "doctor", "fever"]):
        return "Medical Leave"
    if any(word in text for word in ["emergency", "urgent", "accident"]):
        return "Emergency Leave"
    if any(word in text for word in ["dispute", "not marked", "incorrect"]):
        return "Attendance Dispute"
    if any(word in text for word in ["present", "marked", "wrong", "mistake", "correction"]):
        return "Attendance Correction Request"
    if any(word in text for word in ["leave", "absent", "permission"]):
        return "Leave Application"
    if any(word in text for word in ["warning", "low attendance", "shortage", "75"]):
        return "Low Attendance Warning"
    if any(word in text for word in ["eligible", "eligibility", "percentage", "attendance percent"]):
        return "Attendance Inquiry"
    if any(word in text for word in ["parent", "daughter", "son", "ward", "child"]):
        return "Parent Concern"
    if any(word in text for word in ["not working", "login", "download", "error", "bug"]):
        return "Technical Issue"
    if any(word in text for word in ["approve", "approval"]):
        return "Attendance Approval Request"
    if any(word in text for word in ["report", "class report", "faculty report"]):
        return "Faculty Report Request"
    if any(word in text for word in ["timetable", "schedule", "period"]):
        return "Timetable Query"
    if any(word in text for word in ["download"]):
        return "Report Download Issue"
    if any(word in text for word in ["attendance", "present", "absent"]):
        return "Attendance Inquiry"
    if text.strip():
        return "General Inquiry"
    return "Unknown"


# Use: Internal helper for legacy intent name.
# Linked with: generate_ai_reply
def _legacy_intent_name(category):
    if category in {"Attendance Correction Request", "Attendance Dispute"}:
        return "attendance_dispute"
    if category == "Medical Leave":
        return "medical_leave"
    if category in {"Attendance Inquiry", "Low Attendance Warning"}:
        return "eligibility_question"
    if category in {"Leave Application", "Emergency Leave"}:
        return "leave_request"
    return "general_attendance_question"


# Use: Handles generate ai reply behavior in this module.
# Linked with: Streamlit UI, decorators, tests, or external runtime calls.
def generate_ai_reply(student, reply_text, attendance_context):
    analysis = analyze_incoming_email_reply(
        from_email=(student or {}).get("email_id"),
        subject="Attendance Query",
        body=reply_text,
        student=student,
        attendance_context=attendance_context,
    )
    category = analysis["category"]
    intent = _legacy_intent_name(category)

    return {
        "intent": intent,
        "category": category,
        "reply": analysis["reply_email"],
        "escalate": analysis["requires_human_review"],
        "ticket_id": str(uuid.uuid4()),
        "strict_json": analysis,
    }


# Use: Internal helper for teacher by email.
# Linked with: analyze_incoming_email_reply, handle_inbound_email_reply
def _teacher_by_email(email):
    if not email:
        return None
    rows = _safe_table_select("teachers", "*", email_id=email)
    return rows[0] if rows else None


# Use: Internal helper for student by enrollment text.
# Linked with: _student_for_parent_text
def _student_by_enrollment_text(text):
    match = re.search(
        r"(?:roll|enrollment|enrolment|reg(?:istration)?)[\s#:.-]*([A-Za-z0-9/-]{3,})",
        text or "",
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    rows = _safe_table_select("students", "*", enrollment_no=match.group(1))
    return rows[0] if rows else None


# Use: Internal helper for student for parent text.
# Linked with: analyze_incoming_email_reply
def _student_for_parent_text(text):
    student = _student_by_enrollment_text(text)
    if student:
        return student
    return None


# Use: Internal helper for sender type.
# Linked with: analyze_incoming_email_reply
def _sender_type(from_email, body, student=None, teacher=None):
    text = (body or "").lower()
    if student:
        return "Student"
    if teacher:
        return "Teacher"
    if any(word in text for word in ["my daughter", "my son", "my child", "my ward"]):
        return "Parent"
    if any(word in text for word in ["principal", "administrator", "admin office"]):
        return "Administrator"
    return "Unknown"


# Use: Internal helper for sentiment.
# Linked with: analyze_incoming_email_reply
def _sentiment(body):
    text = (body or "").lower()
    if any(word in text for word in ["angry", "unacceptable", "complaint", "wrong", "fraud"]):
        return "Concerned"
    if any(word in text for word in ["urgent", "emergency", "hospital", "accident"]):
        return "Urgent"
    if any(word in text for word in ["please", "kindly", "request"]):
        return "Polite"
    return "Neutral"


# Use: Internal helper for abuse or legal risk.
# Linked with: analyze_incoming_email_reply
def _abuse_or_legal_risk(body):
    text = (body or "").lower()
    return any(
        word in text
        for word in [
            "abuse",
            "threat",
            "threaten",
            "court",
            "legal",
            "lawyer",
            "police",
            "disciplinary",
        ]
    )


# Use: Internal helper for student attendance context.
# Linked with: analyze_incoming_email_reply
def _student_attendance_context(student_id):
    rows = _safe_table_select(
        "attendance_logs",
        "timestamp, is_present, subject_id, subjects(name, subject_code, teachers(name, email_id))",
        student_id=student_id,
    )
    if not rows:
        return {
            "overall_percent": None,
            "present": 0,
            "total": 0,
            "subjects": [],
            "recent_logs": [],
            "database_data_used": [],
        }

    per_subject = {}
    present = 0
    for row in rows:
        is_present = bool(row.get("is_present"))
        present += 1 if is_present else 0
        subject = row.get("subjects") or {}
        subject_name = subject.get("name") or "Subject"
        item = per_subject.setdefault(
            row.get("subject_id"),
            {
                "subject_name": subject_name,
                "subject_code": subject.get("subject_code"),
                "faculty_name": ((subject.get("teachers") or {}).get("name")),
                "present": 0,
                "total": 0,
            },
        )
        item["total"] += 1
        item["present"] += 1 if is_present else 0

    subject_summaries = []
    for item in per_subject.values():
        item["attendance_percent"] = (
            round(item["present"] / item["total"] * 100, 1) if item["total"] else 0.0
        )
        subject_summaries.append(item)

    recent_logs = sorted(rows, key=lambda row: row.get("timestamp") or "", reverse=True)[:5]
    return {
        "overall_percent": round(present / len(rows) * 100, 1),
        "present": present,
        "total": len(rows),
        "subjects": sorted(subject_summaries, key=lambda item: item["subject_name"]),
        "recent_logs": recent_logs,
        "database_data_used": [
            "attendance_percentage",
            "subject_attendance",
            "attendance_logs",
        ],
    }


# Use: Internal helper for optional leave context.
# Linked with: analyze_incoming_email_reply
def _optional_leave_context(student_id):
    data_used = []
    records = []
    for table_name in ("leave_requests", "leaves", "student_leaves"):
        rows = _safe_table_select(table_name, "*", student_id=student_id)
        if rows:
            records = rows
            data_used.append("leave_records")
            break
    return {"records": records[:5], "database_data_used": data_used}


# Use: Internal helper for recent email complaint count.
# Linked with: analyze_incoming_email_reply
def _recent_email_complaint_count(student_id):
    rows = _safe_table_select(
        "email_messages",
        "id, created_at, intent, escalate",
        student_id=student_id,
    )
    complaint_intents = {
        "Attendance Correction Request",
        "Attendance Dispute",
        "Proxy Attendance Complaint",
        "attendance_dispute",
    }
    return sum(1 for row in rows if row.get("intent") in complaint_intents)


# Use: Internal helper for priority.
# Linked with: analyze_incoming_email_reply
def _priority(category, requires_human_review):
    if category in HIGH_PRIORITY_CATEGORIES:
        return "HIGH"
    if requires_human_review and category in {"Unknown", "General Inquiry"}:
        return "MEDIUM"
    if category in MEDIUM_PRIORITY_CATEGORIES:
        return "MEDIUM"
    return "LOW"


# Use: Internal helper for reply subject.
# Linked with: analyze_incoming_email_reply
def _reply_subject(category):
    if category == "Technical Issue":
        return "Regarding Your Technical Support Query"
    if category in {"Leave Application", "Medical Leave", "Emergency Leave"}:
        return "Regarding Your Leave Request"
    if category == "Parent Concern":
        return "Regarding the Attendance Concern"
    if category == "Faculty Report Request":
        return "Regarding the Attendance Report Request"
    return "Regarding Your Attendance Query"


# Use: Internal helper for format date.
# Linked with: _build_personalized_reply
def _format_date(value):
    if not value:
        return "-"
    return str(value).split("T")[0]


# Use: Internal helper for build personalized reply.
# Linked with: analyze_incoming_email_reply
def _build_personalized_reply(sender_type, category, student, teacher, context, leave_context):
    name = "Sir/Madam"
    if sender_type == "Student" and student:
        name = student.get("name") or "Student"
    elif sender_type == "Teacher" and teacher:
        name = teacher.get("name") or "Faculty Member"
    elif sender_type == "Parent" and student:
        name = "Parent/Guardian"

    lines = [f"Dear {name},", "Thank you for contacting the Attendance Management System."]
    overall = context.get("overall_percent")
    subjects = context.get("subjects") or []
    lowest_subject = min(subjects, key=lambda item: item.get("attendance_percent", 100.0), default=None)
    student_name = (student or {}).get("name") or "the student"
    enrollment = (student or {}).get("enrollment_no")

    if category in {"Attendance Correction Request", "Attendance Dispute"}:
        latest = (context.get("recent_logs") or [{}])[0]
        subject_name = ((latest.get("subjects") or {}).get("name")) or (
            lowest_subject or {}
        ).get("subject_name", "the relevant subject")
        lines.append(
            f"We have noted your request for verification in {subject_name}. "
            "The attendance entry will be reviewed by the concerned faculty before any correction is approved."
        )
        if latest:
            lines.append(
                f"The latest available record shows {student_name} as "
                f"{'present' if latest.get('is_present') else 'absent'} on {_format_date(latest.get('timestamp'))}."
            )
    elif category == "Medical Leave":
        lines.append(
            "We have noted the medical leave request. Please submit the required medical document through the prescribed institutional process for verification."
        )
        if leave_context.get("records"):
            latest_leave = leave_context["records"][0]
            lines.append(
                f"The latest leave record available to the system is marked as {latest_leave.get('status', 'under review')}."
            )
    elif category == "Emergency Leave":
        lines.append(
            "We have noted the emergency leave request and it has been marked for priority review by the institution."
        )
    elif category == "Leave Application":
        lines.append(
            "We have received your leave request. It will be checked against the attendance and leave records before approval."
        )
    elif category == "Low Attendance Warning":
        lines.append(
            f"The required attendance benchmark is {LOW_ATTENDANCE_THRESHOLD:.0f}%. Please attend upcoming classes regularly and contact the faculty advisor if there is a valid reason for the shortage."
        )
    elif category == "Parent Concern":
        details = f" for {student_name}"
        if enrollment:
            details += f" ({enrollment})"
        lines.append(
            f"We have reviewed the attendance summary{details}. Please coordinate with the faculty advisor for any detailed academic follow-up."
        )
    elif category == "Technical Issue":
        lines.append(
            "Please try refreshing the portal, signing in again, and checking your internet connection. If the issue continues, share a screenshot and the approximate time of the error for technical review."
        )
    elif category == "Faculty Report Request":
        lines.append(
            "Your attendance report request has been received. Class-level reports should be reviewed through the teacher dashboard or routed to administration if an official copy is required."
        )
    elif category == "Proxy Attendance Complaint":
        lines.append(
            "Your proxy attendance complaint has been marked for human review. For privacy and disciplinary reasons, the verification outcome will be handled by the authorized academic team."
        )
    elif category == "Timetable Query":
        lines.append(
            "Your timetable query has been received. Please refer to the official timetable section or contact the department office if the displayed schedule appears incorrect."
        )
    elif category == "Report Download Issue":
        lines.append(
            "Please retry the report download after refreshing the page. If the file still does not download, share the report type and date range for support review."
        )
    elif category == "Attendance Approval Request":
        lines.append(
            "Your attendance approval request has been forwarded for verification. Attendance cannot be modified automatically without authorized faculty or administrative approval."
        )
    else:
        lines.append(
            "Your message has been received. The system could not confidently classify all details, so it will be routed for appropriate review if required."
        )

    if overall is not None:
        lines.append(f"Current overall attendance percentage: {overall:.1f}%.")
    if lowest_subject:
        faculty = lowest_subject.get("faculty_name")
        subject_line = (
            f"Subject-wise note: {lowest_subject['subject_name']} is currently "
            f"{lowest_subject['attendance_percent']:.1f}%."
        )
        if faculty:
            subject_line += f" Concerned faculty: {faculty}."
        lines.append(subject_line)

    lines.extend(["Regards,", "AI Attendance Management System"])
    return "\n\n".join(lines)


# Use: Handles analyze incoming email reply behavior in this module.
# Linked with: generate_ai_reply, handle_inbound_email_reply
def analyze_incoming_email_reply(
    from_email,
    subject,
    body,
    student=None,
    teacher=None,
    attendance_context=None,
):
    student = student or _student_by_email(from_email) or _student_for_parent_text(body)
    teacher = teacher or _teacher_by_email(from_email)
    sender_type = _sender_type(from_email, body, student=student, teacher=teacher)
    category = classify_student_reply(f"{subject or ''}\n{body or ''}")
    if category not in STRICT_REPLY_CATEGORIES:
        category = "Unknown"

    student_id = (student or {}).get("student_id")
    if attendance_context:
        context = {
            "overall_percent": attendance_context.get("attendance_percent"),
            "present": attendance_context.get("present", 0),
            "total": attendance_context.get("total", 0),
            "subjects": [
                {
                    "subject_name": attendance_context.get("subject_name", "your subject"),
                    "attendance_percent": attendance_context.get("attendance_percent", 0.0),
                    "present": attendance_context.get("present", 0),
                    "total": attendance_context.get("total", 0),
                }
            ],
            "recent_logs": [],
            "database_data_used": ["attendance_percentage"],
        }
    elif student_id is not None:
        context = _student_attendance_context(student_id)
    else:
        context = {
            "overall_percent": None,
            "present": 0,
            "total": 0,
            "subjects": [],
            "recent_logs": [],
            "database_data_used": [],
        }

    leave_context = _optional_leave_context(student_id) if student_id is not None else {
        "records": [],
        "database_data_used": [],
    }
    repeated_complaints = _recent_email_complaint_count(student_id) if student_id is not None else 0
    high_risk_text = _abuse_or_legal_risk(body)
    requires_human_review = (
        sender_type == "Unknown"
        or category == "Unknown"
        or category in {
            "Proxy Attendance Complaint",
            "Attendance Correction Request",
            "Attendance Dispute",
            "Attendance Approval Request",
            "Emergency Leave",
        }
        or high_risk_text
        or repeated_complaints >= 3
    )
    priority = _priority(category, requires_human_review)
    database_data_used = sorted(
        set(
            context.get("database_data_used", [])
            + leave_context.get("database_data_used", [])
            + (["student_details"] if student else [])
            + (["teacher_records"] if teacher else [])
            + (["previous_email_history"] if repeated_complaints else [])
        )
    )
    reply_email = _build_personalized_reply(
        sender_type=sender_type,
        category=category,
        student=student,
        teacher=teacher,
        context=context,
        leave_context=leave_context,
    )

    return {
        "sender_type": sender_type,
        "category": category,
        "priority": priority,
        "requires_human_review": requires_human_review,
        "database_data_used": database_data_used,
        "detected_sentiment": _sentiment(body),
        "reply_email_subject": _reply_subject(category),
        "reply_email": reply_email,
    }


# Use: Processes delivery webhook input for the workflow.
# Linked with: Streamlit UI, decorators, tests, or external runtime calls.
def process_delivery_webhook(message_id, event_type, payload=None):
    status_by_event = {
        "processed": "processed",
        "delivered": "delivered",
        "open": "opened",
        "opened": "opened",
        "bounce": "failed",
        "bounced": "failed",
        "dropped": "failed",
        "spamreport": "failed",
    }
    event = (event_type or "").lower()
    status = status_by_event.get(event, event or "unknown")
    patch = {
        "status": status,
        "metadata": payload or {},
    }
    if status == "delivered":
        patch["delivered_at"] = _now_iso()
    if status == "opened":
        patch["opened_at"] = _now_iso()
    if status == "failed":
        patch["error_message"] = str((payload or {}).get("reason") or event_type)

    try:
        require_supabase().table("email_logs").update(patch).eq(
            "message_id", message_id
        ).execute()
        return {"ok": True, "message_id": message_id, "status": status}
    except Exception as exc:
        if _table_missing(exc):
            return {"ok": False, "error": "email_logs table missing"}
        return {"ok": False, "error": str(exc)}


# Use: Internal helper for student by email.
# Linked with: _insert_inbound_processing_log, analyze_incoming_email_reply, handle_inbound_email_reply
def _student_by_email(email):
    if not email:
        return None
    rows = _safe_table_select("students", "*", email_id=email)
    return rows[0] if rows else None


# Use: Internal helper for latest subject context.
# Linked with: _insert_inbound_processing_log, handle_inbound_email_reply
def _latest_subject_context(student_id):
    response = (
        require_supabase()
        .table("attendance_logs")
        .select("subject_id, is_present, subjects(name)")
        .eq("student_id", student_id)
        .order("timestamp", desc=True)
        .limit(1)
        .execute()
    )
    if not response.data:
        return {}
    latest = response.data[0]
    subject_id = latest.get("subject_id")
    analytics = build_subject_analytics(subject_id).get(int(student_id), {})
    return {
        "subject_id": subject_id,
        "subject_name": (latest.get("subjects") or {}).get("name", "your subject"),
        **analytics,
    }


# Use: Internal helper for upsert thread.
# Linked with: _insert_inbound_processing_log, handle_inbound_email_reply
def _upsert_thread(student_id, subject_id, intent):
    thread_key = f"student:{student_id}:subject:{subject_id or 'general'}"
    supabase = require_supabase()
    existing = (
        supabase.table("email_threads")
        .select("*")
        .eq("thread_key", thread_key)
        .limit(1)
        .execute()
        .data
    )
    if existing:
        thread = existing[0]
        supabase.table("email_threads").update(
            {
                "intent": intent,
                "updated_at": _now_iso(),
            }
        ).eq("id", thread["id"]).execute()
        return thread

    response = (
        supabase.table("email_threads")
        .insert(
            {
                "student_id": student_id,
                "subject_id": subject_id,
                "thread_key": thread_key,
                "intent": intent,
                "created_at": _now_iso(),
                "updated_at": _now_iso(),
            }
        )
        .execute()
    )
    return response.data[0] if response.data else {"thread_key": thread_key}


# Use: Internal helper for insert thread message.
# Linked with: _insert_inbound_processing_log, handle_inbound_email_reply
def _insert_thread_message(thread_id, student_id, direction, body, **extra):
    try:
        require_supabase().table("email_messages").insert(
            {
                "thread_id": thread_id,
                "student_id": student_id,
                "direction": direction,
                "body": body,
                "created_at": _now_iso(),
                **extra,
            }
        ).execute()
    except Exception as exc:
        if not _table_missing(exc):
            print(f"Email message log failed: {exc}")


# Use: Handles handle inbound email reply behavior in this module.
# Linked with: poll_inbound_email_replies
def handle_inbound_email_reply(from_email, subject, body):
    student = _student_by_email(from_email)
    teacher = _teacher_by_email(from_email)
    analysis = analyze_incoming_email_reply(
        from_email=from_email,
        subject=subject,
        body=body,
        student=student,
        teacher=teacher,
    )

    thread_id = None
    student_id = (student or {}).get("student_id")
    subject_id = None
    if student_id is not None:
        context = _latest_subject_context(student_id)
        subject_id = context.get("subject_id")
        thread = _upsert_thread(student_id, subject_id, analysis["category"])
        thread_id = thread.get("id")

    if student_id is not None:
        _insert_thread_message(
            thread_id,
            student_id,
            "inbound",
            body,
            intent=analysis["category"],
            from_email=from_email,
            subject=subject,
            escalate=analysis["requires_human_review"],
            metadata={"sender_type": analysis["sender_type"]},
        )
        _insert_thread_message(
            thread_id,
            student_id,
            "ai_reply",
            analysis["reply_email"],
            intent=analysis["category"],
            to_email=from_email,
            subject=analysis["reply_email_subject"],
            ai_generated=True,
            escalate=analysis["requires_human_review"],
            metadata=analysis,
        )

    _send_message(
        to_email=from_email,
        subject=analysis["reply_email_subject"],
        body=analysis["reply_email"],
    )
    return {"ok": True, "escalate": analysis["requires_human_review"], **analysis}


# Use: Internal helper for imap credentials.
# Linked with: poll_inbound_email_replies
def _imap_credentials():
    host = get_secret("IMAP_HOST", "imap.gmail.com")
    port = int(get_secret("IMAP_PORT", 993))
    username = (
        get_secret("IMAP_USER")
        or get_secret("SENDER_EMAIL")
        or get_secret("SMTP_USER")
    )
    password = (
        get_secret("IMAP_PASSWORD")
        or get_secret("SENDER_PASSWORD")
        or get_secret("SMTP_PASS")
    )
    if not username or not password:
        raise RuntimeError(
            "Inbound email is not configured. Add IMAP_USER/IMAP_PASSWORD or "
            "SENDER_EMAIL/SENDER_PASSWORD in .streamlit/secrets.toml."
        )
    return str(host).strip(), port, str(username).strip(), str(password).replace(" ", "").strip()


# Use: Internal helper for plain text from message.
# Linked with: poll_inbound_email_replies
def _plain_text_from_message(message):
    if message.is_multipart():
        for part in message.walk():
            content_type = part.get_content_type()
            disposition = str(part.get_content_disposition() or "")
            if content_type == "text/plain" and disposition != "attachment":
                try:
                    return part.get_content().strip()
                except Exception:
                    payload = part.get_payload(decode=True) or b""
                    return payload.decode(part.get_content_charset() or "utf-8", errors="replace").strip()
        for part in message.walk():
            if part.get_content_type() == "text/html":
                try:
                    text = part.get_content()
                except Exception:
                    payload = part.get_payload(decode=True) or b""
                    text = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
                text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", "", text)
                text = re.sub(r"(?s)<[^>]+>", " ", text)
                return html.unescape(re.sub(r"\s+", " ", text)).strip()
        return ""

    try:
        return message.get_content().strip()
    except Exception:
        payload = message.get_payload(decode=True) or b""
        return payload.decode(message.get_content_charset() or "utf-8", errors="replace").strip()


# Use: Internal helper for is auto generated message.
# Linked with: poll_inbound_email_replies
def _is_auto_generated_message(message):
    headers = [
        str(message.get("Auto-Submitted", "")).lower(),
        str(message.get("Precedence", "")).lower(),
        str(message.get("X-Auto-Response-Suppress", "")).lower(),
    ]
    return any(
        value and value not in {"no", "false"}
        for value in headers
    )


# Use: Internal helper for message already processed.
# Linked with: poll_inbound_email_replies
def _message_already_processed(message_id):
    """Avoid replying twice to the same inbound email during this app process."""
    if not message_id:
        return False
    if message_id in _PROCESSED_INBOUND_MESSAGE_IDS:
        return True
    rows = _safe_table_select(
        "email_messages",
        "id",
        metadata={"inbound_message_id": message_id},
    )
    return bool(rows)


# Use: Internal helper for insert inbound processing log.
# Linked with: poll_inbound_email_replies
def _insert_inbound_processing_log(message_id, from_email, subject, result):
    student = _student_by_email(from_email)
    student_id = (student or {}).get("student_id")
    thread_id = None
    if student_id is not None:
        context = _latest_subject_context(student_id)
        thread = _upsert_thread(student_id, context.get("subject_id"), result.get("category"))
        thread_id = thread.get("id")
        _insert_thread_message(
            thread_id,
            student_id,
            "inbound_processed",
            result.get("reply_email", ""),
            intent=result.get("category"),
            from_email=from_email,
            subject=subject,
            ai_generated=True,
            escalate=result.get("requires_human_review", False),
            metadata={
                "inbound_message_id": message_id,
                "auto_reply_sent": result.get("ok", False),
            },
        )


# Use: Handles poll inbound email replies behavior in this module.
# Linked with: _inbound_poller_loop
def poll_inbound_email_replies(limit=10):
    """Read unread inbox messages, auto-reply once, then mark each handled message seen."""
    host, port, username, password = _imap_credentials()
    processed = 0
    replied = 0
    skipped = 0
    errors = []

    with imaplib.IMAP4_SSL(host, port) as mailbox:
        mailbox.login(username, password)
        mailbox.select("INBOX")
        status, data = mailbox.search(None, "UNSEEN")
        if status != "OK":
            return {
                "ok": False,
                "processed": 0,
                "replied": 0,
                "skipped": 0,
                "errors": ["IMAP search failed"],
            }

        message_ids = (data[0] or b"").split()[-limit:]
        for imap_id in message_ids:
            try:
                status, fetched = mailbox.fetch(imap_id, "(RFC822)")
                if status != "OK" or not fetched or not fetched[0]:
                    skipped += 1
                    continue

                raw_message = fetched[0][1]
                message = BytesParser(policy=policy.default).parsebytes(raw_message)
                message_id = str(message.get("Message-ID", "")).strip()
                sender = parseaddr(message.get("From", ""))[1]
                subject = str(message.get("Subject", "Attendance Query")).strip()
                body = _plain_text_from_message(message)

                if _message_already_processed(message_id):
                    mailbox.store(imap_id, "+FLAGS", "\\Seen")
                    skipped += 1
                    continue
                if not sender or not body or _is_auto_generated_message(message):
                    mailbox.store(imap_id, "+FLAGS", "\\Seen")
                    skipped += 1
                    continue
                if sender.lower() == username.lower():
                    mailbox.store(imap_id, "+FLAGS", "\\Seen")
                    skipped += 1
                    continue

                result = handle_inbound_email_reply(sender, subject, body)
                _insert_inbound_processing_log(message_id, sender, subject, result)
                if message_id:
                    _PROCESSED_INBOUND_MESSAGE_IDS.add(message_id)
                mailbox.store(imap_id, "+FLAGS", "\\Seen")
                processed += 1
                if result.get("ok"):
                    replied += 1
            except Exception as exc:
                errors.append(str(exc))

        mailbox.logout()

    return {
        "ok": not errors,
        "processed": processed,
        "replied": replied,
        "skipped": skipped,
        "errors": errors,
    }


# Use: Internal helper for inbound poller loop.
# Linked with: Streamlit UI, decorators, tests, or external runtime calls.
def _inbound_poller_loop():
    """Background worker for inbound email auto-replies; quiet unless debug/errors exist."""
    while not _INBOUND_POLLER_STOP.is_set():
        try:
            result = poll_inbound_email_replies(limit=10)
            if result.get("errors") or (INBOUND_POLL_DEBUG_LOGS and result.get("processed")):
                print(f"Inbound email poll result: {result}")
        except Exception as exc:
            print(f"Inbound email poll failed: {exc}")
        _INBOUND_POLLER_STOP.wait(INBOUND_POLL_INTERVAL_SECONDS)


# Use: Handles start inbound email poller behavior in this module.
# Linked with: main
def start_inbound_email_poller():
    """Start one inbound email polling thread per Python process."""
    global _INBOUND_POLLER_THREAD
    enabled = str(get_secret("ENABLE_INBOUND_EMAIL_AUTOREPLY", "true")).lower()
    if enabled in {"0", "false", "no", "off"}:
        return {"started": False, "reason": "disabled"}
    with _INBOUND_POLLER_LOCK:
        if _INBOUND_POLLER_THREAD and _INBOUND_POLLER_THREAD.is_alive():
            return {"started": False, "reason": "already_running"}

        _INBOUND_POLLER_STOP.clear()
        _INBOUND_POLLER_THREAD = threading.Thread(
            target=_inbound_poller_loop,
            name="inbound-email-autoreply",
            daemon=True,
        )
        _INBOUND_POLLER_THREAD.start()
        return {"started": True, "interval_seconds": INBOUND_POLL_INTERVAL_SECONDS}
