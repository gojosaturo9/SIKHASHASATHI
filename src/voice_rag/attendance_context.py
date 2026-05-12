from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

import streamlit as st

from src.database.config import supabase
from src.database.db import (
    get_all_attendance_records,
    get_attendance_for_teacher,
    get_students_for_subject,
    get_student_attendance,
    get_student_subjects,
    get_teacher_subjects,
)
from src.voice_rag.documents import Document, json_to_documents


SENSITIVE_FIELDS = {
    "password",
    "face_embedding",
    "voice_embedding",
    "face_encodings",
    "voice_data",
}


# Use: Handles clean record behavior in this module.
# Linked with: _safe_rows, _student_summary, _teacher_summary, clean_record
def clean_record(value):
    if isinstance(value, dict):
        return {
            key: clean_record(val)
            for key, val in value.items()
            if key not in SENSITIVE_FIELDS
        }
    if isinstance(value, list):
        return [clean_record(item) for item in value]
    return value


# Use: Builds role context data used by another workflow.
# Linked with: _load_dashboard_scope, build_role_documents
def build_role_context(role: str) -> dict:
    if role == "admin":
        return _admin_summary()
    if role == "teacher":
        teacher = st.session_state.get("teacher_data") or {}
        teacher_id = teacher.get("teacher_id")
        return _teacher_summary(
            teacher,
            get_teacher_subjects(teacher_id),
            get_attendance_for_teacher(teacher_id),
        )
    if role == "student":
        student = st.session_state.get("student_data") or {}
        student_id = student.get("student_id")
        return _student_summary(
            student,
            get_student_subjects(student_id),
            get_student_attendance(student_id),
        )
    return {}


# Use: Builds role documents data used by another workflow.
# Linked with: Streamlit UI, decorators, tests, or external runtime calls.
def build_role_documents(role: str) -> list[Document]:
    context = build_role_context(role)
    docs = json_to_documents(context, source=f"{role}_attendance_scope", metadata={"role": role})
    if not docs:
        return [Document(text="No permitted records are currently available.", metadata={"role": role})]
    return docs


# Use: Internal helper for safe rows.
# Linked with: _admin_summary, _student_summary, _teacher_summary
def _safe_rows(rows, limit=80):
    return [clean_record(row) for row in (rows or [])[:limit]]


# Use: Internal helper for extract date.
# Linked with: _date_from_timestamp, _teacher_summary
def _extract_date(timestamp):
    if not timestamp:
        return "Unknown date"
    return str(timestamp).split("T")[0].split(" ")[0]


# Use: Internal helper for date from timestamp.
# Linked with: _teacher_summary
def _date_from_timestamp(timestamp):
    try:
        return datetime.fromisoformat(str(timestamp).replace("Z", "+00:00")).date()
    except Exception:
        try:
            return date.fromisoformat(_extract_date(timestamp))
        except Exception:
            return None


# Use: Internal helper for student summary.
# Linked with: build_role_context
def _student_summary(student, subjects, attendance):
    subject_names = []
    subject_by_id = {}
    for item in subjects or []:
        sub = item.get("subjects") or {}
        if sub:
            subject_names.append(f"{sub.get('name')} ({sub.get('subject_code')})")
            subject_by_id[sub.get("subject_id")] = sub

    totals = defaultdict(lambda: {"total": 0, "present": 0})
    for log in attendance or []:
        subject_id = log.get("subject_id")
        totals[subject_id]["total"] += 1
        if log.get("is_present"):
            totals[subject_id]["present"] += 1

    attendance_lines = []
    alerts = []
    for subject_id, stats in totals.items():
        sub = subject_by_id.get(subject_id, {})
        total = stats["total"]
        present = stats["present"]
        percentage = round((present / total) * 100, 1) if total else 0
        attendance_lines.append(
            f"{sub.get('name', subject_id)}: {present}/{total} present ({percentage}%)"
        )
        if total and percentage < 75:
            alerts.append(
                f"{sub.get('name', subject_id)} attendance is below 75% ({percentage}%)."
            )

    return {
        "profile": clean_record(student),
        "enrolled_subjects": subject_names,
        "attendance_summary": attendance_lines,
        "alerts": alerts,
        "recent_attendance": _safe_rows(
            sorted(attendance or [], key=lambda row: row.get("timestamp") or "", reverse=True),
            limit=40,
        ),
    }


# Use: Internal helper for teacher summary.
# Linked with: build_role_context
def _teacher_summary(teacher, subjects, attendance):
    subject_names = [
        f"{sub.get('name')} ({sub.get('subject_code')})" for sub in subjects or []
    ]
    per_subject = defaultdict(lambda: {"total": 0, "present": 0, "students": set()})
    recent_sessions = Counter()
    week_start = date.today() - timedelta(days=6)
    weekly = defaultdict(lambda: {"total": 0, "present": 0, "students": set(), "sessions": set()})

    for log in attendance or []:
        sub = log.get("subjects") or {}
        student = log.get("students") or {}
        subject_name = sub.get("name", "Unknown subject")
        log_date = _date_from_timestamp(log.get("timestamp"))
        per_subject[subject_name]["total"] += 1
        per_subject[subject_name]["students"].add(student.get("name", "Unknown"))
        if log.get("is_present"):
            per_subject[subject_name]["present"] += 1
        recent_sessions[(subject_name, _extract_date(log.get("timestamp")))] += 1
        if log_date and log_date >= week_start:
            weekly[subject_name]["total"] += 1
            weekly[subject_name]["students"].add(student.get("name", "Unknown"))
            weekly[subject_name]["sessions"].add(log_date.isoformat())
            if log.get("is_present"):
                weekly[subject_name]["present"] += 1

    summary = []
    enrolled_by_subject = []
    for subject_name, stats in per_subject.items():
        total = stats["total"]
        present = stats["present"]
        percentage = round((present / total) * 100, 1) if total else 0
        summary.append(
            {
                "subject": subject_name,
                "students_seen": len(stats["students"]),
                "present_marks": present,
                "total_marks": total,
                "attendance_percent": percentage,
            }
        )

    for subject in subjects or []:
        subject_id = subject.get("subject_id")
        students = get_students_for_subject(subject_id) if subject_id else []
        enrolled_by_subject.append(
            {
                "subject_id": subject_id,
                "subject": subject.get("name"),
                "subject_code": subject.get("subject_code"),
                "students": _safe_rows(students, limit=120),
                "total_students": len(students or []),
            }
        )

    student_subject_totals = defaultdict(lambda: {"total": 0, "present": 0})
    for log in attendance or []:
        student = log.get("students") or {}
        subject = log.get("subjects") or {}
        key = (
            student.get("student_id"),
            student.get("name", "Unknown student"),
            subject.get("name", "Unknown subject"),
        )
        student_subject_totals[key]["total"] += 1
        if log.get("is_present"):
            student_subject_totals[key]["present"] += 1

    low_attendance = []
    for (student_id, student_name, subject_name), stats in student_subject_totals.items():
        total = stats["total"]
        present = stats["present"]
        percentage = round((present / total) * 100, 1) if total else 0
        if total and percentage < 75:
            low_attendance.append(
                {
                    "student_id": student_id,
                    "student": student_name,
                    "subject": subject_name,
                    "present": present,
                    "total": total,
                    "attendance_percent": percentage,
                }
            )

    weekly_summary = []
    for subject_name, stats in weekly.items():
        total = stats["total"]
        present = stats["present"]
        percentage = round((present / total) * 100, 1) if total else 0
        weekly_summary.append(
            {
                "subject": subject_name,
                "present_marks": present,
                "total_marks": total,
                "attendance_percent": percentage,
                "students_seen": len(stats["students"]),
                "sessions": len(stats["sessions"]),
            }
        )

    total_enrolled_students = sum(
        row.get("total_students", 0) for row in enrolled_by_subject
    )

    return {
        "teacher": clean_record(teacher),
        "subjects": subject_names,
        "enrolled_students_by_subject": enrolled_by_subject,
        "total_enrolled_students": total_enrolled_students,
        "attendance_summary": summary,
        "weekly_attendance_summary": weekly_summary,
        "low_attendance_students": low_attendance,
        "recent_attendance": _safe_rows(
            sorted(attendance or [], key=lambda row: row.get("timestamp") or "", reverse=True),
            limit=80,
        ),
        "recent_sessions": [
            {"subject": item[0][0], "date": item[0][1], "records": item[1]}
            for item in recent_sessions.most_common(25)
        ],
    }


# Use: Internal helper for admin summary.
# Linked with: build_role_context
def _admin_summary():
    students = supabase.table("students").select("*").execute().data
    teachers = (
        supabase.table("teachers")
        .select("teacher_id, name, username, email_id")
        .execute()
        .data
    )
    subjects = supabase.table("subjects").select("*").execute().data
    attendance = get_all_attendance_records()

    # Use: Handles group count behavior in this module.
    # Linked with: _admin_summary
    def group_count(rows, key):
        return dict(Counter(row.get(key, "Unknown") for row in rows or []))

    return {
        "totals": {
            "students": len(students or []),
            "teachers": len(teachers or []),
            "subjects": len(subjects or []),
            "attendance_records": len(attendance or []),
        },
        "students_by_branch": group_count(students, "branch"),
        "students_by_semester": group_count(students, "semester"),
        "students_by_section": group_count(students, "section"),
        "teachers": _safe_rows(teachers, limit=100),
        "students": _safe_rows(students, limit=100),
        "subjects": _safe_rows(subjects, limit=100),
        "attendance_records": _safe_rows(attendance, limit=160),
    }
