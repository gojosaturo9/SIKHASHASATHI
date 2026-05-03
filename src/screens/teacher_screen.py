import streamlit as st
from src.ui.base_layout import style_background_dashboard, style_base_layout
from src.components.header import header_dashboard
from src.components.footer import footer_dashboard
from src.components.subject_card import subject_card
from src.components.dialog_share_subject import share_subject_dialog
from src.database.db import (
    register_teacher,
    get_teacher_subjects,
    get_attendance_for_teacher,
    check_pass,
)
from src.components.dialog_create_subject import create_subject_dialog
from src.components.dialog_add_photo import add_photos_dialog

from src.pipelines.face_pipeline import predict_attendance
from src.components.dialog_attendance_results import attendance_result_dialog
import numpy as np

from datetime import datetime

import pandas as pd

from src.database.config import supabase
from src.components.dialog_voice_attendance import voice_attendance_dialog


def teacher_screen():

    style_background_dashboard()
    style_base_layout()

    if "teacher_data" in st.session_state:
        teacher_dashboard()
    elif (
        "teacher_login_type" not in st.session_state
        or st.session_state.teacher_login_type == "login"
    ):
        teacher_screen_login()
    elif st.session_state.teacher_login_type == "register":
        teacher_screen_register()


def teacher_dashboard():
    teacher_data = st.session_state.teacher_data
    c1, c2 = st.columns(2, vertical_alignment="center", gap="xxlarge")
    with c1:
        header_dashboard()
    with c2:
        st.subheader(f"""Welcome, {teacher_data['name']} """)
        if st.button(
            "Logout", type="secondary", key="loginbackbtn", shortcut="control+backspace"
        ):
            st.session_state["is_logged_in"] = False
            del st.session_state.teacher_data
            st.rerun()

    st.space()

    if "current_teacher_tab" not in st.session_state:
        st.session_state.current_teacher_tab = "take_attendance"
    tab1, tab2, tab3 = st.columns(3)

    with tab1:
        type1 = (
            "primary"
            if st.session_state.current_teacher_tab == "take_attendance"
            else "tertiary"
        )
        if st.button(
            "Take Attendance", type=type1, width="stretch", icon=":material/ar_on_you:"
        ):
            st.session_state.current_teacher_tab = "take_attendance"
            st.rerun()

    with tab2:
        type2 = (
            "primary"
            if st.session_state.current_teacher_tab == "manage_subjects"
            else "tertiary"
        )
        if st.button(
            "Manage Subjects",
            type=type2,
            width="stretch",
            icon=":material/book_ribbon:",
        ):
            st.session_state.current_teacher_tab = "manage_subjects"
            st.rerun()

    with tab3:
        type3 = (
            "primary"
            if st.session_state.current_teacher_tab == "attendance_records"
            else "tertiary"
        )
        if st.button(
            "Attendance Records",
            type=type3,
            width="stretch",
            icon=":material/cards_stack:",
        ):
            st.session_state.current_teacher_tab = "attendance_records"
            st.rerun()

    st.divider()

    if st.session_state.current_teacher_tab == "take_attendance":
        teacher_tab_take_attendance()

    if st.session_state.current_teacher_tab == "manage_subjects":
        teacher_tab_manage_subjects()

    if st.session_state.current_teacher_tab == "attendance_records":
        teacher_tab_attendance_records()

    footer_dashboard()


def teacher_tab_take_attendance():
    teacher_id = st.session_state.teacher_data["teacher_id"]
    st.header("Take AI Attendance")

    if "attendance_images" not in st.session_state:
        st.session_state.attendance_images = []

    subjects = get_teacher_subjects(teacher_id)

    if not subjects:
        st.warning("You haven't created any subjects yet! Please create one to begin!")
        return

    # Subject details store karna zaroori hai (Name aur ID dono)
    subject_options = {f"{s['name']} - {s['subject_code']}": s for s in subjects}

    col1, col2 = st.columns([3, 1], vertical_alignment="bottom")
    with col1:
        selected_label = st.selectbox(
            "Select Subject", options=list(subject_options.keys())
        )
        selected_subject = subject_options[selected_label]
        selected_subject_id = selected_subject["subject_id"]
        selected_subject_name = selected_subject["name"]

    with col2:
        if st.button(
            "Add Photos",
            type="primary",
            icon=":material/photo_prints:",
            width="stretch",
        ):
            add_photos_dialog()

    st.divider()

    if st.session_state.attendance_images:
        st.header("Added Photos")
        gallery_cols = st.columns(4)
        for idx, img in enumerate(st.session_state.attendance_images):
            with gallery_cols[idx % 4]:
                st.image(img, use_container_width=True, caption=f"Photo {idx+1}")

    has_photos = bool(st.session_state.attendance_images)
    c1, c2, c3 = st.columns(3)

    with c1:
        if st.button(
            "Clear all photos",
            width="stretch",
            type="tertiary",
            icon=":material/delete:",
            disabled=not has_photos,
        ):
            st.session_state.attendance_images = []
            st.rerun()

    with c2:
        if st.button(
            "Run Face Analysis",
            width="stretch",
            type="secondary",
            icon=":material/analytics:",
            disabled=not has_photos,
        ):
            with st.spinner("Deep scanning classroom photos..."):
                all_detected_ids = {}

                for idx, img in enumerate(st.session_state.attendance_images):
                    img_np = np.array(img.convert("RGB"))
                    # 🚀 STEP 5: Ab hum subject_id pass kar rahe hain (Smart Prediction)
                    detected, _, _ = predict_attendance(img_np, selected_subject_id)

                    if detected:
                        for sid in detected.keys():
                            student_id = int(sid)
                            all_detected_ids.setdefault(student_id, []).append(
                                f"Photo {idx+1}"
                            )

                # 🚀 STEP 3: Smart student fetching (Auto or Manual)
                from src.database.db import get_students_for_subject

                students_list = get_students_for_subject(selected_subject_id)

                if not students_list:
                    st.warning("No students found for this class/subject.")
                else:
                    results, attendance_to_log = [], []
                    current_timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

                    for student in students_list:
                        sources = all_detected_ids.get(int(student["student_id"]), [])
                        is_present = len(sources) > 0

                        results.append(
                            {
                                "Name": student["name"],
                                "ID": student["student_id"],
                                "email_id": student.get(
                                    "email_id"
                                ),  # Email notification ke liye zaroori
                                "is_present": is_present,
                                "Source": ", ".join(sources) if is_present else "-",
                                "Status": "✅ Present" if is_present else "❌ Absent",
                            }
                        )

                        attendance_to_log.append(
                            {
                                "student_id": student["student_id"],
                                "subject_id": selected_subject_id,
                                "timestamp": current_timestamp,
                                "is_present": bool(is_present),
                            }
                        )

                    # 🚀 STEP 5: Dialog ko subject name bhi pass kar rahe hain email trigger ke liye
                    attendance_result_dialog(
                        pd.DataFrame(results), attendance_to_log, selected_subject_name
                    )

    with c3:
        if st.button(
            "Use Voice Attendance",
            type="primary",
            width="stretch",
            icon=":material/mic:",
        ):
            voice_attendance_dialog(selected_subject_id)


def teacher_tab_manage_subjects():
    teacher_id = st.session_state.teacher_data["teacher_id"]
    col1, col2 = st.columns(2)
    with col1:
        st.header("Manage Subjects", width="stretch")
    with col2:
        if st.button("Create New Subject", width="stretch"):
            create_subject_dialog(teacher_id)

    subjects = get_teacher_subjects(teacher_id)
    if subjects:
        for sub in subjects:
            is_class_wise = sub.get("type") == "class_wise"
            sub_type_label = "📍 Class-wise" if is_class_wise else "🌐 Mixed"

            if is_class_wise:
                b = sub.get("target_branch", "All")
                s = sub.get("target_semester", "All")
                sec = sub.get("target_section", "All")
                class_details = f"🎓 {b} | Sem {s} | Sec {sec}"
            else:
                # 🚀 FIX: Yahan se section dikhane ka logic hata diya
                class_details = "🧩 Mixed/Open Class"

            stats = [
                ("🫂", "Students", sub["total_students"]),
                ("🕰️", "Classes", sub["total_classes"]),
                ("🏷️", "Type", sub_type_label),
            ]

            def share_btn(current_sub=sub):
                if st.button(
                    f"Share Code: {current_sub['name']}",
                    key=f"share_{current_sub['subject_id']}",
                    icon=":material/share:",
                ):
                    share_subject_dialog(
                        current_sub["name"], current_sub["subject_code"]
                    )
                st.space()

            subject_card(
                name=sub["name"],
                code=sub["subject_code"],
                section=class_details,
                stats=stats,
                footer_callback=share_btn,
            )
    else:
        st.info("NO SUBJECTS FOUND. CREATE ONE ABOVE")


def teacher_tab_attendance_records():
    st.header("Attendance Records")

    teacher_id = st.session_state.teacher_data["teacher_id"]
    records = get_attendance_for_teacher(teacher_id)

    if not records:
        st.info("No attendance records found.")
        return

    # --- Data Prepare ---
    data = []
    for r in records:
        ts = r.get("timestamp")
        data.append(
            {
                "ts_group": ts.split(".")[0] if ts else None,
                "Date": (
                    datetime.fromisoformat(ts).strftime("%Y-%m-%d") if ts else "N/A"
                ),
                "Time": (
                    datetime.fromisoformat(ts).strftime("%I:%M %p") if ts else "N/A"
                ),
                "Subject": r["subjects"]["name"],
                "Subject Code": r["subjects"]["subject_code"],
                "subject_id": r["subjects"]["subject_id"],
                "Student Name": r["students"]["name"],
                "student_id": r["students"]["student_id"],
                "is_present": bool(r.get("is_present", False)),
                "Status": "✅ Present" if r.get("is_present") else "❌ Absent",
            }
        )

    df = pd.DataFrame(data)

    # --- Subject Filter ---
    subjects = df["Subject"].unique().tolist()
    selected_subject = st.selectbox("📚 Select Subject", ["All Subjects"] + subjects)

    if selected_subject != "All Subjects":
        df = df[df["Subject"] == selected_subject]

    # --- Session History ---
    st.subheader("📋 Session History")

    summary = (
        df.groupby(["ts_group", "Date", "Time", "Subject", "Subject Code"])
        .agg(Present=("is_present", "sum"), Total=("is_present", "count"))
        .reset_index()
    )
    summary["Attendance %"] = ((summary["Present"] / summary["Total"]) * 100).round(
        1
    ).astype(str) + "%"
    summary["Stats"] = (
        "✅ " + summary["Present"].astype(str) + " / " + summary["Total"].astype(str)
    )
    summary = summary.sort_values("ts_group", ascending=False).reset_index(drop=True)

    # Summary Table
    st.dataframe(
        summary[["Date", "Time", "Subject", "Subject Code", "Stats", "Attendance %"]],
        hide_index=True,
        use_container_width=True,
    )

    st.write("")

    # --- Session Detail ---
    st.subheader("🔍 Session Detail")
    st.caption("Select any session to see the details ")

    session_options = (
        summary["Date"] + " | " + summary["Time"] + " | " + summary["Subject"]
    ).tolist()
    selected_session_label = st.selectbox(
        "Session Select karo", ["-- Select a Session --"] + session_options
    )

    if selected_session_label != "-- Select a Session --":
        idx = session_options.index(selected_session_label)
        selected_ts = summary.iloc[idx]["ts_group"]
        selected_subj = summary.iloc[idx]["Subject"]

        session_df = df[
            (df["ts_group"] == selected_ts) & (df["Subject"] == selected_subj)
        ]

        st.divider()

        # Metrics
        m1, m2, m3 = st.columns(3)
        present_count = int(session_df["is_present"].sum())
        total_count = len(session_df)
        absent_count = total_count - present_count
        percent = round((present_count / total_count) * 100, 1) if total_count else 0

        m1.metric("Total Students", total_count)
        m2.metric("✅ Present", present_count)
        m3.metric("❌ Absent", absent_count)

        st.metric("Attendance %", f"{percent}%")

        st.write("")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("### ✅ Present Students")
            present_df = session_df[session_df["is_present"] == True][["Student Name"]]
            if present_df.empty:
                st.info("Koi present nahi")
            else:
                st.dataframe(present_df, hide_index=True, use_container_width=True)

        with col2:
            st.markdown("### ❌ Absent Students")
            absent_df = session_df[session_df["is_present"] == False][["Student Name"]]
            if absent_df.empty:
                st.success("All students are present ")
            else:
                st.dataframe(absent_df, hide_index=True, use_container_width=True)

    # --- Overall Student Attendance Summary ---
    st.divider()
    st.subheader("📊 Student-wise Overall Attendance")

    student_summary = (
        df.groupby(["student_id", "Student Name", "Subject"])
        .agg(Total_Classes=("is_present", "count"), Present_Days=("is_present", "sum"))
        .reset_index()
    )
    student_summary["Absent Days"] = (
        student_summary["Total_Classes"] - student_summary["Present_Days"]
    )
    student_summary["Attendance %"] = (
        (student_summary["Present_Days"] / student_summary["Total_Classes"]) * 100
    ).round(1).astype(str) + "%"

    student_summary["⚠️"] = (
        student_summary["Present_Days"] / student_summary["Total_Classes"] * 100 < 75
    ).map({True: "⚠️ Low", False: "✅ Good"})

    st.dataframe(
        student_summary[
            [
                "Student Name",
                "Subject",
                "Total_Classes",
                "Present_Days",
                "Absent Days",
                "Attendance %",
                "⚠️",
            ]
        ],
        hide_index=True,
        use_container_width=True,
    )


def teacher_screen_login():
    st.markdown(
        """
        <style>
            /* 1. Label Text Color */
            .stTextInput label p {
                color: #2D3436 !important; 
                font-weight: 600 !important;
                font-size: 1.1rem !important;
            }
            
            /* 2. Input Box Styling */
            .stTextInput input {
                background-color: #FFFFFF !important; 
                color: #000000 !important; 
                border: 2px solid #5865F2 !important; 
                border-radius: 0.8rem !important;
            }
            
            /* 3. Focus / Click Effect */
            .stTextInput input:focus {
                border-color: #EB459E !important; 
                box-shadow: 0 0 5px rgba(235, 69, 158, 0.5) !important;
            }
            
            /*  Placeholder wapas laane ke liye */
            .stTextInput input::placeholder {
                color: #A0AAB2 !important; /* Halka grey color */
                opacity: 1 !important; /* Ensure visibility */
            }

            /*  "Press Enter to apply" gayab karne ke liye */
            div[data-testid="InputInstructions"] {
                display: none !important;
            }
            
            /* 4. Custom Divider */
            hr {
                border: none !important;
                border-top: 2px solid #5865F2 !important; 
                margin-top: 2rem !important;
                margin-bottom: 2rem !important;
                opacity: 0.5; 
            }
        </style>
    """,
        unsafe_allow_html=True,
    )

    # --- Baki ka code same rahega ---
    c1, c2 = st.columns(2, vertical_alignment="center", gap="xxlarge")
    with c1:
        header_dashboard()
    with c2:
        if st.button(
            "Go back to Home",
            type="secondary",
            key="loginbackbtn",
            shortcut="control+backspace",
        ):
            st.session_state["login_type"] = None
            st.rerun()

    st.markdown(
        "<h2 style='text-align: center; color:black;'>Login using password</h2>",
        unsafe_allow_html=True,
    )

    st.write("")
    st.write("")

    teacher_username = st.text_input("Enter username", placeholder="Enter username")
    teacher_pass = st.text_input(
        "Enter password", type="password", placeholder="Enter password"
    )

    st.markdown(
        "<hr style='border: 2px solid #5865F2; border-radius: 5px; opacity: 0.5;'>",
        unsafe_allow_html=True,
    )

    btnc1, btnc2 = st.columns(2)
    with btnc1:
        if st.button(
            "Login",
            icon=":material/passkey:",
            shortcut="control+enter",
            width="stretch",
        ):

            response = (
                supabase.table("teachers")
                .select("*")
                .eq("username", teacher_username)
                .execute()
            )

            if response.data:
                teacher_data = response.data[0]

                # Step 1: Pehle password check karein
                if check_pass(teacher_pass, teacher_data["password"]):

                    # Step 2: Password sahi hai, ab check karein Admin ne verify kiya hai ya nahi
                    if teacher_data.get("is_verified") == True:
                        # Verified! Login kara dein
                        st.session_state["is_logged_in"] = True
                        st.session_state["user_role"] = "teacher"
                        st.session_state["teacher_data"] = teacher_data

                        st.toast("Welcome back!", icon="👋")
                        import time

                        time.sleep(1)
                        st.rerun()
                    else:
                        # Password sahi hai, par Admin verification baaki hai
                        st.warning(
                            "⚠️ Your account is pending Admin approval. Please wait for verification."
                        )
                else:
                    st.error("Invalid password!")
            else:
                st.error("Username not found!")

    with btnc2:
        if st.button(
            "Register Instead",
            type="primary",
            icon=":material/app_registration:",
            width="stretch",
        ):
            st.session_state.teacher_login_type = "register"
            st.rerun()
    # 👆 YAHAN TAK 👆

    footer_dashboard()


def teacher_screen_register():
    st.markdown(
        """
        <style>
            /* 1. Label Text Color */
            .stTextInput label p {
                color: #2D3436 !important; 
                font-weight: 600 !important;
                font-size: 1.1rem !important;
            }
            
            /* 2. Input Box Styling */
            .stTextInput input {
                background-color: #FFFFFF !important; 
                color: #000000 !important; 
                border: 2px solid #5865F2 !important; 
                border-radius: 0.8rem !important;
            }
            
            /* 3. Focus / Click Effect */
            .stTextInput input:focus {
                border-color: #EB459E !important; 
                box-shadow: 0 0 5px rgba(235, 69, 158, 0.5) !important;
            }
            
            /*  NAYA FIX 1: Placeholder wapas laane ke liye */
            .stTextInput input::placeholder {
                color: #A0AAB2 !important; 
                opacity: 1 !important; 
            }

            /* NAYA FIX 2: "Press Enter to apply" gayab karne ke liye */
            div[data-testid="InputInstructions"] {
                display: none !important;
            }
            
            /* 4. Custom Divider */
            hr {
                border: none !important;
                border-top: 2px solid #5865F2 !important; 
                margin-top: 2rem !important;
                margin-bottom: 2rem !important;
                opacity: 0.5; 
            }
        </style>
    """,
        unsafe_allow_html=True,
    )
    c1, c2 = st.columns(2, vertical_alignment="center", gap="xxlarge")
    with c1:
        header_dashboard()
    with c2:
        if st.button(
            "Go back to Home",
            type="secondary",
            key="loginbackbtn",
            shortcut="control+backspace",
        ):
            st.session_state["login_type"] = None
            st.rerun()

    st.markdown(
        "<h2 style='text-align: center; color:black;'>Register your teacher profile</h2>",
        unsafe_allow_html=True,
    )

    teacher_username = st.text_input(
        "Enter username", placeholder="Enter username here"
    )

    teacher_name = st.text_input("Enter name", placeholder="Enter your name here")

    # 👇 NAYA FIELD: Email ID ke liye
    teacher_email = st.text_input(
        "Enter Email ID", placeholder="Enter your valid email id"
    )

    teacher_pass = st.text_input(
        "Enter password", type="password", placeholder="Enter password"
    )

    teacher_pass_confirm = st.text_input(
        "Confirm your password", type="password", placeholder="Enter password"
    )

    st.divider()

    btnc1, btnc2 = st.columns(2)

    with btnc1:
        if st.button(
            "Register now",
            icon=":material/passkey:",
            shortcut="control+enter",
            width="stretch",
        ):

            success, message = register_teacher(
                teacher_username,
                teacher_name,
                teacher_email,
                teacher_pass,
                teacher_pass_confirm,
            )
            if success:
                st.success(message)
                import time

                time.sleep(2)
                st.session_state.teacher_login_type = "login"
                st.rerun()
            else:
                st.error(message)

    with btnc2:
        if st.button(
            "Login Instead", type="primary", icon=":material/passkey:", width="stretch"
        ):
            st.session_state.teacher_login_type = "login"

    footer_dashboard()
