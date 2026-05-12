import streamlit as st

from src.ui.base_layout import style_background_dashboard, style_base_layout
from src.database.config import is_supabase_configured, render_supabase_setup

from src.components.header import header_dashboard
from src.components.footer import footer_dashboard

from PIL import Image
import numpy as np
import time

from src.pipelines.face_pipeline import (
    FacePipelineSetupError,
    get_face_profile_count,
    predict_attendance,
    get_face_embeddings,
    train_classifier,
)
from src.pipelines.voice_pipeline import get_voice_embedding

# ✅ FIX 1: DB functions cache ke saath (30 sec cache — DB calls instant honge)
from src.database.db import (
    get_all_students as _get_all_students,
    cleanup_old_feedback,
    create_student,
    create_subject_feedback,
    delete_subject_feedback,
    feedback_table_available,
    get_student_feedback as _get_student_feedback,
    get_student_subjects as _get_student_subjects,
    get_student_attendance as _get_student_attendance,
    StudentRegistrationPolicyError,
    update_subject_feedback,
)

# Use: Fetches all students data for the app flow.
# Linked with: get_trained_model, student_screen
@st.cache_data(ttl=30)
def get_all_students():
    return _get_all_students()

# Use: Fetches student subjects data for the app flow.
# Linked with: build_role_context, student_dashboard
@st.cache_data(ttl=30)
def get_student_subjects(student_id):
    return _get_student_subjects(student_id)

# Use: Fetches student attendance data for the app flow.
# Linked with: build_role_context, student_dashboard
@st.cache_data(ttl=30)
def get_student_attendance(student_id):
    return _get_student_attendance(student_id)


# Use: Fetches student feedback data for the app flow.
# Linked with: student_dashboard
@st.cache_data(ttl=20)
def get_student_feedback(student_id):
    return _get_student_feedback(student_id)

from src.utils.notifier import notify_student_registration
from src.components.subject_card import subject_card
from src.voice_rag.streamlit_ui import render_voice_rag_chatbot


# Use: Internal helper for finish student login.
# Linked with: student_screen
def _finish_student_login(student):
    """Store the recognized/registered student in Streamlit session state."""
    st.session_state.is_logged_in = True
    st.session_state.user_role = "student"
    st.session_state.student_data = student


# Use: Handles student dashboard behavior in this module.
# Linked with: student_screen
def student_dashboard():
    """Render the logged-in student view: profile, attendance, subjects, feedback, chatbot."""
    student_data = st.session_state.student_data
    student_id = student_data["student_id"]
    cleanup_old_feedback()

    from src.database.db import get_student_leaderboard
    leaderboard = get_student_leaderboard()
    
    # Calculate global attendance stats for theme
    with st.spinner("Calculating your attendance profile.."):
        subjects = get_student_subjects(student_id)
        logs = get_student_attendance(student_id)

    total_classes = len(logs)
    present_classes = sum(1 for log in logs if log.get("is_present"))
    attendance_percent = (
        round((present_classes / total_classes) * 100, 1) if total_classes else 0
    )

    # Apply dynamic background theme
    from src.ui.base_layout import apply_attendance_theme
    apply_attendance_theme(attendance_percent)

    from src.database.db import get_active_announcements
    announcements = get_active_announcements()
    if announcements:
        for ann in announcements:
            icon = "🔔" if ann['category'] == "General" else "📅" if ann['category'] == "Holiday" else "🚨" if ann['category'] == "Urgent" else "🎉"
            st.info(f"{icon} **{ann['title']}**: {ann['content']}")

    c1, c2 = st.columns([4, 1], vertical_alignment="center")
    with c1:
        header_dashboard()
        
        st.markdown(
            f"""
            <div class="ss-welcome-container">
                <h2 style="color: white;">Welcome, {student_data['name']}</h2>
            </div>
            """, 
            unsafe_allow_html=True
        )
    with c2:
        if st.button("Logout", type="secondary", key="logoutbtn", use_container_width=True):
            st.session_state["is_logged_in"] = False
            st.session_state["login_type"] = None
            if "student_data" in st.session_state:
                del st.session_state.student_data
            st.rerun()

    st.write("")

    total_classes = len(logs)
    present_classes = sum(1 for log in logs if log.get("is_present"))
    absent_classes = total_classes - present_classes
    attendance_percent = (
        round((present_classes / total_classes) * 100, 1) if total_classes else 0
    )

    profile_col, summary_col = st.columns([1.2, 1], gap="large")
    with profile_col:
        st.subheader("Your Profile", anchor=False)
        profile_rows = [
            ("Name", student_data.get("name", "-")),
            ("Enrollment No.", student_data.get("enrollment_no", "-")),
            ("Email", student_data.get("email_id", "-")),
            ("Class / Branch", student_data.get("branch", "-")),
            ("Semester", student_data.get("semester", "-")),
            ("Section", student_data.get("section", "-")),
        ]
        st.dataframe(
            [{"Field": field, "Value": str(value)} for field, value in profile_rows],
            hide_index=True,
            use_container_width=True,
        )

    with summary_col:
        st.subheader("Attendance Summary", anchor=False)
        m1, m2 = st.columns(2)
        m1.metric("Total Classes", total_classes)
        m2.metric("Present", present_classes)
        m3, m4 = st.columns(2)
        m3.metric("Absent", absent_classes)
        m4.metric("Attendance", f"{attendance_percent}%")

        if total_classes:
            st.progress(min(attendance_percent / 100, 1.0))
            if attendance_percent < 75:
                st.warning("Your attendance is below 75%.")
            else:
                st.success("Your attendance is 75% or above.")

    st.divider()

    st.header("Your Subjects", anchor=False)

    stats_map = {}

    for log in logs:
        sid = log["subject_id"]

        if sid not in stats_map:
            stats_map[sid] = {"total": 0, "attended": 0}

        stats_map[sid]["total"] += 1

        if log.get("is_present"):
            stats_map[sid]["attended"] += 1

    cols = st.columns(3)
    if not subjects:
        st.info(
            "No subjects are assigned yet. Subjects appear automatically when a teacher creates a class for your branch, semester, and section."
        )

    for i, sub_node in enumerate(subjects):
        sub = sub_node["subjects"]
        sid = sub["subject_id"]

        stats = stats_map.get(sid, {"total": 0, "attended": 0})
        absent = stats["total"] - stats["attended"]
        subject_percent = (
            round((stats["attended"] / stats["total"]) * 100, 1)
            if stats["total"]
            else 0
        )

        if sub.get("type") == "class_wise":
            section_text = (
                f"Semester {student_data.get('semester', '-')} | "
                f"Section {student_data.get('section', '-')}"
            )
        else:
            section_text = sub.get("section") or "Open subject"

        with cols[i % 3]:
            subject_card(
                name=sub["name"],
                code=sub["subject_code"],
                section=section_text,
                stats=[
                    ("📅", "Total", stats["total"]),
                    ("✅", "Attended", stats["attended"]),
                    ("❌", "Absent", absent),
                    ("%", "Attendance", f"{subject_percent}%"),
                ],
            )

    st.divider()
    st.header("Subject Feedback & Doubts", anchor=False)

    if not feedback_table_available():
        st.warning(
            "Feedback table missing hai. Supabase SQL Editor me "
            "supabase_feedback_migration.sql run karo, phir app refresh karo."
        )
    elif not subjects:
        st.info("Feedback options will appear once subjects are assigned.")
    else:
        subject_options = {
            f"{node['subjects']['name']} - {node['subjects']['subject_code']}": node["subjects"]
            for node in subjects
            if node.get("subjects")
        }

        with st.form("student_subject_feedback_form"):
            selected_subject_label = st.selectbox("Select Subject", list(subject_options.keys()))
            feedback_type = st.selectbox(
                "Response Type",
                ["Doubt / Question", "Feedback", "What I understood", "What I did not understand"],
            )
            understanding = st.selectbox(
                "Understanding Level",
                ["Understood well", "Partially understood", "Not understood"],
            )
            message = st.text_area(
                "Write your response",
                placeholder="Ask a doubt, raise a question, or explain what you understood.",
                height=120,
            )
            submitted_feedback = st.form_submit_button(
                "Submit to Teacher", type="primary", use_container_width=True
            )

        if submitted_feedback:
            if not message.strip():
                st.warning("Please write your response before submitting.")
            else:
                selected_subject = subject_options[selected_subject_label]
                result = create_subject_feedback(
                    student_id=student_id,
                    subject_id=selected_subject["subject_id"],
                    feedback_type=feedback_type,
                    message=message.strip(),
                    understanding=understanding,
                )
                if result["ok"]:
                    get_student_feedback.clear()
                    st.success("Your response has been sent to the teacher.")
                    time.sleep(0.8)
                    st.rerun()
                else:
                    st.error(result["error"])

        feedback_rows = get_student_feedback(student_id)
        if feedback_rows:
            st.subheader("Your Responses", anchor=False)
            for row in feedback_rows[:8]:
                subject = row.get("subjects") or {}
                title = (
                    f"{subject.get('name', 'Subject')} | "
                    f"{row.get('feedback_type', 'Feedback')} | "
                    f"{row.get('status', 'open').title()}"
                )
                with st.expander(title, expanded=False):
                    st.caption(f"Understanding: {row.get('understanding', '-')}")
                    st.write(row.get("message", ""))
                    if row.get("teacher_reply"):
                        st.success(f"Teacher reply: {row['teacher_reply']}")
                    else:
                        st.info("Teacher reply pending.")

                    edit_key = f"edit_feedback_{row['id']}"
                    if st.toggle("Edit this response", key=edit_key):
                        with st.form(f"edit_feedback_form_{row['id']}"):
                            edited_type = st.selectbox(
                                "Response Type",
                                ["Doubt / Question", "Feedback", "What I understood", "What I did not understand"],
                                index=["Doubt / Question", "Feedback", "What I understood", "What I did not understand"].index(row.get("feedback_type", "Feedback"))
                                if row.get("feedback_type", "Feedback") in ["Doubt / Question", "Feedback", "What I understood", "What I did not understand"]
                                else 1,
                            )
                            edited_understanding = st.selectbox(
                                "Understanding Level",
                                ["Understood well", "Partially understood", "Not understood"],
                                index=["Understood well", "Partially understood", "Not understood"].index(row.get("understanding", "Partially understood"))
                                if row.get("understanding", "Partially understood") in ["Understood well", "Partially understood", "Not understood"]
                                else 1,
                            )
                            edited_message = st.text_area(
                                "Update response",
                                value=row.get("message", ""),
                                height=120,
                            )
                            save_edit = st.form_submit_button("Save Changes", type="primary")

                        if save_edit:
                            result = update_subject_feedback(
                                row["id"],
                                student_id,
                                edited_type,
                                edited_message.strip(),
                                edited_understanding,
                            )
                            if result["ok"]:
                                get_student_feedback.clear()
                                st.success("Feedback updated.")
                                time.sleep(0.5)
                                st.rerun()
                            else:
                                st.error(result["error"])

                    if st.button("Delete Response", key=f"delete_feedback_{row['id']}", type="secondary"):
                        result = delete_subject_feedback(row["id"], student_id)
                        if result["ok"]:
                            get_student_feedback.clear()
                            st.success("Feedback deleted.")
                            time.sleep(0.5)
                            st.rerun()
                        else:
                            st.error(result["error"])
        else:
            st.caption("No doubts or feedback submitted yet.")
    render_voice_rag_chatbot("student")
    footer_dashboard()


# Use: Handles student screen behavior in this module.
# Linked with: main
def student_screen():
    """Render student login and new registration, including face and required voice capture."""
    style_background_dashboard()
    style_base_layout()

    if not is_supabase_configured():
        c1, c2 = st.columns(2, vertical_alignment="center", gap="xxlarge")
        with c1:
            header_dashboard()
        with c2:
            if st.button("Go back to Home", type="secondary", key="loginbackbtn"):
                st.session_state["login_type"] = None
                st.rerun()
        st.header("Student Login", anchor=False)
        render_supabase_setup("Student Portal")
        footer_dashboard()
        return

    if "student_data" in st.session_state:
        student_dashboard()
        return

    c1, c2 = st.columns(2, vertical_alignment="center", gap="xxlarge")
    with c1:
        header_dashboard()
    with c2:
        if st.button(
            "Go back to Home",
            type="secondary",
            key="loginbackbtn",
        ):
            st.session_state["login_type"] = None
            st.rerun()

    st.header("Student Login", anchor=False)
    st.caption("Scan your face to open your dashboard.")
    st.caption(f"Registered face profiles available: {get_face_profile_count()}")

    # Mirror effect for camera
    st.markdown(
        """
    <style>
        [data-testid="stCameraInputButton"] + div video,
        [data-testid="stCameraInput"] video {
            transform: scaleX(-1) !important;
        }
    </style>
    """,
        unsafe_allow_html=True,
    )

    show_registration = False
    photo_source = st.camera_input("Position your face in the center and capture")

    if photo_source:
        st.success("Face captured. Matching now...")
        img = np.array(Image.open(photo_source))

        with st.spinner("AI is scanning.."):
            try:
                train_classifier()
                detected, all_ids, num_faces = predict_attendance(img)
            except FacePipelineSetupError as e:
                st.error(str(e))
                footer_dashboard()
                return

            if num_faces == 0:
                st.warning("Face not found!")
            elif num_faces > 1:
                st.warning(
                    "Multiple faces found! Please ensure only one person is in the frame."
                )
            else:
                if detected:
                    student_id = list(detected.keys())[0]
                    all_students = get_all_students()
                    student = next(
                        (s for s in all_students if s["student_id"] == student_id),
                        None
                    )
                    if student:
                        _finish_student_login(student)
                        st.toast(f"Welcome Back {student['name']}! 👋")
                        time.sleep(1)
                        st.rerun()
                else:
                    if not all_ids:
                        st.warning(
                            "Database me koi usable face profile nahi mila. Student ko New student registration se face profile create karni hogi."
                        )
                    else:
                        st.info(
                            "Face not recognized. If you are a new student, complete registration below."
                        )
                    show_registration = True

    # --- REGISTRATION SECTION ---
    with st.expander("New student registration", expanded=show_registration):
        if photo_source is None:
            st.info("Capture your live face photo above before creating an account.")
        else:
            st.header("Register New Profile", anchor=False)
            st.caption('Record your voice saying "I am present" to create your voice profile.')
            voice_source = st.audio_input("Record your voice for registration")

            # ✅ FIX 2: st.form wrap — sirf Submit pe rerun hoga, typing smooth rahegi
            with st.form("registration_form"):

                # --- Personal Info ---
                new_name = st.text_input(
                    "Enter your full name", placeholder="E.g., Ayush Kumar"
                )
                new_email = st.text_input(
                    "Enter your email", placeholder="E.g., ayush@college.edu"
                )
                new_enrollment = st.text_input(
                    "Enter Enrollment No.", placeholder="E.g., CS2024001"
                )

                st.divider()

                # --- Academic Info ---
                st.subheader("Academic Details", anchor=False)
                col1, col2, col3 = st.columns(3)
                with col1:
                    new_class = st.selectbox(
                        "Class / Branch",
                        [
                            "Computer Science",
                            "Information Tech",
                            "ECE",
                            "Mechanical",
                            "Civil",
                            "AI/ML",
                            "AI/DS",
                            "DS",
                        ],
                    )
                with col2:
                    new_semester = st.selectbox("Semester", [1, 2, 3, 4, 5, 6, 7, 8])
                with col3:
                    new_section = st.selectbox("Section", ["A", "B", "C", "D", "None"])

                st.divider()

                # --- Submit Button ---
                submitted = st.form_submit_button(
                    "Create Account", type="primary", use_container_width=True
                )

            # Form submit logic (form ke bahar)
            if submitted:
                if new_name and new_email and new_enrollment and voice_source is not None:
                    with st.spinner("Creating your profile and encoding biometrics..."):
                        img = np.array(Image.open(photo_source))
                        try:
                            encodings = get_face_embeddings(img)
                        except FacePipelineSetupError as e:
                            st.error(str(e))
                            footer_dashboard()
                            return
                        voice_emb = get_voice_embedding(voice_source.read())

                    if encodings and voice_emb:
                        face_emb = encodings[0].tolist()

                        try:
                            response_data = create_student(
                                name=new_name,
                                email_id=new_email,
                                enrollment_no=new_enrollment,
                                branch=new_class,
                                semester=new_semester,
                                section=new_section,
                                face_embedding=face_emb,
                                voice_embedding=voice_emb,
                            )
                        except StudentRegistrationPolicyError as exc:
                            st.error(str(exc))
                            footer_dashboard()
                            return
                        except Exception as exc:
                            st.error(f"Student profile create nahi ho paya: {exc}")
                            footer_dashboard()
                            return

                        if response_data:
                            train_classifier()
                            mail_status = notify_student_registration(
                                new_email, new_name, new_enrollment
                            )
                            _finish_student_login(response_data[0])
                            if mail_status["ok"]:
                                st.success(
                                    f"Profile created successfully. Registration email sent to {new_email}."
                                )
                            else:
                                st.warning(
                                    f"Profile created, but registration email failed: {mail_status['error']}"
                                )
                            time.sleep(1)
                            st.rerun()
                    elif encodings and not voice_emb:
                        st.error(
                            "Voice profile create nahi ho paya. Please clear voice recording karke dobara try karein."
                        )
                    else:
                        liveness = st.session_state.get("_last_face_liveness", {})
                        if liveness.get("spoofed_faces"):
                            spoofed = liveness["spoofed_faces"][0]
                            score = (
                                spoofed.details.get(
                                    "best_score", round(spoofed.real_score, 4)
                                )
                                if spoofed.details
                                else round(spoofed.real_score, 4)
                            )
                            st.error(
                                f"Face liveness is too low for registration. Score: {score}. Try again with a clearer live camera photo."
                            )
                        elif liveness.get("uncertain_faces"):
                            uncertain = liveness["uncertain_faces"][0]
                            score = (
                                uncertain.details.get(
                                    "real_score", round(uncertain.real_score, 4)
                                )
                                if uncertain.details
                                else round(uncertain.real_score, 4)
                            )
                            st.warning(
                                f"Face looks real but registration is uncertain. Score: {score}. Try brighter light and face the camera directly."
                            )
                        else:
                            st.error(
                                "Couldn't capture clear facial features. Please ensure good lighting and try again."
                            )
                else:
                    st.warning(
                        "Please fill Name, Email, Enrollment No. and record your voice to proceed!"
                    )

    footer_dashboard()
