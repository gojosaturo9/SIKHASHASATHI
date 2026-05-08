import json
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

import streamlit as st
from google import genai
from google.genai import types

from src.database.config import supabase


GEMINI_API_KEY = (
    st.secrets.get("GEMINI_API_KEY")
    or st.secrets.get("GOOGLE_API_KEY")
    or st.secrets.get("GOOGLE_GENAI_API_KEY")
)
gemini_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None
LOCAL_TIMEZONE = ZoneInfo("Asia/Kolkata")

SENTIMENTS = {
    "Positive": {
        "emoji": "\U0001f60a",
        "color": "#16a34a",
        "bg": "#dcfce7",
        "tone": "Teacher reaction: confident and encouraged",
    },
    "Neutral": {
        "emoji": "\U0001f610",
        "color": "#ca8a04",
        "bg": "#fef9c3",
        "tone": "Teacher reaction: steady, needs observation",
    },
    "Negative": {
        "emoji": "\U0001f61f",
        "color": "#dc2626",
        "bg": "#fee2e2",
        "tone": "Teacher reaction: needs attention",
    },
}


def _extract_json(text):
    clean_text = (text or "").strip()
    if clean_text.startswith("```"):
        clean_text = clean_text.strip("`").replace("json", "", 1).strip()

    start = clean_text.find("{")
    end = clean_text.rfind("}")
    if start != -1 and end != -1:
        clean_text = clean_text[start : end + 1]

    return json.loads(clean_text)


def analyze_sentiment(feedback_text):
    prompt = f"""
You are an Educational Data Analyst reviewing post-lecture student feedback.

Analyze the feedback and return strictly one JSON object with exactly these keys:
{{
  "label": "Positive",
  "score": 0.95,
  "themes": ["Good Examples", "Fast Pace"]
}}

Rules:
- label must be exactly one of: Positive, Neutral, Negative.
- score must be a float from 0.0 to 1.0.
- themes must be a list of 1 to 3 short strings.
- themes should name specific engagement topics mentioned by the student, such as "Fast Pace", "MERN Routing", "Good Examples", "Confusing Demo", or "Needs Practice".
- Return JSON only. No markdown, no explanation.

Feedback:
{feedback_text}
""".strip()

    try:
        if gemini_client is None:
            raise RuntimeError("Missing GEMINI_API_KEY or GOOGLE_API_KEY in st.secrets.")

        response = gemini_client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2,
            ),
        )
        result = _extract_json(response.text)
        label = result.get("label", "Neutral")
        score = float(result.get("score", 0.0))
        themes = _normalize_themes(result.get("themes"))

        if label not in {"Positive", "Neutral", "Negative"}:
            label = "Neutral"

        return {
            "label": label,
            "score": max(0.0, min(score, 1.0)),
            "themes": themes,
        }
    except Exception as exc:
        st.error(f"Sentiment analysis failed: {exc}")
        return {"label": "Neutral", "score": 0.0, "themes": ["General Feedback"]}


def _normalize_themes(raw_themes):
    if isinstance(raw_themes, str):
        try:
            parsed = json.loads(raw_themes)
            raw_themes = parsed if isinstance(parsed, list) else [raw_themes]
        except json.JSONDecodeError:
            raw_themes = [item.strip() for item in raw_themes.split(",")]

    if not isinstance(raw_themes, list):
        raw_themes = []

    themes = []
    for theme in raw_themes:
        theme_text = str(theme).strip()
        if theme_text and theme_text not in themes:
            themes.append(theme_text[:40])

    return themes[:3] or ["General Feedback"]


def _is_missing_column_error(exc, column_name):
    message = str(exc)
    return "PGRST204" in message and column_name in message


def _get_subject_id_by_name(subject_name):
    if not subject_name:
        return None

    try:
        rows = (
            supabase.table("subjects")
            .select("subject_id")
            .eq("name", subject_name)
            .limit(1)
            .execute()
            .data
            or []
        )
        return rows[0]["subject_id"] if rows else None
    except Exception:
        return None


def _subject_options(subjects):
    options = {}
    for item in subjects or []:
        subject = item.get("subjects", item)
        subject_id = subject.get("subject_id")
        if not subject_id:
            continue

        label = subject.get("name", "Subject")
        code = subject.get("subject_code")
        if code:
            label = f"{label} - {code}"

        options[label] = subject_id
    return options


def render_feedback_ui(
    current_student_id,
    current_subject_name=None,
    subjects=None,
    selected_subject_id=None,
    selected_subject_name=None,
    show_header=True,
    show_success=True,
    conversation_mode=False,
):
    if show_header:
        st.subheader("Post-Lecture Feedback")
        st.caption(
            "Select the lecture subject and share feedback. Teachers and Admin can review it subject-wise."
        )
    if show_success:
        st.success("Attendance marked successfully.")

    with st.container(border=True):
        if isinstance(current_subject_name, list) and subjects is None:
            subjects = current_subject_name
            current_subject_name = selected_subject_name

        student_id = current_student_id
        subject_choices = _subject_options(subjects)
        selected_subject_id = selected_subject_id
        subject_key_suffix = selected_subject_id or "all"

        if conversation_mode:
            title = selected_subject_name or "Selected Subject"
            st.markdown(f"#### Give Feedback: {title}")
            st.caption("This feedback goes to the teacher and Admin subject-wise.")

        if subject_choices:
            reverse_subjects = {
                subject_id: label for label, subject_id in subject_choices.items()
            }
            if selected_subject_id:
                selected_subject_label = reverse_subjects.get(
                    selected_subject_id, selected_subject_name or "Selected Subject"
                )
                selected_subject_name = selected_subject_name or selected_subject_label.split(
                    " - ", 1
                )[0]
                st.text_input(
                    "Lecture subject",
                    value=selected_subject_label,
                    disabled=True,
                    key=f"lecture_feedback_subject_locked_{student_id}_{subject_key_suffix}",
                )
            else:
                selected_subject_label = st.selectbox(
                    "Lecture subject",
                    list(subject_choices.keys()),
                    key=f"lecture_feedback_subject_{student_id}",
                )
                selected_subject_id = subject_choices[selected_subject_label]
                subject_key_suffix = selected_subject_id
                selected_subject_name = selected_subject_label.split(" - ", 1)[0]
        else:
            selected_subject_name = selected_subject_name or current_subject_name
            if selected_subject_name:
                st.text_input(
                    "Lecture subject",
                    value=selected_subject_name,
                    disabled=True,
                    key=f"lecture_feedback_subject_name_{student_id}_{subject_key_suffix}",
                )
            else:
                st.info("Enroll in a subject before submitting subject-wise feedback.")

        if conversation_mode:
            feedback_text = st.text_area(
                "Your feedback",
                placeholder="What went well? What was confusing? What should improve?",
                key=f"lecture_feedback_chat_text_{student_id}_{subject_key_suffix}",
                height=96,
            )
            should_submit = st.button(
                "Send Feedback",
                type="primary",
                icon=":material/send:",
                key=f"submit_feedback_chat_{student_id}_{subject_key_suffix}",
            )
        else:
            feedback_text = st.text_area(
                "Optional lecture feedback",
                placeholder="Share what worked well or what felt confusing in today's lecture.",
                key=f"lecture_feedback_{student_id}_{subject_key_suffix}",
                height=120,
            )
            should_submit = st.button(
                "Submit Feedback",
                type="primary",
                icon=":material/send:",
                key=f"submit_feedback_{student_id}_{subject_key_suffix}",
            )

        if should_submit:
            subject_name = selected_subject_name or current_subject_name
            if not subject_name:
                st.warning("Please select a subject before submitting feedback.")
                return

            if not feedback_text.strip():
                st.info("Feedback is optional. Write a short note before submitting.")
                return

            sentiment = analyze_sentiment(feedback_text)
            row = {
                "student_id": student_id,
                "subject_name": subject_name,
                "raw_text": feedback_text.strip(),
                "sentiment": sentiment["label"],
                "confidence_score": sentiment["score"],
                "themes": sentiment["themes"],
            }

            try:
                try:
                    supabase.table("feedback").insert(row).execute()
                except Exception as exc:
                    if not (
                        _is_missing_column_error(exc, "subject_name")
                        or _is_missing_column_error(exc, "themes")
                    ):
                        raise

                    legacy_row = {
                        "student_id": student_id,
                        "subject_id": selected_subject_id
                        or _get_subject_id_by_name(subject_name),
                        "raw_text": feedback_text.strip(),
                        "sentiment": sentiment["label"],
                        "confidence_score": sentiment["score"],
                    }
                    supabase.table("feedback").insert(legacy_row).execute()

                if conversation_mode:
                    st.success(
                        f"Saved as {sentiment['label']} with {sentiment['score']:.2f} confidence."
                    )
                st.toast("Feedback submitted successfully.")
            except Exception as exc:
                st.error(f"Could not save feedback: {exc}")


def _base_feedback_select():
    return "student_id, subject_name, themes, sentiment, confidence_score, raw_text, created_at"


def _legacy_feedback_select():
    return "student_id, subject_id, sentiment, confidence_score, raw_text, created_at"


def _enrich_feedback_rows(rows):
    subject_ids = sorted(
        {
            row.get("subject_id")
            for row in rows
            if row.get("subject_id") is not None
        }
    )
    subject_names = sorted(
        {
            row.get("subject_name")
            for row in rows
            if row.get("subject_name") is not None
        }
    )
    if not subject_names and not subject_ids:
        return rows

    try:
        query = supabase.table("subjects").select(
            "subject_id, name, subject_code, teacher_id"
        )
        if subject_names:
            subjects = query.in_("name", subject_names).execute().data or []
        else:
            subjects = query.in_("subject_id", subject_ids).execute().data or []
    except Exception:
        subjects = []

    teacher_ids = sorted(
        {
            subject.get("teacher_id")
            for subject in subjects
            if subject.get("teacher_id") is not None
        }
    )
    if teacher_ids:
        try:
            teachers = (
                supabase.table("teachers")
                .select("teacher_id, name, username")
                .in_("teacher_id", teacher_ids)
                .execute()
                .data
                or []
            )
        except Exception:
            teachers = []
    else:
        teachers = []

    teacher_map = {teacher.get("teacher_id"): teacher for teacher in teachers}
    subject_map_by_id = {}
    subject_map_by_name = {}
    for subject in subjects:
        subject["teachers"] = teacher_map.get(subject.get("teacher_id"), {})
        subject_map_by_id[subject.get("subject_id")] = subject
        subject_map_by_name[subject.get("name")] = subject

    for row in rows:
        subject = subject_map_by_name.get(row.get("subject_name")) or subject_map_by_id.get(
            row.get("subject_id")
        )
        row["subjects"] = subject or {}
        if not row.get("subject_name") and subject:
            row["subject_name"] = subject.get("name")
        if "themes" not in row:
            row["themes"] = []
    return rows


def _fetch_todays_feedback(teacher_id=None):
    today = datetime.now(LOCAL_TIMEZONE).date()
    start_local = datetime.combine(today, time.min, tzinfo=LOCAL_TIMEZONE)
    end_local = datetime.combine(today, time.max, tzinfo=LOCAL_TIMEZONE)
    start_utc = start_local.astimezone(timezone.utc).isoformat()
    end_utc = end_local.astimezone(timezone.utc).isoformat()

    try:
        rows = (
            supabase.table("feedback")
            .select(_base_feedback_select())
            .gte("created_at", start_utc)
            .lte("created_at", end_utc)
            .execute()
            .data
            or []
        )
        rows = _enrich_feedback_rows(rows)
        if teacher_id is not None:
            rows = [
                row
                for row in rows
                if (row.get("subjects") or {}).get("teacher_id") == teacher_id
            ]
        return rows
    except Exception:
        try:
            rows = (
                supabase.table("feedback")
                .select(_legacy_feedback_select())
                .gte("created_at", start_utc)
                .lte("created_at", end_utc)
                .execute()
                .data
                or []
            )
            rows = _enrich_feedback_rows(rows)
            if teacher_id is not None:
                rows = [
                    row
                    for row in rows
                    if (row.get("subjects") or {}).get("teacher_id") == teacher_id
                ]
            return rows
        except Exception as exc:
            st.error(f"Could not load today's feedback: {exc}")
            return []


def _render_sentiment_metrics(feedback_rows):
    counts = {label: 0 for label in SENTIMENTS}
    for row in feedback_rows:
        sentiment = row.get("sentiment")
        if sentiment in counts:
            counts[sentiment] += 1

    cols = st.columns(3)
    for col, label in zip(cols, ["Positive", "Neutral", "Negative"]):
        meta = SENTIMENTS[label]
        col.markdown(
            f"""
            <div style="
                background:{meta['bg']};
                border:1px solid {meta['color']}33;
                border-left:6px solid {meta['color']};
                border-radius:8px;
                padding:14px 16px;
                min-height:92px;">
                <div style="font-size:1.8rem; line-height:1;">{meta['emoji']}</div>
                <div style="color:{meta['color']}; font-weight:700; margin-top:8px;">{label}</div>
                <div style="font-size:1.7rem; font-weight:800; color:#111827;">{counts[label]}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    strongest = max(counts, key=counts.get) if feedback_rows else "Neutral"
    st.caption(SENTIMENTS[strongest]["tone"])
    return counts


def _engagement_score(counts):
    total = sum(counts.values())
    if total == 0:
        return 0

    weighted_score = (
        counts["Positive"] * 100
        + counts["Neutral"] * 60
        + counts["Negative"] * 25
    )
    return round(weighted_score / total)


def render_subject_feedback_summary(subject_id, teacher_id=None, subject_name=None):
    feedback_rows = _fetch_todays_feedback(teacher_id=teacher_id)
    feedback_rows = [
        row
        for row in feedback_rows
        if row.get("subject_name") == subject_name
        or (row.get("subjects") or {}).get("subject_id") == subject_id
    ]

    st.markdown(f"#### Feedback Pulse{f' - {subject_name}' if subject_name else ''}")
    counts = _render_sentiment_metrics(feedback_rows)
    engagement = _engagement_score(counts)

    meter_col, note_col = st.columns([1, 2], vertical_alignment="center")
    with meter_col:
        st.metric("Student Engagement", f"{engagement}%")
    with note_col:
        st.progress(engagement / 100 if engagement else 0)
        if engagement >= 75:
            st.success("Strong engagement for this subject.")
        elif engagement >= 45:
            st.info("Mixed engagement. Review neutral feedback.")
        else:
            st.warning("Low engagement. Negative feedback needs attention.")

    if not feedback_rows:
        st.info("No feedback submitted for this subject today.")
        return

    st.dataframe(_rows_to_feedback_table(feedback_rows), width="stretch", hide_index=True)


def render_teacher_feedback_overview(teacher_id):
    feedback_rows = _fetch_todays_feedback(teacher_id=teacher_id)

    with st.container(border=True):
        st.subheader("Today's Feedback Overview")
        st.caption("Live sentiment summary from student feedback across your subjects.")
        counts = _render_sentiment_metrics(feedback_rows)
        engagement = _engagement_score(counts)

        metric_col, meter_col = st.columns([1, 3], vertical_alignment="center")
        with metric_col:
            st.metric("Overall Engagement", f"{engagement}%")
        with meter_col:
            st.progress(engagement / 100 if engagement else 0)

        if not feedback_rows:
            st.info("No student feedback submitted today yet.")


def _fetch_feedback_for_subject(subject_name):
    if not subject_name:
        return []

    try:
        rows = (
            supabase.table("feedback")
            .select(_base_feedback_select())
            .eq("subject_name", subject_name)
            .order("created_at", desc=True)
            .execute()
            .data
            or []
        )
        return rows
    except Exception as exc:
        if not _is_missing_column_error(exc, "subject_name"):
            st.error(f"Could not load feedback for {subject_name}: {exc}")
            return []

    try:
        subject = (
            supabase.table("subjects")
            .select("subject_id")
            .eq("name", subject_name)
            .limit(1)
            .execute()
            .data
            or []
        )
        if not subject:
            return []

        rows = (
            supabase.table("feedback")
            .select(_legacy_feedback_select())
            .eq("subject_id", subject[0]["subject_id"])
            .order("created_at", desc=True)
            .execute()
            .data
            or []
        )
        return rows
    except Exception as exc:
        st.error(f"Could not load feedback for {subject_name}: {exc}")
        return []


def _sentiment_counts(feedback_rows):
    counts = {label: 0 for label in SENTIMENTS}
    for row in feedback_rows:
        sentiment = row.get("sentiment")
        if sentiment in counts:
            counts[sentiment] += 1
    return counts


def _theme_counts(feedback_rows):
    counts = {}
    for row in feedback_rows:
        for theme in _normalize_themes(row.get("themes")):
            counts[theme] = counts.get(theme, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _render_theme_tags(theme_counts):
    if not theme_counts:
        st.info("No engagement themes found for this subject yet.")
        return

    tags = " ".join(
        f"<span style='display:inline-block;margin:0 8px 8px 0;padding:6px 10px;"
        f"border-radius:999px;background:#eef2ff;color:#3730a3;border:1px solid #c7d2fe;"
        f"font-size:.88rem;font-weight:600;'>{theme} ({count})</span>"
        for theme, count in theme_counts.items()
    )
    st.markdown(tags, unsafe_allow_html=True)


def render_manage_subjects(teacher_id=None, subjects=None):
    st.subheader("Subject Feedback")

    subject_names = []
    for subject in subjects or []:
        name = subject.get("name")
        if name and name not in subject_names:
            subject_names.append(name)

    if not subject_names:
        subject_names = ["Web Development", "Data Structures", "Computer Networks"]

    selected_subject = st.selectbox(
        "Select Subject",
        subject_names,
        key=f"manage_subject_feedback_{teacher_id or 'all'}",
    )

    feedback_rows = _fetch_feedback_for_subject(selected_subject)
    feedback_rows = _enrich_feedback_rows(feedback_rows)

    if teacher_id is not None:
        feedback_rows = [
            row
            for row in feedback_rows
            if not (row.get("subjects") or {}).get("teacher_id")
            or (row.get("subjects") or {}).get("teacher_id") == teacher_id
        ]

    counts = _sentiment_counts(feedback_rows)
    metric_cols = st.columns(3)
    metric_cols[0].metric("Total Positive", counts["Positive"])
    metric_cols[1].metric("Total Neutral", counts["Neutral"])
    metric_cols[2].metric("Total Negative", counts["Negative"])

    st.markdown("#### Trending Engagement Themes")
    _render_theme_tags(_theme_counts(feedback_rows))

    st.markdown("#### Student Feedback")
    if not feedback_rows:
        st.info(f"No feedback submitted for {selected_subject} yet.")
        return

    for row in feedback_rows:
        label = row.get("sentiment", "Neutral")
        confidence = float(row.get("confidence_score") or 0)
        themes = ", ".join(_normalize_themes(row.get("themes")))
        st.info(
            f"**{label}** ({confidence:.2f}) | Themes: {themes}\n\n"
            f"{row.get('raw_text', '')}"
        )


def _rows_to_feedback_table(feedback_rows):
    table_rows = []
    for row in feedback_rows:
        subject = row.get("subjects") or {}
        teacher = subject.get("teachers") or {}
        subject_name = subject.get("name") or row.get("subject_name") or "Unknown"
        subject_code = subject.get("subject_code")
        if subject_code:
            subject_name = f"{subject_name} ({subject_code})"

        table_rows.append(
            {
                "Subject": subject_name,
                "Teacher": teacher.get("name") or teacher.get("username") or "Unknown",
                "Sentiment": row.get("sentiment", "Neutral"),
                "Confidence": row.get("confidence_score", 0),
                "Themes": ", ".join(_normalize_themes(row.get("themes"))),
                "Feedback": row.get("raw_text", ""),
                "Submitted At": row.get("created_at", ""),
            }
        )
    return table_rows


def render_teacher_analytics(teacher_id=None):
    st.subheader("Class Vibe")

    feedback_rows = _fetch_todays_feedback(teacher_id=teacher_id)
    subject_labels = sorted(
        {
            (row.get("subjects") or {}).get("name")
            for row in feedback_rows
            if (row.get("subjects") or {}).get("name")
        }
    )

    if subject_labels:
        selected_subject = st.selectbox(
            "Subject filter",
            ["All Subjects"] + subject_labels,
            key=f"teacher_feedback_subject_{teacher_id or 'all'}",
        )
        if selected_subject != "All Subjects":
            feedback_rows = [
                row
                for row in feedback_rows
                if (row.get("subjects") or {}).get("name") == selected_subject
            ]

    _render_sentiment_metrics(feedback_rows)

    if not feedback_rows:
        st.info("No feedback submitted today yet.")
        return

    st.dataframe(_rows_to_feedback_table(feedback_rows), width="stretch", hide_index=True)


def render_admin_feedback_analytics():
    st.header("Subject-wise Feedback Sentiment")

    feedback_rows = _fetch_todays_feedback()
    if not feedback_rows:
        st.info("No feedback submitted today yet.")
        return

    teacher_labels = sorted(
        {
            ((row.get("subjects") or {}).get("teachers") or {}).get("name")
            or ((row.get("subjects") or {}).get("teachers") or {}).get("username")
            for row in feedback_rows
            if (row.get("subjects") or {}).get("teachers")
        }
    )
    subject_labels = sorted(
        {
            (row.get("subjects") or {}).get("name")
            for row in feedback_rows
            if (row.get("subjects") or {}).get("name")
        }
    )

    teacher_col, subject_col = st.columns(2)
    with teacher_col:
        selected_teacher = st.selectbox(
            "Teacher",
            ["All Teachers"] + teacher_labels,
            key="admin_feedback_teacher",
        )
    with subject_col:
        selected_subject = st.selectbox(
            "Subject",
            ["All Subjects"] + subject_labels,
            key="admin_feedback_subject",
        )

    filtered_rows = feedback_rows
    if selected_teacher != "All Teachers":
        filtered_rows = [
            row
            for row in filtered_rows
            if (
                ((row.get("subjects") or {}).get("teachers") or {}).get("name")
                or ((row.get("subjects") or {}).get("teachers") or {}).get("username")
            )
            == selected_teacher
        ]
    if selected_subject != "All Subjects":
        filtered_rows = [
            row
            for row in filtered_rows
            if (row.get("subjects") or {}).get("name") == selected_subject
        ]

    _render_sentiment_metrics(filtered_rows)
    st.dataframe(_rows_to_feedback_table(filtered_rows), width="stretch", hide_index=True)
