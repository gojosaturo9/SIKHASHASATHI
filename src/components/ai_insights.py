from datetime import date, datetime, timedelta
from io import StringIO

import pandas as pd
import streamlit as st
from google import genai
from google.genai import types

from src.database.config import supabase


ATTENDANCE_TABLE_CANDIDATES = ("attendance", "attendance_logs")
MIN_ATTENDANCE_ROWS_FOR_TRENDS = 8


def _to_iso_start(day: date) -> str:
    return f"{day.isoformat()}T00:00:00"


def _get_secret(*names):
    for name in names:
        value = st.secrets.get(name)
        if value:
            return value
    return None


def _execute_attendance_query(table_name, start_iso):
    select_with_joins = (
        "timestamp, created_at, date, is_present, status, student_id, subject_id, "
        "students(student_id, name, enrollment_no, branch, semester, section), "
        "subjects(name, subject_code)"
    )
    try:
        return (
            supabase.table(table_name)
            .select(select_with_joins)
            .gte("timestamp", start_iso)
            .order("timestamp", desc=False)
            .execute()
            .data
        )
    except Exception:
        try:
            return (
                supabase.table(table_name)
                .select(select_with_joins)
                .gte("created_at", start_iso)
                .order("created_at", desc=False)
                .execute()
                .data
            )
        except Exception:
            return supabase.table(table_name).select("*").execute().data


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


def _fetch_current_week_feedback(start_day):
    start_iso = _to_iso_start(start_day)
    try:
        try:
            return (
                supabase.table("feedback")
                .select("*")
                .gte("created_at", start_iso)
                .order("created_at", desc=False)
                .execute()
                .data
                or []
            )
        except Exception:
            try:
                return (
                    supabase.table("feedback")
                    .select("*")
                    .gte("timestamp", start_iso)
                    .order("timestamp", desc=False)
                    .execute()
                    .data
                    or []
                )
            except Exception:
                return (
                    supabase.table("feedback")
                    .select("*")
                    .gte("date", start_day.isoformat())
                    .execute()
                    .data
                    or []
                )
    except Exception:
        return []


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


def _is_present(row):
    if "is_present" in row:
        return bool(row.get("is_present"))

    status = str(row.get("status", "")).lower()
    return status in {"present", "p", "true", "1", "yes"}


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


def _csv_text(name, rows_or_df):
    if isinstance(rows_or_df, pd.DataFrame):
        df = rows_or_df.copy()
    else:
        df = pd.DataFrame(rows_or_df)

    if df.empty:
        return f"{name}\n(no rows)\n"

    buffer = StringIO()
    df.to_csv(buffer, index=False)
    return f"{name}\n{buffer.getvalue()}"


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


def _build_prompt(attendance_csv, feedback_csv, has_enough_data):
    data_instruction = (
        "If the dataset is too small, clearly say: Insufficient data for trend analysis."
        if not has_enough_data
        else "Use the provided CSV data only. Do not invent students, dates, or percentages."
    )

    return f"""
Tu ek Senior Data Analyst hai. Tujhe niche diye gaye attendance data se 4 specific cheezein nikaalni hain:

1. Trend Detection: Pichle hafte vs is hafte ki attendance percentage compare kar.
2. Anomaly Detection (Mass Bunk Alert): Check kar ki kya koi aisa specific din ya time-slot hai jaha attendance achanak se drop hui, especially 20%+ drop.
3. Predictive Warning: Identify kar aise students ko jinki attendance filhal 75% se upar hai par recent absent pattern ki wajah se woh agle 3 din mein 75% se niche gir sakte hain.
4. Executive Summary (Overall Vibe): Principal ke liye 3-4 bullet points mein pure campus ka health report.

Output English mein professional dashboard style mein do.
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


def _generate_ai_analysis(attendance_csv, feedback_csv, has_enough_data):
    api_key = _get_secret("GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_GENAI_API_KEY")
    if not api_key:
        return (
            "Gemini API key missing. Add GEMINI_API_KEY or GOOGLE_API_KEY in "
            ".streamlit/secrets.toml to enable AI analysis."
        )

    system_instruction = (
        "You are a Senior Data Analyst. Analyze attendance and feedback data with "
        "strict numerical discipline. Return concise English insights. If data is "
        "limited, say 'Insufficient data for trend analysis' and avoid guessing."
    )
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model="gemini-1.5-flash",
        contents=_build_prompt(attendance_csv, feedback_csv, has_enough_data),
        config=types.GenerateContentConfig(system_instruction=system_instruction),
    )
    return response.text or "No AI insight returned."


def render_ai_insights():
    st.header("AI Insights Dashboard")
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

    with st.container():
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

        with st.chat_message("assistant"):
            st.markdown(analysis)

        st.session_state["ai_insights_last_result"] = analysis
    elif st.session_state.get("ai_insights_last_result"):
        with st.chat_message("assistant"):
            st.markdown(st.session_state["ai_insights_last_result"])
    else:
        st.info("Click Generate AI Insights to create the latest executive summary.")
