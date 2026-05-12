from datetime import date, datetime, timedelta
from io import StringIO

import pandas as pd
import streamlit as st

from src.database.config import require_supabase
from src.utils.secrets import get_secret


ATTENDANCE_TABLE_CANDIDATES = ("attendance_logs", "attendance")
MIN_ATTENDANCE_ROWS_FOR_TRENDS = 8


# Use: Internal helper for to iso start.
# Linked with: _fetch_attendance_rows, _fetch_current_week_feedback
def _to_iso_start(day: date) -> str:
    return f"{day.isoformat()}T00:00:00"


# Use: Internal helper for execute attendance query.
# Linked with: _fetch_attendance_rows
def _execute_attendance_query(table_name, start_iso):
    select_with_joins = (
        "timestamp, created_at, date, is_present, status, student_id, subject_id, "
        "students(student_id, name, enrollment_no, branch, semester, section), "
        "subjects(name, subject_code)"
    )
    supabase = require_supabase()

    for timestamp_col in ("timestamp", "created_at"):
        try:
            return (
                supabase.table(table_name)
                .select(select_with_joins)
                .gte(timestamp_col, start_iso)
                .order(timestamp_col, desc=False)
                .execute()
                .data
            )
        except Exception:
            continue

    try:
        return (
            supabase.table(table_name)
            .select(select_with_joins)
            .gte("date", start_iso.split("T", 1)[0])
            .order("date", desc=False)
            .execute()
            .data
        )
    except Exception:
        return supabase.table(table_name).select("*").execute().data


# Use: Internal helper for fetch attendance rows.
# Linked with: render_ai_insights
def _fetch_attendance_rows(start_day):
    start_iso = _to_iso_start(start_day)
    last_error = None

    for table_name in ATTENDANCE_TABLE_CANDIDATES:
        try:
            rows = _execute_attendance_query(table_name, start_iso)
            return table_name, rows or []
        except Exception as exc:
            last_error = exc

    raise RuntimeError(f"Could not fetch attendance data: {last_error}")


# Use: Internal helper for fetch current week feedback.
# Linked with: render_ai_insights
def _fetch_current_week_feedback(start_day):
    supabase = require_supabase()
    start_iso = _to_iso_start(start_day)

    for timestamp_col, value in (
        ("created_at", start_iso),
        ("timestamp", start_iso),
        ("date", start_day.isoformat()),
    ):
        try:
            return (
                supabase.table("feedback")
                .select("*")
                .gte(timestamp_col, value)
                .order(timestamp_col, desc=False)
                .execute()
                .data
                or []
            )
        except Exception:
            continue
    return []


# Use: Internal helper for parse timestamp.
# Linked with: _normalize_attendance
def _parse_timestamp(value):
    if not value:
        return None

    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        try:
            return datetime.strptime(str(value), "%Y-%m-%d")
        except ValueError:
            return None


# Use: Internal helper for is present.
# Linked with: _normalize_attendance
def _is_present(row):
    if "is_present" in row:
        return bool(row.get("is_present"))

    status = str(row.get("status", "")).lower()
    return status in {"present", "p", "true", "1", "yes"}


# Use: Internal helper for normalize attendance.
# Linked with: render_ai_insights
def _normalize_attendance(rows):
    normalized = []
    for row in rows:
        student = row.get("students") or {}
        subject = row.get("subjects") or {}
        raw_ts = row.get("timestamp") or row.get("created_at") or row.get("date")
        parsed_ts = _parse_timestamp(raw_ts)
        present = _is_present(row)

        normalized.append(
            {
                "date": parsed_ts.date().isoformat() if parsed_ts else str(raw_ts or ""),
                "time": parsed_ts.strftime("%H:%M") if parsed_ts else "",
                "student_id": row.get("student_id") or student.get("student_id"),
                "student_name": student.get("name") or row.get("student_name") or "",
                "enrollment_no": student.get("enrollment_no") or row.get("enrollment_no") or "",
                "branch": student.get("branch") or row.get("branch") or "",
                "semester": student.get("semester") or row.get("semester") or "",
                "section": student.get("section") or row.get("section") or "",
                "subject_id": row.get("subject_id"),
                "subject": subject.get("name") or row.get("subject") or row.get("subject_name") or "",
                "status": "present" if present else "absent",
                "is_present": present,
            }
        )

    df = pd.DataFrame(normalized)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
        df = df.dropna(subset=["date"])
    return df


# Use: Internal helper for csv text.
# Linked with: render_ai_insights
def _csv_text(name, rows_or_df):
    df = rows_or_df.copy() if isinstance(rows_or_df, pd.DataFrame) else pd.DataFrame(rows_or_df)
    if df.empty:
        return f"{name}\n(no rows)\n"

    buffer = StringIO()
    df.to_csv(buffer, index=False)
    return f"{name}\n{buffer.getvalue()}"


# Use: Internal helper for compute metrics.
# Linked with: render_ai_insights
def _compute_metrics(df):
    if df.empty:
        return {
            "total_records": 0,
            "avg_attendance": 0.0,
            "student_count": 0,
            "session_count": 0,
            "trend_delta": 0.0,
        }

    today = date.today()
    current_week_start = today - timedelta(days=today.weekday())
    previous_week_start = current_week_start - timedelta(days=7)
    previous_week_end = current_week_start - timedelta(days=1)

    this_week = df[df["date"] >= current_week_start]
    last_week = df[(df["date"] >= previous_week_start) & (df["date"] <= previous_week_end)]

    this_week_pct = this_week["is_present"].mean() * 100 if not this_week.empty else 0.0
    last_week_pct = last_week["is_present"].mean() * 100 if not last_week.empty else 0.0

    return {
        "total_records": len(df),
        "avg_attendance": df["is_present"].mean() * 100,
        "student_count": df["student_id"].nunique() if "student_id" in df else 0,
        "session_count": df[["date", "time", "subject"]].drop_duplicates().shape[0],
        "trend_delta": this_week_pct - last_week_pct,
    }


# Use: Internal helper for detect mass bunk.
# Linked with: render_ai_insights
def _detect_mass_bunk(df):
    if df.empty or len(df) < MIN_ATTENDANCE_ROWS_FOR_TRENDS:
        return None

    session_cols = ["date", "time", "subject"]
    sessions = (
        df.groupby(session_cols, dropna=False)
        .agg(attendance_pct=("is_present", "mean"), total=("is_present", "count"))
        .reset_index()
    )
    sessions["attendance_pct"] = sessions["attendance_pct"] * 100

    if len(sessions) < 2:
        return None

    baseline = sessions["attendance_pct"].median()
    sessions["drop"] = baseline - sessions["attendance_pct"]
    candidate = sessions.sort_values("drop", ascending=False).iloc[0]

    if candidate["drop"] >= 20 and candidate["total"] >= 3:
        return {
            "date": candidate["date"],
            "time": candidate["time"] or "N/A",
            "subject": candidate["subject"] or "N/A",
            "attendance_pct": round(float(candidate["attendance_pct"]), 1),
            "drop": round(float(candidate["drop"]), 1),
        }
    return None


# Use: Internal helper for build prompt.
# Linked with: GeminiChatClient.answer, _generate_ai_analysis
def _build_prompt(attendance_csv, feedback_csv, has_enough_data):
    data_instruction = (
        "If the dataset is too small, clearly say: Insufficient data for trend analysis."
        if not has_enough_data
        else "Use the provided CSV data only. Do not invent students, dates, or percentages."
    )

    return f"""
You are a senior data analyst. Analyze the attendance and feedback CSVs and return:

1. Trend Detection: Compare last week vs this week attendance percentage.
2. Anomaly Detection: Detect a mass bunk or unusual attendance drop, especially 20%+.
3. Predictive Warning: Identify students who may fall below 75% soon.
4. Executive Summary: 3-4 concise bullets for leadership.

Use these exact headings:
Trend Detection
Anomaly Detection
Predictive Warning
Executive Summary

{data_instruction}

Attendance CSV:
{attendance_csv}

Current Week Feedback CSV:
{feedback_csv}
""".strip()


# Use: Internal helper for generate ai analysis.
# Linked with: render_ai_insights
def _generate_ai_analysis(attendance_csv, feedback_csv, has_enough_data):
    api_key = get_secret("GEMINI_API_KEY") or get_secret("GOOGLE_API_KEY")
    if not api_key:
        return (
            "Gemini API key missing. Add GEMINI_API_KEY in "
            ".streamlit/secrets.toml to enable AI Insights."
        )

    import google.generativeai as genai

    genai.configure(api_key=api_key)
    model_name = get_secret("GEMINI_MODEL", "gemini-2.0-flash")
    model = genai.GenerativeModel(
        model_name,
        system_instruction=(
            "You are a senior attendance data analyst. Use only supplied data. "
            "Return concise, numerically disciplined insights."
        ),
    )
    response = model.generate_content(
        _build_prompt(attendance_csv, feedback_csv, has_enough_data)
    )
    return response.text or "No AI insight returned."


# Use: Renders the ai insights UI section.
# Linked with: admin_dashboard, teacher_dashboard
def render_ai_insights():
    st.header("AI Insights Dashboard", anchor=False)
    st.caption("Attendance and feedback patterns generated from recent campus data.")

    today = date.today()
    fourteen_days_ago = today - timedelta(days=14)
    current_week_start = today - timedelta(days=today.weekday())

    try:
        attendance_table, attendance_rows = _fetch_attendance_rows(fourteen_days_ago)
        feedback_rows = _fetch_current_week_feedback(current_week_start)
    except Exception as exc:
        st.error(f"Could not load AI insights data: {exc}")
        return

    attendance_df = _normalize_attendance(attendance_rows)
    metrics = _compute_metrics(attendance_df)
    has_enough_data = metrics["total_records"] >= MIN_ATTENDANCE_ROWS_FOR_TRENDS

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Records Analyzed", metrics["total_records"])
    c2.metric("Avg Attendance", f"{metrics['avg_attendance']:.1f}%")
    c3.metric("Students Covered", metrics["student_count"])
    c4.metric("Week Trend", f"{metrics['trend_delta']:+.1f}%")

    st.caption(f"Source: Supabase table `{attendance_table}` | Window: last 14 days")

    anomaly = _detect_mass_bunk(attendance_df)
    if anomaly:
        st.error(
            "Mass bunk alert: "
            f"{anomaly['subject']} on {anomaly['date']} at {anomaly['time']} "
            f"dropped by {anomaly['drop']} points. Attendance was {anomaly['attendance_pct']}%."
        )

    if not has_enough_data:
        st.info("Insufficient data for trend analysis. More attendance sessions are needed.")

    attendance_csv = _csv_text("attendance_last_14_days", attendance_df)
    feedback_csv = _csv_text("feedback_current_week", feedback_rows)

    if st.button("Generate AI Insights", type="primary", icon=":material/auto_awesome:"):
        with st.spinner("Gemini is analyzing recent attendance and feedback..."):
            try:
                analysis = _generate_ai_analysis(
                    attendance_csv, feedback_csv, has_enough_data
                )
            except Exception as exc:
                st.error(f"AI analysis failed: {exc}")
                return

        st.session_state["ai_insights_last_result"] = analysis

    if st.session_state.get("ai_insights_last_result"):
        with st.chat_message("assistant"):
            st.markdown(st.session_state["ai_insights_last_result"])
    else:
        st.info("Click Generate AI Insights to create the latest executive summary.")
