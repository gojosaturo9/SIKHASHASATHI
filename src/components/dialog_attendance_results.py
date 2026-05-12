from datetime import datetime
import time

import streamlit as st

from src.database.db import create_attendance, get_subject_attendance_with_students
from src.utils.email_automation import dispatch_attendance_emails
from src.utils.notifier import notify_low_attendance_bg


LOW_ATTENDANCE_THRESHOLD = 75


# Use: Internal helper for queue low attendance alerts.
# Linked with: show_attendance_result
def _queue_low_attendance_alerts(logs, subject_name):
    if not logs:
        return []

    subject_id = logs[0].get("subject_id")
    if not subject_id:
        return []

    rows = get_subject_attendance_with_students(subject_id)
    stats = {}

    for row in rows:
        student = row.get("students") or {}
        student_id = student.get("student_id")
        if student_id is None:
            continue

        item = stats.setdefault(
            student_id,
            {
                "name": student.get("name", "Student"),
                "email_id": student.get("email_id"),
                "subject_name": subject_name,
                "total_days": 0,
                "present_days": 0,
            },
        )
        item["total_days"] += 1
        if row.get("is_present"):
            item["present_days"] += 1

    alerts = []
    for item in stats.values():
        total_days = item["total_days"]
        attendance_percent = (
            item["present_days"] / total_days * 100 if total_days else 0
        )
        if attendance_percent < LOW_ATTENDANCE_THRESHOLD:
            item["attendance_percent"] = attendance_percent
            alerts.append(item)

    return alerts


# Use: Internal helper for apply pending manual overrides.
# Linked with: show_attendance_result
def _apply_pending_manual_overrides(df, logs, override_ids, reason):
    if not override_ids:
        return df, logs

    override_ids = {int(student_id) for student_id in override_ids}
    updated_df = df.copy()
    for idx, row in updated_df.iterrows():
        student_id = int(row.get("ID"))
        if student_id in override_ids and not bool(row.get("photo_detected", False)):
            updated_df.at[idx, "is_present"] = True
            updated_df.at[idx, "manual_override"] = True
            updated_df.at[idx, "override_reason"] = reason
            updated_df.at[idx, "Status"] = "Manual Present"

    updated_logs = []
    for log in logs:
        item = dict(log)
        if int(item["student_id"]) in override_ids and not item.get("photo_detected"):
            item["is_present"] = True
            item["manual_override"] = True
            item["override_by_role"] = st.session_state.get("user_role", "teacher")
            teacher = st.session_state.get("teacher_data") or {}
            item["override_by_id"] = str(teacher.get("teacher_id", ""))
            item["override_by_name"] = teacher.get("name", "Teacher")
            item["override_reason"] = reason
            item["override_at"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        updated_logs.append(item)
    return updated_df, updated_logs


# Use: Handles show attendance result behavior in this module.
# Linked with: attendance_result_dialog, teacher_tab_take_attendance, voice_attendance_dialog
def show_attendance_result(df, logs, subject_name="Selected Subject", source_kind=None):
    if "is_present" not in df.columns:
        st.error("Attendance results are missing the is_present field.")
        return

    pending_data = st.session_state.get("pending_attendance_result", {})
    total_enrolled = pending_data.get("total_enrolled", 0)
    total_present = pending_data.get("total_present")
    if total_present is None:
        total_present = int(df["is_present"].fillna(False).sum())
    total_absent = pending_data.get("total_absent")
    if total_absent is None:
        total_absent = max(total_enrolled - total_present, len(df) - total_present)

    st.markdown(f"### Attendance Summary: {subject_name}")
    stat_c1, stat_c2, stat_c3, stat_c4 = st.columns(4)
    stat_c1.metric("Registered", total_enrolled)
    stat_c2.metric("Detected & Present", total_present)
    stat_c3.metric("Marked Absent", total_absent)
    stat_c4.metric(
        "Match Rate",
        f"{(total_present / total_enrolled * 100) if total_enrolled > 0 else 0:.1f}%",
    )

    if total_present == 0 and total_enrolled > 0:
        st.warning(
            "No students were automatically marked present. Please check liveness or recognition threshold."
        )

    if total_enrolled == 0:
        st.warning("No enrolled students were found for this subject. Check subject targets and enrollment sync.")

    st.dataframe(df, hide_index=True, width="stretch")

    override_ids = []
    override_reason = "Manual override"

    eligible = df[df["is_present"] == False]
    if not eligible.empty:
        with st.expander("Manual Correction", expanded=False):
            st.info("Mark any student present who was missed by the AI.")
            override_labels = {
                f"{row['Name']} ({row['ID']})": int(row["ID"])
                for _, row in eligible.iterrows()
            }
            selected_labels = st.multiselect(
                "Mark as Present:",
                options=list(override_labels.keys()),
            )
            override_ids = [override_labels[label] for label in selected_labels]
            override_reason = st.text_input("Reason (Optional)", value=override_reason)

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Discard", width="stretch"):
            st.session_state.voice_attendance_results = None
            st.session_state.pending_attendance_result = None
            st.session_state.attendance_images = []
            st.rerun()

    with col2:
        if st.button("Confirm & Save", width="stretch", type="primary"):
            try:
                df_to_save, logs_to_save = _apply_pending_manual_overrides(
                    df, logs, override_ids, override_reason
                )
                create_attendance(logs_to_save)

                today_date = datetime.now().strftime("%d %b %Y")
                records = df_to_save.to_dict("records")
                subject_id = logs_to_save[0].get("subject_id") if logs_to_save else None
                try:
                    mail_result = dispatch_attendance_emails(
                        records,
                        subject_name=subject_name,
                        subject_id=subject_id,
                        marked_date=today_date,
                    )
                except Exception as mail_error:
                    mail_result = {
                        "queued": 0,
                        "sent_now": 0,
                        "failed_count": 1,
                        "failed": [
                            {
                                "student": "Email automation",
                                "email": "-",
                                "error": str(mail_error),
                            }
                        ],
                        "skipped": 0,
                    }

                try:
                    low_alerts = _queue_low_attendance_alerts(logs_to_save, subject_name)
                    notify_low_attendance_bg(low_alerts)
                except Exception as alert_error:
                    st.warning(f"Low attendance alert check failed: {alert_error}")
                st.success(
                    "Attendance saved. "
                    f"{mail_result['sent_now']} absent-student follow-up email(s) sent. "
                    f"{mail_result['queued']} present-attendance email(s) started."
                )
                if mail_result.get("failed_count"):
                    failed_preview = "; ".join(
                        f"{item['student']} ({item['email']}): {item['error']}"
                        for item in mail_result.get("failed", [])[:3]
                    )
                    st.error(
                        "Some absent-student emails failed. "
                        f"{failed_preview}"
                    )
                if mail_result["skipped"]:
                    st.warning(
                        f"{mail_result['skipped']} student(s) skipped because email/student ID is missing."
                    )

                st.session_state.attendance_images = []
                st.session_state.attendance_photo_meta = []
                st.session_state.voice_attendance_results = None
                st.session_state.pending_attendance_result = None
                time.sleep(1)
                st.rerun()

            except Exception as e:
                st.error(f"Sync failed! Error: {e}")


# Use: Handles attendance result dialog behavior in this module.
# Linked with: Streamlit UI, decorators, tests, or external runtime calls.
@st.dialog("Attendance Reports")
def attendance_result_dialog(df, logs, subject_name="Selected Subject"):
    show_attendance_result(df, logs, subject_name)
