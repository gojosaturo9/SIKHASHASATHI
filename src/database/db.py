import time
from datetime import datetime, timedelta, timezone

from src.database.config import require_admin_supabase, require_supabase


ATTENDANCE_AUDIT_FIELDS = {
    "source",
    "photo_detected",
    "manual_override",
    "override_by_role",
    "override_by_id",
    "override_by_name",
    "override_reason",
    "override_at",
    "editable_until",
}

TRANSIENT_DB_ERROR_MARKERS = (
    "readerror",
    "writeerror",
    "connecterror",
    "timeout",
    "timed out",
    "winerror 10035",
    "non-blocking socket operation",
    "connection reset",
    "connection aborted",
    "remoteprotocolerror",
    "server disconnected",
    "server disconnected without sending a response",
)


class StudentRegistrationPolicyError(RuntimeError):
    """Raised when Supabase RLS blocks a new student insert."""
    pass


# Use: Internal helper for is transient db error.
# Linked with: _execute_with_retry
def _is_transient_db_error(exc):
    text = f"{type(exc).__name__}: {exc}".lower()
    return any(marker in text for marker in TRANSIENT_DB_ERROR_MARKERS)


# Use: Internal helper for is rls policy error.
# Linked with: create_student
def _is_rls_policy_error(exc):
    text = str(exc).lower()
    return "42501" in text or "row-level security" in text


# Use: Internal helper for execute with retry.
# Linked with: cleanup_old_feedback, create_attendance, create_subject, create_subject_feedback, create_teacher, delete_subject_feedback, enroll_student_to_matching_class_subjects, get_all_attendance_records and more
def _execute_with_retry(build_query, attempts=3, base_delay=0.6):
    last_exc = None
    for attempt in range(1, attempts + 1):
        try:
            return build_query().execute()
        except Exception as exc:
            last_exc = exc
            if attempt >= attempts or not _is_transient_db_error(exc):
                raise
            time.sleep(base_delay * attempt)
    raise last_exc


# Use: Internal helper for is missing audit column error.
# Linked with: create_attendance, get_all_attendance_records, get_editable_attendance_for_teacher, update_attendance_override
def _is_missing_audit_column_error(exc):
    text = str(exc)
    return "42703" in text and "attendance_logs" in text


# Use: Internal helper for is missing feedback table error.
# Linked with: cleanup_old_feedback, create_subject_feedback, delete_subject_feedback, get_student_feedback, get_teacher_feedback, reply_to_subject_feedback, update_subject_feedback
def _is_missing_feedback_table_error(exc):
    text = str(exc).lower()
    return (
        "42p01" in text
        or "pgrst205" in text
        or "feedback" in text and "could not find" in text
        or "feedback" in text and "does not exist" in text
    )


# Use: Internal helper for is missing announcements table error.
# Linked with: create_announcement, get_active_announcements, cleanup_old_announcements
def _is_missing_announcements_table_error(exc):
    text = str(exc).lower()
    return (
        "42p01" in text
        or "pgrst205" in text
        or "announcements" in text and "could not find" in text
        or "announcements" in text and "does not exist" in text
    )


# Use: Internal helper for utc iso timestamp.
# Linked with: create_announcement, get_active_announcements, cleanup_old_announcements
def _utc_iso(timestamp=None):
    return (timestamp or datetime.now(timezone.utc)).isoformat(timespec="seconds")


# Use: Checks whether the feedback table exists before showing feedback UI.
# Linked with: student_dashboard, teacher_tab_student_feedback
def feedback_table_available():
    supabase = require_admin_supabase()
    try:
        _execute_with_retry(
            lambda: supabase.table("feedback").select("id").limit(1),
            attempts=2,
            base_delay=0.3,
        )
        return True
    except Exception as exc:
        if _is_missing_feedback_table_error(exc):
            return False
        raise


# Use: Internal helper for strip attendance audit fields.
# Linked with: create_attendance
def _strip_attendance_audit_fields(logs):
    return [
        {key: value for key, value in log.items() if key not in ATTENDANCE_AUDIT_FIELDS}
        for log in logs
    ]


# Use: Internal helper for as list.
# Linked with: _student_matches_class
def _as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


# Use: Internal helper for normalize branch.
# Linked with: _student_matches_class
def _normalize_branch(value):
    normalized = (
        str(value or "")
        .strip()
        .lower()
        .replace(" ", "")
        .replace("_", "")
        .replace("-", "")
        .replace("/", "")
        .replace("&", "and")
    )
    aliases = {
        "cs": "computerscience",
        "cse": "computerscience",
        "computer": "computerscience",
        "computerengineering": "computerscience",
        "computerscienceengineering": "computerscience",
        "computerscienceandengineering": "computerscience",
        "it": "informationtech",
        "informationtechnology": "informationtech",
        "informationtechnologyengineering": "informationtech",
        "aiml": "aiml",
        "artificialintelligencemachinelearning": "aiml",
        "aids": "aids",
        "artificialintelligencedatascience": "aids",
        "datascience": "ds",
        "ece": "ece",
        "electronicscommunication": "ece",
        "electronicsandcommunication": "ece",
    }
    return aliases.get(normalized, normalized)


# Use: Internal helper for normalize section.
# Linked with: _student_matches_class
def _normalize_section(value):
    return str(value or "").strip().upper()


# Use: Internal helper for normalize semester.
# Linked with: _student_matches_class
def _normalize_semester(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return str(value or "").strip()


# Use: Internal helper for student matches class.
# Linked with: enroll_student_to_matching_class_subjects, get_students_matching_class
def _student_matches_class(student, branches, semesters, sections):
    branch_filters = {_normalize_branch(branch) for branch in _as_list(branches) if branch}
    semester_filters = {
        _normalize_semester(semester) for semester in _as_list(semesters) if semester != ""
    }
    section_filters = {
        _normalize_section(section) for section in _as_list(sections) if section
    }

    branch_ok = (
        not branch_filters
        or _normalize_branch(student.get("branch")) in branch_filters
    )
    semester_ok = (
        not semester_filters
        or _normalize_semester(student.get("semester")) in semester_filters
    )
    section_ok = (
        not section_filters
        or _normalize_section(student.get("section")) in section_filters
    )
    return branch_ok and semester_ok and section_ok


# Use: Checks check pass condition for control flow.
# Linked with: change_password_dialog, teacher_screen_login
def check_pass(pwd, hashed):
    import bcrypt

    return bcrypt.checkpw(pwd.encode(), hashed.encode())


# Use: Fetches teacher by username data for the app flow.
# Linked with: teacher_screen_login
def get_teacher_by_username(username):
    """Fetch one teacher login row with retry for temporary Supabase disconnects."""
    supabase = require_admin_supabase()
    username = str(username or "").strip()
    response = _execute_with_retry(
        lambda: supabase.table("teachers")
        .select("*")
        .eq("username", username),
        attempts=4,
        base_delay=0.8,
    )
    return response.data[0] if response.data else None


# Use: Creates teacher data in the app/database flow.
# Linked with: Streamlit UI, decorators, tests, or external runtime calls.
def create_teacher(name, username, email_id, hashed_password):
    """Create a teacher account and return the inserted row including teacher_id."""
    supabase = require_admin_supabase()
    name = str(name or "").strip()
    username = str(username or "").strip()
    email_id = str(email_id or "").strip()
    existing = _execute_with_retry(
        lambda: supabase.table("teachers")
        .select("teacher_id, username")
        .eq("username", username),
        attempts=4,
        base_delay=0.8,
    )
    if existing.data:
        return {"ok": False, "teacher": None, "error": "Username already exists"}

    response = _execute_with_retry(
        lambda: supabase.table("teachers").insert(
            {
                "name": name,
                "username": username,
                "email_id": email_id,
                "password": hashed_password,
            }
        ),
        attempts=4,
        base_delay=0.8,
    )
    return {"ok": True, "teacher": response.data[0] if response.data else None, "error": None}


# Use: Updates teacher password data after a user or system action.
# Linked with: attendance_analytics_tab
def update_teacher_password(username, hashed_password):
    """Admin password reset for a teacher account."""
    supabase = require_admin_supabase()
    response = _execute_with_retry(
        lambda: supabase.table("teachers")
        .update({"password": hashed_password})
        .eq("username", str(username or "").strip()),
        attempts=4,
        base_delay=0.8,
    )
    return response.data


# Use: Fetches all students data for the app flow.
# Linked with: get_trained_model, student_screen
def get_all_students():
    """Fetch students with biometric fields for face matching."""
    supabase = require_admin_supabase()
    response = _execute_with_retry(
        lambda: supabase.table("students").select("*"),
        attempts=4,
        base_delay=0.8,
    )
    return response.data


# Use: Fetches student by enrollment data for the app flow.
# Linked with: Streamlit UI, decorators, tests, or external runtime calls.
def get_student_by_enrollment(enrollment_no):
    supabase = require_admin_supabase()
    response = _execute_with_retry(
        lambda: supabase.table("students")
        .select("*")
        .eq("enrollment_no", enrollment_no.strip()),
        attempts=4,
        base_delay=0.8,
    )
    return response.data[0] if response.data else None


# Use: Updates student face embedding data after a user or system action.
# Linked with: Streamlit UI, decorators, tests, or external runtime calls.
def update_student_face_embedding(student_id, face_embedding):
    supabase = require_admin_supabase()
    response = _execute_with_retry(
        lambda: supabase.table("students")
        .update({"face_embedding": face_embedding})
        .eq("student_id", student_id),
        attempts=4,
        base_delay=0.8,
    )
    return response.data


# Use: Creates student data in the app/database flow.
# Linked with: add_student_tab, student_screen
def create_student(
    name,
    email_id,
    enrollment_no,
    branch,
    semester,
    section,
    face_embedding=None,
    voice_embedding=None,
):
    """Insert a student profile, then auto-enroll them into matching class-wise subjects."""
    supabase = require_admin_supabase()

    new_student_data = {
        "name": name,
        "email_id": email_id,
        "enrollment_no": enrollment_no,
        "branch": branch,
        "semester": semester,
        "section": section,
        "face_embedding": face_embedding,
        "voice_embedding": voice_embedding,
    }

    try:
        response = supabase.table("students").insert(new_student_data).execute()
    except Exception as exc:
        if _is_rls_policy_error(exc):
            raise StudentRegistrationPolicyError(
                "Supabase RLS is blocking student registration. Run "
                "supabase_student_registration_rls.sql in the Supabase SQL Editor."
            ) from exc
        raise
    if response.data:
        enroll_student_to_matching_class_subjects(response.data[0])
    return response.data


# Use: Creates subject data in the app/database flow.
# Linked with: create_subject_dialog
def create_subject(
    teacher_id,
    code,
    name,
    sub_type="mixed",
    target_branch=None,
    target_semester=None,
    target_section=None,
):
    supabase = require_admin_supabase()
    try:
        data = {
            "teacher_id": teacher_id,
            "subject_code": code,
            "name": name,
            "type": sub_type,
            "target_branch": target_branch if target_branch else [],
            "target_semester": target_semester if target_semester else [],
            "target_section": target_section if target_section else [],
        }
        response = _execute_with_retry(
            lambda: supabase.table("subjects").insert(data),
            attempts=4,
            base_delay=0.8,
        )
        if not response.data:
            return {"created": False, "enrolled_count": 0}

        enrolled_count = 0
        if sub_type == "class_wise":
            enrolled_count = enroll_matching_students_to_subject(
                response.data[0]["subject_id"],
                target_branch,
                target_semester,
                target_section,
            )

        return {
            "created": True,
            "subject": response.data[0],
            "enrolled_count": enrolled_count,
        }
    except Exception as e:
        print(f"Error creating subject: {e}")
        raise e


# Use: Fetches teacher subjects data for the app flow.
# Linked with: build_role_context, teacher_tab_manage_subjects, teacher_tab_take_attendance
def get_teacher_subjects(teacher_id):
    supabase = require_admin_supabase()
    response = _execute_with_retry(
        lambda: supabase.table("subjects")
        .select("*, subject_students(count), attendance_logs(timestamp)")
        .eq("teacher_id", teacher_id)
    )
    subjects = response.data

    for sub in subjects:
        sub["total_students"] = (
            sub.get("subject_students", [{}])[0].get("count", 0)
            if sub.get("subject_students")
            else 0
        )
        attendance = sub.get("attendance_logs", [])
        unique_sessions = len(set(log["timestamp"] for log in attendance))
        sub["total_classes"] = unique_sessions

        sub.pop("subject_student", None)
        sub.pop("attendance_logs", None)

    return subjects


# Use: Handles enroll student to subject behavior in this module.
# Linked with: Streamlit UI, decorators, tests, or external runtime calls.
def enroll_student_to_subject(student_id, subject_id):
    supabase = require_admin_supabase()
    existing = (
        supabase.table("subject_students")
        .select("student_id")
        .eq("student_id", student_id)
        .eq("subject_id", subject_id)
        .execute()
    )
    if existing.data:
        return existing.data

    data = {"student_id": student_id, "subject_id": subject_id}
    response = supabase.table("subject_students").insert(data).execute()
    return response.data


# Use: Handles enroll students to subject behavior in this module.
# Linked with: enroll_matching_students_to_subject, enroll_student_to_matching_class_subjects
def enroll_students_to_subject(student_ids, subject_id):
    supabase = require_admin_supabase()
    unique_ids = sorted({student_id for student_id in student_ids if student_id is not None})
    if not unique_ids:
        return 0

    existing = (
        supabase.table("subject_students")
        .select("student_id")
        .eq("subject_id", subject_id)
        .in_("student_id", unique_ids)
        .execute()
    )
    existing_ids = {row["student_id"] for row in existing.data}
    rows = [
        {"student_id": student_id, "subject_id": subject_id}
        for student_id in unique_ids
        if student_id not in existing_ids
    ]
    if not rows:
        return 0

    response = supabase.table("subject_students").insert(rows).execute()
    return len(response.data or [])


# Use: Fetches students matching class data for the app flow.
# Linked with: enroll_matching_students_to_subject, get_students_for_subject
def get_students_matching_class(target_branch=None, target_semester=None, target_section=None):
    supabase = require_admin_supabase()
    response = _execute_with_retry(
        lambda: supabase.table("students").select("*"),
        attempts=4,
        base_delay=0.8,
    )
    return [
        student
        for student in response.data
        if _student_matches_class(student, target_branch, target_semester, target_section)
    ]


# Use: Handles enroll matching students to subject behavior in this module.
# Linked with: create_subject, sync_teacher_class_subject_enrollments
def enroll_matching_students_to_subject(
    subject_id, target_branch=None, target_semester=None, target_section=None
):
    students = get_students_matching_class(target_branch, target_semester, target_section)
    return enroll_students_to_subject(
        [student.get("student_id") for student in students],
        subject_id,
    )


# Use: Handles enroll student to matching class subjects behavior in this module.
# Linked with: create_student, get_student_subjects
def enroll_student_to_matching_class_subjects(student):
    supabase = require_admin_supabase()
    response = _execute_with_retry(
        lambda: supabase.table("subjects").select("*").eq("type", "class_wise"),
        attempts=4,
        base_delay=0.8,
    )
    enrolled_count = 0
    for subject in response.data:
        if _student_matches_class(
            student,
            subject.get("target_branch"),
            subject.get("target_semester"),
            subject.get("target_section"),
        ):
            enrolled_count += enroll_students_to_subject(
                [student.get("student_id")],
                subject["subject_id"],
            )
    return enrolled_count


# Use: Handles sync teacher class subject enrollments behavior in this module.
# Linked with: teacher_tab_manage_subjects, teacher_tab_take_attendance
def sync_teacher_class_subject_enrollments(teacher_id):
    supabase = require_admin_supabase()
    response = _execute_with_retry(
        lambda: supabase.table("subjects")
        .select("*")
        .eq("teacher_id", teacher_id)
        .eq("type", "class_wise")
    )
    enrolled_count = 0
    for subject in response.data:
        enrolled_count += enroll_matching_students_to_subject(
            subject["subject_id"],
            subject.get("target_branch"),
            subject.get("target_semester"),
            subject.get("target_section"),
        )
    return enrolled_count


# Use: Handles unenroll student to subject behavior in this module.
# Linked with: Streamlit UI, decorators, tests, or external runtime calls.
def unenroll_student_to_subject(student_id, subject_id):
    supabase = require_supabase()
    response = (
        supabase.table("subject_students")
        .delete()
        .eq("student_id", student_id)
        .eq("subject_id", subject_id)
        .execute()
    )
    return response.data


# Use: Fetches student subjects data for the app flow.
# Linked with: build_role_context, student_dashboard
def get_student_subjects(student_id):
    supabase = require_admin_supabase()
    student_response = _execute_with_retry(
        lambda: supabase.table("students").select("*").eq("student_id", student_id),
        attempts=4,
        base_delay=0.8,
    )
    if student_response.data:
        enroll_student_to_matching_class_subjects(student_response.data[0])

    response = _execute_with_retry(
        lambda: supabase.table("subject_students")
        .select("*, subjects(*)")
        .eq("student_id", student_id),
        attempts=4,
        base_delay=0.8,
    )
    return response.data


# Use: Fetches student attendance data for the app flow.
# Linked with: build_role_context, student_dashboard
def get_student_attendance(student_id):
    supabase = require_supabase()
    response = (
        supabase.table("attendance_logs")
        .select("*, subjects(*)")
        .eq("student_id", student_id)
        .execute()
    )
    return response.data


# Use: Creates subject feedback data in the app/database flow.
# Linked with: student_dashboard
def create_subject_feedback(student_id, subject_id, feedback_type, message, understanding):
    supabase = require_supabase()
    data = {
        "student_id": student_id,
        "subject_id": subject_id,
        "feedback_type": feedback_type,
        "message": message,
        "understanding": understanding,
        "status": "open",
        "created_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
    }
    try:
        response = _execute_with_retry(lambda: supabase.table("feedback").insert(data))
        return {"ok": True, "data": response.data, "error": None}
    except Exception as exc:
        if _is_missing_feedback_table_error(exc):
            return {
                "ok": False,
                "data": None,
                "error": "Feedback table missing. Run supabase_feedback_migration.sql in Supabase.",
            }
        return {"ok": False, "data": None, "error": str(exc)}


# Use: Fetches student feedback data for the app flow.
# Linked with: student_dashboard, cleanup_old_feedback
def get_student_feedback(student_id):
    supabase = require_admin_supabase()
    try:
        cutoff = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S")
        response = _execute_with_retry(
            lambda: supabase.table("feedback")
            .select("*, subjects(name, subject_code)")
            .eq("student_id", student_id)
            .gte("created_at", cutoff)
            .order("created_at", desc=True)
        )
        return response.data or []
    except Exception as exc:
        if _is_missing_feedback_table_error(exc):
            return []
        raise


# Use: Fetches teacher feedback data for the app flow.
# Linked with: teacher_tab_student_feedback, cleanup_old_feedback
def get_teacher_feedback(teacher_id):
    supabase = require_admin_supabase()
    try:
        cutoff = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S")
        teacher_subjects = _execute_with_retry(
            lambda: supabase.table("subjects")
            .select("subject_id, name, subject_code")
            .eq("teacher_id", teacher_id),
            attempts=4,
            base_delay=0.8,
        ).data or []
        subject_ids = [
            row.get("subject_id")
            for row in teacher_subjects
            if row.get("subject_id") is not None
        ]
        if not subject_ids:
            return []

        response = _execute_with_retry(
            lambda: supabase.table("feedback")
            .select(
                "*, students(name, email_id, enrollment_no, branch, semester, section), subjects(name, subject_code, teacher_id)"
            )
            .in_("subject_id", subject_ids)
            .gte("created_at", cutoff)
            .order("created_at", desc=True)
        )
        rows = response.data or []
        allowed_subject_ids = set(subject_ids)
        return [
            row
            for row in rows
            if row.get("subject_id") in allowed_subject_ids
            and (row.get("subjects") or {}).get("teacher_id", teacher_id) == teacher_id
        ]
    except Exception as exc:
        if _is_missing_feedback_table_error(exc):
            return []
        raise


# Use: Handles reply to subject feedback behavior in this module.
# Linked with: teacher_tab_student_feedback
def reply_to_subject_feedback(feedback_id, teacher_id, reply_text):
    supabase = require_admin_supabase()
    data = {
        "teacher_reply": reply_text,
        "reply_teacher_id": teacher_id,
        "reply_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "status": "replied",
    }
    try:
        response = _execute_with_retry(
            lambda: supabase.table("feedback").update(data).eq("id", feedback_id)
        )
        return {"ok": True, "data": response.data, "error": None}
    except Exception as exc:
        if _is_missing_feedback_table_error(exc):
            return {
                "ok": False,
                "data": None,
                "error": "Feedback table missing. Run supabase_feedback_migration.sql in Supabase.",
            }
        return {"ok": False, "data": None, "error": str(exc)}


# Use: Updates subject feedback data after a user or system action.
# Linked with: student_dashboard
def update_subject_feedback(feedback_id, student_id, feedback_type, message, understanding):
    supabase = require_admin_supabase()
    data = {
        "feedback_type": feedback_type,
        "message": message,
        "understanding": understanding,
        "status": "open",
        "teacher_reply": None,
        "reply_teacher_id": None,
        "reply_at": None,
        "updated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
    }
    try:
        response = _execute_with_retry(
            lambda: supabase.table("feedback")
            .update(data)
            .eq("id", feedback_id)
            .eq("student_id", student_id)
        )
        return {"ok": True, "data": response.data, "error": None}
    except Exception as exc:
        if _is_missing_feedback_table_error(exc):
            return {
                "ok": False,
                "data": None,
                "error": "Feedback table missing. Run supabase_feedback_migration.sql in Supabase.",
            }
        return {"ok": False, "data": None, "error": str(exc)}


# Use: Deletes subject feedback data from the app/database flow.
# Linked with: student_dashboard
def delete_subject_feedback(feedback_id, student_id):
    supabase = require_admin_supabase()
    try:
        response = _execute_with_retry(
            lambda: supabase.table("feedback")
            .delete()
            .eq("id", feedback_id)
            .eq("student_id", student_id)
        )
        return {"ok": True, "data": response.data, "error": None}
    except Exception as exc:
        if _is_missing_feedback_table_error(exc):
            return {
                "ok": False,
                "data": None,
                "error": "Feedback table missing. Run supabase_feedback_migration.sql in Supabase.",
            }
        return {"ok": False, "data": None, "error": str(exc)}


# Use: Handles cleanup old feedback behavior in this module.
# Linked with: student_dashboard, teacher_dashboard
def cleanup_old_feedback(days=7):
    supabase = require_admin_supabase()
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S")
    try:
        response = _execute_with_retry(
            lambda: supabase.table("feedback").delete().lt("created_at", cutoff)
        )
        return len(response.data or [])
    except Exception as exc:
        if _is_missing_feedback_table_error(exc):
            return 0
        raise


# Use: Creates attendance data in the app/database flow.
# Linked with: show_attendance_result
def create_attendance(logs):
    supabase = require_admin_supabase()
    try:
        response = _execute_with_retry(
            lambda: supabase.table("attendance_logs").insert(logs),
            attempts=4,
            base_delay=0.8,
        )
    except Exception as exc:
        if not _is_missing_audit_column_error(exc):
            raise
        response = _execute_with_retry(
            lambda: supabase.table("attendance_logs").insert(
                _strip_attendance_audit_fields(logs)
            ),
            attempts=4,
            base_delay=0.8,
        )
    return response.data


# Use: Updates attendance override data after a user or system action.
# Linked with: teacher_tab_attendance_records
def update_attendance_override(
    attendance_id,
    is_present,
    actor_role,
    actor_id=None,
    actor_name=None,
    reason="manual override",
):
    supabase = require_supabase()
    from datetime import datetime

    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    data = {
        "is_present": bool(is_present),
        "manual_override": True,
        "override_by_role": actor_role,
        "override_by_id": str(actor_id) if actor_id is not None else None,
        "override_by_name": actor_name,
        "override_reason": reason,
        "override_at": now,
    }
    try:
        response = (
            supabase.table("attendance_logs")
            .update(data)
            .eq("id", attendance_id)
            .eq("photo_detected", False)
            .gt("editable_until", now)
            .execute()
        )
    except Exception as exc:
        if _is_missing_audit_column_error(exc):
            return []
        raise
    return response.data


# Use: Fetches editable attendance for teacher data for the app flow.
# Linked with: teacher_tab_attendance_records
def get_editable_attendance_for_teacher(teacher_id):
    supabase = require_supabase()
    from datetime import datetime

    try:
        response = (
            supabase.table("attendance_logs")
            .select(
                "id, timestamp, is_present, source, photo_detected, manual_override, "
                "override_by_role, override_by_name, override_reason, override_at, "
                "editable_until, subjects!inner(*), students!inner(name, student_id, email_id)"
            )
            .eq("subjects.teacher_id", teacher_id)
            .eq("photo_detected", False)
            .gt("editable_until", datetime.now().strftime("%Y-%m-%dT%H:%M:%S"))
            .execute()
        )
    except Exception as exc:
        if _is_missing_audit_column_error(exc):
            return []
        raise
    return response.data


# Use: Fetches subject attendance with students data for the app flow.
# Linked with: _queue_low_attendance_alerts
def get_subject_attendance_with_students(subject_id):
    supabase = require_supabase()
    response = _execute_with_retry(
        lambda: supabase.table("attendance_logs")
        .select("*, students!inner(student_id, name, email_id)")
        .eq("subject_id", subject_id)
    )
    return response.data


# Use: Fetches attendance for teacher data for the app flow.
# Linked with: build_role_context, teacher_tab_attendance_records
def get_attendance_for_teacher(teacher_id):
    supabase = require_supabase()
    response = (
        supabase.table("attendance_logs")
        .select("*, subjects!inner(*), students!inner(name, student_id, email_id)")
        .eq("subjects.teacher_id", teacher_id)
        .execute()
    )
    return response.data


# Use: Fetches subject by code data for the app flow.
# Linked with: Streamlit UI, decorators, tests, or external runtime calls.
def get_subject_by_code(subject_code):
    supabase = require_supabase()
    response = (
        supabase.table("subjects")
        .select("subject_id, name, subject_code")
        .eq("subject_code", subject_code.strip())
        .execute()
    )
    return response.data[0] if response.data else None


# Use: Checks is student enrolled condition for control flow.
# Linked with: Streamlit UI, decorators, tests, or external runtime calls.
def is_student_enrolled(student_id, subject_id):
    supabase = require_supabase()
    response = (
        supabase.table("subject_students")
        .select("student_id")
        .eq("student_id", student_id)
        .eq("subject_id", subject_id)
        .execute()
    )
    return bool(response.data)


# Use: Fetches all attendance records data for the app flow.
# Linked with: _admin_summary, attendance_analytics_tab, get_student_leaderboard
def get_all_attendance_records():
    """Fetch admin attendance analytics with retry for temporary Supabase disconnects."""
    supabase = require_supabase()
    try:
        response = _execute_with_retry(
            lambda: supabase.table("attendance_logs")
            .select(
                "id, timestamp, is_present, source, photo_detected, manual_override, "
                "override_by_role, override_by_name, override_reason, override_at, "
                "editable_until, students(student_id, name, branch, semester, section), subjects(name)"
            ),
            attempts=4,
            base_delay=0.8,
        )
    except Exception as exc:
        if not _is_missing_audit_column_error(exc):
            raise
        response = _execute_with_retry(
            lambda: supabase.table("attendance_logs")
            .select(
                "timestamp, is_present, students(student_id, name, branch, semester, section), subjects(name)"
            ),
            attempts=4,
            base_delay=0.8,
        )

    flattened_data = []
    for row in response.data:
        student_info = row.get("students", {}) or {}
        subject_info = row.get("subjects", {}) or {}
        raw_date = row.get("timestamp", "")
        formatted_date = raw_date.split("T")[0] if raw_date else "-"

        flattened_data.append(
            {
                "Date": formatted_date,
                "student_id": student_info.get("student_id"),  # ✅ naya
                "Student Name": student_info.get("name", "N/A"),
                "Subject": subject_info.get("name", "N/A"),
                "branch": student_info.get("branch", "N/A"),
                "semester": student_info.get("semester", "N/A"),
                "section": student_info.get("section", "N/A"),
                "is_present": bool(row.get("is_present", False)),  # ✅ naya
                "Status": "✅ Present" if row.get("is_present") else "❌ Absent",
                "source": row.get("source", "legacy"),
                "photo_detected": bool(row.get("photo_detected", False)),
                "manual_override": bool(row.get("manual_override", False)),
                "override_by": row.get("override_by_name") or row.get("override_by_role"),
                "override_reason": row.get("override_reason"),
                "override_at": row.get("override_at"),
                "editable_until": row.get("editable_until"),
            }
        )

    return flattened_data


# Use: Fetches student leaderboard data for the app flow.
# Linked with: student_dashboard
def get_student_leaderboard(limit=3):
    """Calculate top students across the institution by attendance percentage."""
    records = get_all_attendance_records()
    if not records:
        return []

    import pandas as pd

    df = pd.DataFrame(records)
    # Group by student_id and Name
    summary = (
        df.groupby(["student_id", "Student Name"])
        .agg(
            total_classes=("is_present", "count"),
            attended_classes=("is_present", "sum"),
        )
        .reset_index()
    )

    # Filter students who have at least 1 class session
    summary = summary[summary["total_classes"] > 0].copy()
    summary["attendance_percent"] = (
        (summary["attended_classes"] / summary["total_classes"]) * 100
    ).round(1)

    # Sort by percentage desc, then attended count desc
    leaderboard = summary.sort_values(
        by=["attendance_percent", "attended_classes"], ascending=False
    ).head(limit)

    return leaderboard.to_dict("records")


# Use: Creates announcement data in the app/database flow.
# Linked with: broadcast_tab
def create_announcement(title, content, category="General"):
    """Create a new global announcement (Admin only)."""
    supabase = require_admin_supabase()
    data = {
        "title": str(title or "").strip(),
        "content": str(content or "").strip(),
        "category": str(category or "General").strip() or "General",
        "created_at": _utc_iso(),
    }
    if not data["title"] or not data["content"]:
        raise ValueError("Title and message are required.")
    try:
        response = _execute_with_retry(
            lambda: supabase.table("announcements").insert(data),
            attempts=4,
            base_delay=0.8,
        )
        return response.data
    except Exception as exc:
        if _is_missing_announcements_table_error(exc):
            raise RuntimeError(
                "Announcements table missing. Run supabase_rls_policies.sql in Supabase."
            ) from exc
        raise


# Use: Fetches active announcements data for the app flow.
# Linked with: broadcast_tab, student_dashboard, teacher_dashboard
def get_active_announcements():
    """Fetch recent announcements (last 24 hours) for students and teachers."""
    try:
        supabase = require_admin_supabase()
        cutoff = _utc_iso(datetime.now(timezone.utc) - timedelta(hours=24))
        cleanup_old_announcements(cutoff=cutoff)

        response = (
            supabase.table("announcements")
            .select("*")
            .gte("created_at", cutoff)
            .order("created_at", desc=True)
            .limit(5)
            .execute()
        )
        return response.data
    except Exception as exc:
        if not _is_missing_announcements_table_error(exc):
            print(f"Announcement fetch error: {exc}")
        return []


# Use: Handles cleanup old announcements behavior in this module.
# Linked with: broadcast_tab
def cleanup_old_announcements(cutoff=None):
    """Physically delete announcements older than 24 hours."""
    try:
        supabase = require_admin_supabase()
        cutoff = cutoff or _utc_iso(datetime.now(timezone.utc) - timedelta(hours=24))

        response = (
            supabase.table("announcements")
            .delete()
            .lt("created_at", cutoff)
            .execute()
        )
        return response.data
    except Exception as exc:
        if not _is_missing_announcements_table_error(exc):
            print(f"Error cleaning up announcements: {exc}")
        return []


# Use: Deletes announcement data from the app/database flow.
# Linked with: broadcast_tab
def delete_announcement(ann_id):
    """Delete an announcement (Admin only)."""
    try:
        supabase = require_admin_supabase()
        response = supabase.table("announcements").delete().eq("id", ann_id).execute()
        return response.data
    except Exception as e:
        print(f"Error deleting announcement: {e}")
        return None


# Use: Fetches students for subject data for the app flow.
# Linked with: _teacher_summary, get_trained_model, teacher_tab_take_attendance
def get_students_for_subject(subject_id):
    supabase = require_admin_supabase()
    sub_response = _execute_with_retry(
        lambda: supabase.table("subjects").select("*").eq("subject_id", subject_id)
    )

    if not sub_response.data:
        return []

    subject = sub_response.data[0]
    sub_type = subject.get("type", "mixed")

    if sub_type == "class_wise":
        matched_students = get_students_matching_class(
            subject.get("target_branch"),
            subject.get("target_semester"),
            subject.get("target_section"),
        )
        if matched_students:
            return matched_students

        fallback = _execute_with_retry(
            lambda: supabase.table("subject_students")
            .select("students(*)")
            .eq("subject_id", subject_id),
            attempts=4,
            base_delay=0.8,
        )
        return [item["students"] for item in fallback.data if item.get("students")]
    else:
        res = (
            _execute_with_retry(
                lambda: supabase.table("subject_students")
            .select("students(*)")
            .eq("subject_id", subject_id)
            )
        )
        students = [item["students"] for item in res.data if item.get("students")]
        return students


# Use: Deletes teacher data from the app/database flow.
# Linked with: attendance_analytics_tab
def delete_teacher(username):
    """Delete a teacher from the database."""
    try:
        supabase = require_admin_supabase()
        response = supabase.table("teachers").delete().eq("username", username).execute()
        return response.data
    except Exception as e:
        print(f"Error deleting teacher: {e}")
        return None


# Use: Deletes student data from the app/database flow.
# Linked with: attendance_analytics_tab
def delete_student(student_id):
    """Delete a student from the database."""
    try:
        supabase = require_admin_supabase()
        response = supabase.table("students").delete().eq("student_id", student_id).execute()
        return response.data
    except Exception as e:
        print(f"Error deleting student: {e}")
        return None


# Use: Deletes subject data from the app/database flow.
# Linked with: teacher_tab_manage_subjects.share_btn
def delete_subject(subject_id):
    """Delete a subject from the database."""
    try:
        supabase = require_supabase()
        response = supabase.table("subjects").delete().eq("subject_id", subject_id).execute()
        return response.data
    except Exception as e:
        print(f"Error deleting subject: {e}")
        return None
