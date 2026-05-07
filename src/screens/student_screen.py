import streamlit as st

from src.ui.base_layout import style_background_dashboard, style_base_layout

from src.components.header import header_dashboard
from src.components.footer import footer_dashboard

from PIL import Image
import numpy as np
import time

from src.pipelines.face_pipeline import (
    predict_attendance,
    get_face_embeddings,
    train_classifier,
)
from src.pipelines.voice_pipeline import get_voice_embedding
from src.database.db import (
    get_all_students,
    create_student,
    get_student_subjects,
    get_student_attendance,
    unenroll_student_to_subject,
)
import time

from src.components.dialog_enroll import enroll_dialog
from src.components.subject_card import subject_card
from src.components.chatbot import role_chatbot


def student_dashboard():
    student_data = st.session_state.student_data
    student_id = student_data["student_id"]
    c1, c2 = st.columns(2, vertical_alignment="center", gap="xxlarge")
    with c1:
        header_dashboard()
    with c2:
        st.subheader(f"""Welcome, {student_data['name']} """)
        if st.button(
            "Logout", type="secondary", key="loginbackbtn", shortcut="control+backspace"
        ):
            st.session_state["is_logged_in"] = False
            del st.session_state.student_data
            st.rerun()

    st.space()

    if "current_student_tab" not in st.session_state:
        st.session_state.current_student_tab = "subjects"

    tab1, tab2 = st.columns(2)
    with tab1:
        tab_type = (
            "primary" if st.session_state.current_student_tab == "subjects" else "tertiary"
        )
        if st.button("My Subjects", type=tab_type, width="stretch"):
            st.session_state.current_student_tab = "subjects"
            st.rerun()
    with tab2:
        tab_type = (
            "primary" if st.session_state.current_student_tab == "chatbot" else "tertiary"
        )
        if st.button("Chatbot", type=tab_type, width="stretch", icon=":material/chat:"):
            st.session_state.current_student_tab = "chatbot"
            st.rerun()

    st.divider()

    if st.session_state.current_student_tab == "chatbot":
        role_chatbot("student")
        footer_dashboard()
        return

    c1, c2 = st.columns(2)
    with c1:
        st.header("Your Enrolled Subjects")
    with c2:
        if st.button("Enroll in Subject", type="primary", width="stretch"):
            enroll_dialog()

    with st.spinner("Loading your enrolled subjects.."):
        subjects = get_student_subjects(student_id)
        logs = get_student_attendance(student_id)

    stats_map = {}

    for log in logs:
        sid = log["subject_id"]

        if sid not in stats_map:
            stats_map[sid] = {"total": 0, "attended": 0}

        stats_map[sid]["total"] += 1

        if log.get("is_present"):
            stats_map[sid]["attended"] += 1

    cols = st.columns(2)
    for i, sub_node in enumerate(subjects):
        sub = sub_node["subjects"]
        sid = sub["subject_id"]

        stats = stats_map.get(sid, {"total": 0, "attended": 0})

        def unenroll_button():
            if st.button(
                "Unenroll from tihs course",
                type="tertiary",
                width="stretch",
                icon=":material/delete_forever:",
            ):
                unenroll_student_to_subject(student_id, sid)
                st.toast(f"Unenrolled from {sub['name']} successfully!")
                st.rerun()

        with cols[i % 2]:

            subject_card(
                name=sub["name"],
                code=sub["subject_code"],
                section=sub["section"],
                stats=[
                    ("📅", "Total", stats["total"]),
                    ("✅", "Attended", stats["attended"]),
                ],
                footer_callback=unenroll_button,
            )
    footer_dashboard()


def student_screen():
    style_background_dashboard()
    style_base_layout()

    if "student_data" in st.session_state:
        # Agar already logged in hai toh direct dashboard dikhao (yeh function aapne define kiya hoga)
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

    st.header("Login using FaceID", anchor=False)

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
    photo_source = st.camera_input("Position your face in the center")

    if photo_source:
        img = np.array(Image.open(photo_source))

        with st.spinner("AI is scanning.."):
            detected, all_ids, num_faces = predict_attendance(img)

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
                        (s for s in all_students if s["student_id"] == student_id), None
                    )

                    if student:
                        st.session_state.is_logged_in = True
                        st.session_state.user_role = "student"
                        st.session_state.student_data = student
                        st.toast(f"Welcome Back {student['name']}! 👋")
                        time.sleep(1)
                        st.rerun()
                else:
                    st.info(
                        "Face not recognized! Looks like you are a new student. Please register below."
                    )
                    show_registration = True

    # --- REGISTRATION SECTION ---
    if show_registration:
        with st.container(border=True):
            st.header("Register New Profile", anchor=False)

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

            # --- Academic Info (Dropdowns Added Here) ---
            st.subheader("Academic Details", anchor=False)
            col1, col2, col3 = st.columns(3)
            with col1:
                new_branch = st.selectbox(
                    "Branch",
                    [
                        "Computer Science",
                        "Information Tech",
                        "ECE",
                        "Mechanical",
                        "Civil",
                        "Ai/Ml",
                        "AI/DS",
                        "DS",
                    ],
                )
            with col2:
                # Drodown for Semester (1 to 8)
                new_semester = st.selectbox("Semester", [1, 2, 3, 4, 5, 6, 7, 8])
            with col3:
                new_section = st.selectbox("Section", ["A", "B", "C", "D", "None"])

            st.divider()

            # --- Optional: Voice Info ---
            st.subheader("Optional: Voice Enrollment", anchor=False)
            st.info("Enroll your voice for audio attendance backup")

            audio_data = None
            try:
                audio_data = st.audio_input(
                    'Record a short phrase like: "I am present, My name is Ayush."'
                )
            except Exception:
                st.error(
                    "Audio recording failed! Please check your microphone permissions."
                )

            # --- Submit Button ---
            if st.button("Create Account", type="primary", width="stretch"):
                if new_name and new_email and new_enrollment:
                    with st.spinner("Creating your profile and encoding biometrics..."):
                        img = np.array(Image.open(photo_source))
                        encodings = get_face_embeddings(img)

                        if encodings:
                            face_emb = encodings[0].tolist()
                            voice_emb = None
                            if audio_data:
                                voice_emb = get_voice_embedding(audio_data.read())

                            response_data = create_student(
                                name=new_name,
                                email_id=new_email,
                                enrollment_no=new_enrollment,
                                branch=new_branch,
                                semester=new_semester,
                                section=new_section,
                                face_embedding=face_emb,
                                voice_embedding=voice_emb,
                            )

                            if response_data:
                                train_classifier()
                                st.session_state.is_logged_in = True
                                st.session_state.user_role = "student"
                                st.session_state.student_data = response_data[0]
                                st.success(
                                    f"Profile Created successfully! Welcome {new_name}!"
                                )
                                time.sleep(1)
                                st.rerun()
                        else:
                            st.error(
                                "Couldn't capture clear facial features. Please ensure good lighting and try again."
                            )
                else:
                    st.warning(
                        "Please fill all the basic details (Name, Email, Enrollment No.) to proceed!"
                    )

    footer_dashboard()
