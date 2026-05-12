import streamlit as st
import pandas as pd
import random
import string
import bcrypt  # 🚀 Password hash karne ke liye
from src.database.config import (
    is_supabase_configured,
    render_supabase_setup,
    require_admin_supabase,
    require_supabase,
)
from src.database.db import (
    create_teacher,
    get_all_attendance_records,
)

# 🚀 FIX: Naya email function import kiya
from src.ui.base_layout import style_background_dashboard, style_base_layout
from src.components.footer import footer_dashboard
from src.components.ai_insights import render_ai_insights
from src.voice_rag.streamlit_ui import render_voice_rag_chatbot
from src.utils.notifier import (
    notify_student_registration,
    send_teacher_credentials_email_now,
)


# --- 🚀 NAYA FIX: ADD TEACHER TAB (Purana verification tab hata diya) ---
# Use: Handles add teacher tab behavior in this module.
# Linked with: admin_dashboard
def add_teacher_tab():
    supabase = require_admin_supabase()
    st.header("👨‍🏫 Add New Teacher")
    st.write(
        "Create a secure account for a new faculty member. They will receive their auto-generated password via email."
    )

    with st.form("add_teacher_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            t_name = st.text_input("Full Name", placeholder="e.g., Dr. Ramesh Kumar")
            t_username = st.text_input("Username", placeholder="e.g., ramesh_cs")
        with col2:
            t_email = st.text_input(
                "Email Address", placeholder="e.g., ramesh@college.edu"
            )

        st.write("")
        submitted = st.form_submit_button(
            "Create Teacher Account", type="primary", use_container_width=True
        )

        if submitted:
            if not t_name or not t_username or not t_email:
                st.warning("⚠️ Please fill all the fields!")
            else:
                with st.spinner("Creating account & generating secure credentials..."):
                    # 1. Check if username already exists
                    check = (
                        supabase.table("teachers")
                        .select("username")
                        .eq("username", t_username)
                        .execute()
                    )

                    if check.data:
                        st.error(
                            "❌ Username already exists! Please choose a different one."
                        )
                    else:
                        # 2. Generate Random 8-character Password
                        raw_pass = "".join(
                            random.choices(
                                string.ascii_letters + string.digits + "@#$", k=8
                            )
                        )

                        # 3. Hash the password for security
                        hashed_pass = bcrypt.hashpw(
                            raw_pass.encode("utf-8"), bcrypt.gensalt()
                        ).decode("utf-8")

                        try:
                            # 4. Save to Database (is_verified column hata diya gaya hai)
                            insert_response = supabase.table("teachers").insert(
                                {
                                    "name": t_name,
                                    "username": t_username,
                                    "email_id": t_email,
                                    "password": hashed_pass,
                                }
                            ).execute()
                            created_teacher = insert_response.data[0] if insert_response.data else {}
                            teacher_id = created_teacher.get("teacher_id", "created")

                            st.info(f"Teacher ID: {teacher_id}")
                            # 5. Send Email with Credentials
                            st.success(f"✅ Account for {t_name} created successfully!")
                            try:
                                send_teacher_credentials_email_now(
                                    t_email, t_name, t_username, raw_pass
                                )
                                st.info(f"Credentials have been emailed to {t_email}")
                            except Exception as mail_error:
                                st.warning(
                                    f"Account created, but credentials email failed: {mail_error}"
                                )
                                st.info(
                                    "Email fail hua, isliye credentials manually share karo. "
                                    f"Username: {t_username} | Temporary Password: {raw_pass}"
                                )
                        except Exception as e:
                            error_text = str(e)
                            if "42501" in error_text or "row-level security" in error_text.lower():
                                st.error(
                                    "Teacher account create nahi ho paya because Supabase RLS policy teachers table par insert allow nahi kar rahi. "
                                    "Supabase SQL Editor me updated supabase_student_registration_rls.sql run karo."
                                )
                                return
                            st.error(f"⚠️ Error creating account: {e}")


# Use: Handles add student tab behavior in this module.
# Linked with: admin_dashboard
def add_student_tab():
    from src.database.db import create_student
    st.header("🎓 Add New Student")
    st.write("Manually register a student profile. They can later scan their face during their first login.")

    with st.form("add_student_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            s_name = st.text_input("Full Name", placeholder="e.g., Aniket Singh")
            s_email = st.text_input("Email ID", placeholder="e.g., aniket@gmail.com")
            s_roll = st.text_input("Enrollment / Roll No.", placeholder="e.g., 0123CS191001")
        with c2:
            s_branch = st.text_input("Branch / Department", placeholder="e.g., CSE")
            s_semester = st.selectbox("Semester", [str(i) for i in range(1, 9)])
            s_section = st.text_input("Section", placeholder="e.g., A")

        submitted = st.form_submit_button("Create Student Profile", type="primary", use_container_width=True)

        if submitted:
            if not s_name or not s_roll or not s_email:
                st.warning("Please fill essential fields (Name, Email, Roll No).")
            else:
                try:
                    create_student(s_name, s_email, s_roll, s_branch, s_semester, s_section)
                    mail_status = notify_student_registration(s_email, s_name, s_roll)
                    st.success(f"✅ Student profile for {s_name} created successfully!")
                    if mail_status["ok"]:
                        st.info(f"Registration email sent to {s_email}")
                    else:
                        st.warning(
                            f"Student created, but registration email failed: {mail_status['error']}"
                        )
                except Exception as e:
                    st.error(f"Error creating student: {e}")


# Use: Handles admin dashboard behavior in this module.
# Linked with: main
def admin_dashboard():
    style_background_dashboard()
    style_base_layout()

    c1, c2 = st.columns([4, 1], vertical_alignment="center")
    with c1:
        st.title("🛡️ Admin Control Panel")
    with c2:
        if st.button("Logout", type="secondary", icon=":material/logout:", use_container_width=True):
            st.session_state["is_logged_in"] = False
            st.session_state["user_role"] = None
            st.session_state["login_type"] = None

            if "teacher_data" in st.session_state:
                del st.session_state["teacher_data"]

            st.toast("Logged out successfully!")
            st.rerun()

    st.divider()

    if not is_supabase_configured():
        render_supabase_setup("Admin Portal")
        footer_dashboard()
        return

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["👨‍🏫 Add Teacher", "🎓 Add Student", "📊 Analytics", "📢 Broadcast", "Insights"]
    )

    with tab1:
        add_teacher_tab()
    with tab2:
        add_student_tab()
    with tab3:
        attendance_analytics_tab()
    with tab4:
        broadcast_tab()
    with tab5:
        render_ai_insights()

    render_voice_rag_chatbot("admin")
    footer_dashboard()


# Use: Handles broadcast tab behavior in this module.
# Linked with: admin_dashboard
def broadcast_tab():
    st.header("📢 Global Broadcast System")
    st.write("Post important messages, holiday notices, or urgent updates to all students and teachers.")

    from src.database.db import create_announcement, get_active_announcements, cleanup_old_announcements

    # Auto-cleanup old announcements
    cleanup_old_announcements()

    with st.form("broadcast_form", clear_on_submit=True):
        title = st.text_input("Announcement Title", placeholder="e.g., Holiday Notice")
        category = st.selectbox("Category", ["General", "Holiday", "Urgent", "Event"])
        content = st.text_area("Message Content", placeholder="Enter your detailed message here...")

        submitted = st.form_submit_button("Broadcast to Everyone", type="primary", use_container_width=True)

        if submitted:
            if title and content:
                try:
                    create_announcement(title, content, category)
                    st.success("✅ Announcement broadcasted successfully!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}. (Make sure the 'announcements' table exists in Supabase)")
            else:
                st.warning("Please provide both title and content.")

    st.divider()
    st.subheader("Recent Broadcasts")
    try:
        from src.database.db import delete_announcement
        active = get_active_announcements()
        if active:
            for ann in active:
                exp_col, del_col = st.columns([6, 1], vertical_alignment="center")
                with exp_col:
                    with st.expander(f"{ann['title']} - {ann['created_at'].split('T')[0]}"):
                        st.caption(f"Category: {ann['category']}")
                        st.write(ann['content'])
                with del_col:
                    if st.button("Delete", key=f"del_ann_{ann['id']}", type="secondary", use_container_width=True):
                        delete_announcement(ann['id'])
                        st.toast("Announcement deleted.")
                        st.rerun()
        else:
            st.info("No recent announcements found.")
    except Exception:
        st.info("Announcements table might not be ready yet.")


# Use: Handles attendance analytics tab behavior in this module.
# Linked with: admin_dashboard
def attendance_analytics_tab():
    supabase = require_supabase()
    st.caption(
        "Admin has read-only attendance analytics. Present/absent corrections are handled by teachers in their Records section."
    )
    st.header("📊 Deep Analytics & College Dashboard")

    try:
        records = get_all_attendance_records()
    except Exception as exc:
        records = []
        st.warning(
            "Attendance analytics abhi load nahi ho paya because Supabase connection temporarily disconnect ho gaya. "
            f"Page refresh karke dobara try karein. Detail: {exc}"
        )
    df = pd.DataFrame(records) if records else pd.DataFrame()

    try:
        # 🚀 FIX: Select me se 'is_verified' hata diya
        teachers_data = (
            supabase.table("teachers").select("name, username, email_id").execute().data
        )
        students_data = supabase.table("students").select("*").execute().data

        teachers_df = pd.DataFrame(teachers_data)
        students_df = pd.DataFrame(students_data)

        cols_to_drop = [
            "face_embedding",
            "voice_embedding",
            "face_encodings",
            "voice_data",
        ]
        students_df = students_df.drop(
            columns=[c for c in cols_to_drop if c in students_df.columns],
            errors="ignore",
        )

        if not df.empty and "Subject" in df.columns:
            df["Subject"] = df["Subject"].astype(str).str.upper()

        if not students_df.empty:
            for col in students_df.columns:
                if "enroll" in col.lower() or "roll" in col.lower():
                    students_df[col] = students_df[col].astype(str).str.upper()

    except Exception as e:
        st.error(f"Database Error: Could not fetch extra details - {e}")
        teachers_df = pd.DataFrame()
        students_df = pd.DataFrame()

    if df.empty and students_df.empty:
        st.warning("No records found in the database yet.")
        return

    st.subheader("Key Performance Indicators")
    m1, m2, m3, m4 = st.columns(4)

    with m1:
        total_students = (
            len(students_df)
            if not students_df.empty
            else (df["Student Name"].nunique() if not df.empty else 0)
        )
        st.metric("Total Enrolled Students 🎓", total_students)
    with m2:
        # 🚀 FIX: is_verified wala logic hata kar seedha len(teachers_df) kar diya
        total_teachers = len(teachers_df) if not teachers_df.empty else 0
        st.metric("Total Teachers 👨‍🏫", total_teachers)
    with m3:
        total_days = df["Date"].nunique() if not df.empty else 0
        st.metric("Total Class Days 📅", total_days)
    with m4:
        avg_attendance = (
            (df["Status"] == "✅ Present").mean() * 100 if not df.empty else 0
        )
        st.metric("College Avg. Attendance", f"{avg_attendance:.1f}%")

    st.divider()

    tab_overview, tab_students, tab_defaulters, tab_teachers, tab_raw = st.tabs(
        [
            "📈 Analytics Overview",
            "🎓 Student Directory",
            "🚨 Defaulters List",
            "👨‍🏫 Teacher Directory",
            "📄 Raw Data",
        ]
    )

    with tab_overview:
        if not df.empty:
            c1, c2 = st.columns(2)
            with c1:
                st.write("#### 📊 Branch-wise Student Strength")
                branch_counts = df.groupby("branch")["Student Name"].nunique()
                st.bar_chart(branch_counts, color="#0984e3")

            with c2:
                st.write("#### 📈 Daily Attendance Trend")
                daily_trend = (
                    df[df["Status"] == "✅ Present"].groupby("Date").count()["Status"]
                )
                st.line_chart(daily_trend, color="#00b894")

            st.divider()
            st.write("#### 📚 Subject-wise Average Attendance (%)")
            if "Subject" in df.columns:
                subject_stats = (
                    df.groupby("Subject")
                    .apply(lambda x: (x["Status"] == "✅ Present").mean() * 100)
                    .round(1)
                )
                st.bar_chart(subject_stats, color="#fdcb6e")
        else:
            st.info("Not enough attendance data for charts.")

    if not students_df.empty and not df.empty:
        student_report = (
            df.groupby("Student Name")
            .agg(
                Total_Classes=("Status", "count"),
                Present_Days=("Status", lambda x: (x == "✅ Present").sum()),
            )
            .reset_index()
        )

        student_report["Present_Days"] = student_report["Present_Days"].astype(float)
        student_report["Total_Classes"] = student_report["Total_Classes"].astype(float)
        student_report["Attendance_%"] = (
            student_report["Present_Days"] / student_report["Total_Classes"] * 100
        ).round(1)

        col_to_merge = (
            "name" if "name" in students_df.columns else students_df.columns[0]
        )
        full_student_data = pd.merge(
            students_df,
            student_report,
            left_on=col_to_merge,
            right_on="Student Name",
            how="left",
        )
        full_student_data.fillna(
            {"Total_Classes": 0, "Present_Days": 0, "Attendance_%": 0.0}, inplace=True
        )

        if "Student Name" in full_student_data.columns:
            full_student_data.drop(columns=["Student Name"], inplace=True)

        # Use: Handles color low attendance behavior in this module.
        # Linked with: Streamlit UI, decorators, tests, or external runtime calls.
        def color_low_attendance(val):
            if pd.isna(val):
                return ""
            color = "red" if float(val) < 75 else "green"
            return f"color: {color}; font-weight: bold;"

    else:
        full_student_data = pd.DataFrame()

    with tab_students:
        st.write("### Complete Student Profiles & Attendance Stats")
        if not full_student_data.empty:
            search_stu = st.text_input(
                "🔍 Search Student Name/Roll No",
                placeholder="Type here...",
                key="search_all",
            )

            f1, f2, f3 = st.columns(3)
            with f1:
                branch_filter = st.selectbox(
                    "Branch",
                    ["All"]
                    + list(
                        full_student_data.get("branch", pd.Series()).dropna().unique()
                    ),
                    key="branch_all",
                )
            with f2:
                sem_filter = st.selectbox(
                    "Semester",
                    ["All"]
                    + list(
                        full_student_data.get("semester", pd.Series()).dropna().unique()
                    ),
                    key="sem_all",
                )
            with f3:
                sec_filter = st.selectbox(
                    "Section",
                    ["All"]
                    + list(
                        full_student_data.get("section", pd.Series()).dropna().unique()
                    ),
                    key="sec_all",
                )

            display_df = full_student_data.copy()

            if branch_filter != "All":
                display_df = display_df[display_df["branch"] == branch_filter]
            if sem_filter != "All":
                display_df = display_df[display_df["semester"] == sem_filter]
            if sec_filter != "All":
                display_df = display_df[display_df["section"] == sec_filter]

            if search_stu:
                display_df = display_df[
                    display_df.astype(str)
                    .apply(lambda x: x.str.contains(search_stu, case=False))
                    .any(axis=1)
                ]

            st.dataframe(
                display_df.style.map(color_low_attendance, subset=["Attendance_%"]),
                width="stretch",
                hide_index=True,
            )

            st.divider()
            st.subheader("🗑️ Remove Student")
            with st.expander("Danger Zone: Delete Student Account"):
                s_to_del = st.selectbox("Select Student to Remove", options=["-"] + display_df["name"].tolist() if not display_df.empty else ["-"], key="del_stu_box")
                if s_to_del != "-":
                    stu_row = display_df[display_df["name"] == s_to_del].iloc[0]
                    st.warning(f"Are you sure you want to delete {s_to_del} ({stu_row.get('enrollment_no', 'N/A')})?")
                    if st.button("Confirm Delete Student", type="primary"):
                        from src.database.db import delete_student
                        deleted = delete_student(stu_row["student_id"])
                        if deleted is not None:
                            st.success(f"Student {s_to_del} removed.")
                            st.rerun()
                        else:
                            st.error("Student delete nahi ho paya. Service role key/RLS settings check karo.")
        else:
            st.warning("Either Student records or Attendance records are missing.")
            if not students_df.empty:
                st.dataframe(students_df, width="stretch", hide_index=True)
                st.divider()
                st.subheader("Remove Student")
                with st.expander("Danger Zone: Delete Student Account"):
                    s_to_del = st.selectbox(
                        "Select Student to Remove",
                        options=["-"] + students_df["name"].astype(str).tolist()
                        if "name" in students_df.columns
                        else ["-"],
                        key="del_stu_box_no_attendance",
                    )
                    if s_to_del != "-":
                        stu_row = students_df[students_df["name"].astype(str) == s_to_del].iloc[0]
                        st.warning(
                            f"Are you sure you want to delete {s_to_del} ({stu_row.get('enrollment_no', 'N/A')})?"
                        )
                        if st.button("Confirm Delete Student", type="primary", key="confirm_delete_student_no_attendance"):
                            from src.database.db import delete_student

                            deleted = delete_student(stu_row["student_id"])
                            if deleted is not None:
                                st.success(f"Student {s_to_del} removed.")
                                st.rerun()
                            else:
                                st.error("Student delete nahi ho paya. Service role key/RLS settings check karo.")

    with tab_defaulters:
        st.write("### 🚨 Critical Attention Required (Attendance < 75%)")
        if not full_student_data.empty:
            df1, df2, df3 = st.columns(3)
            with df1:
                d_branch_filter = st.selectbox(
                    "Branch",
                    ["All"]
                    + list(
                        full_student_data.get("branch", pd.Series()).dropna().unique()
                    ),
                    key="d_branch",
                )
            with df2:
                d_sem_filter = st.selectbox(
                    "Semester",
                    ["All"]
                    + list(
                        full_student_data.get("semester", pd.Series()).dropna().unique()
                    ),
                    key="d_sem",
                )
            with df3:
                d_sec_filter = st.selectbox(
                    "Section",
                    ["All"]
                    + list(
                        full_student_data.get("section", pd.Series()).dropna().unique()
                    ),
                    key="d_sec",
                )

            defaulters_df = full_student_data[
                full_student_data["Attendance_%"] < 75.0
            ].sort_values(by="Attendance_%")

            if d_branch_filter != "All":
                defaulters_df = defaulters_df[
                    defaulters_df["branch"] == d_branch_filter
                ]
            if d_sem_filter != "All":
                defaulters_df = defaulters_df[defaulters_df["semester"] == d_sem_filter]
            if d_sec_filter != "All":
                defaulters_df = defaulters_df[defaulters_df["section"] == d_sec_filter]

            if defaulters_df.empty:
                st.success(
                    "Great news! No defaulters found with the selected filters. 🎉"
                )
            else:
                st.error(f"Found {len(defaulters_df)} students with low attendance.")
                st.dataframe(
                    defaulters_df.style.map(
                        lambda x: "color: red; font-weight: bold;",
                        subset=["Attendance_%"],
                    ),
                    width="stretch",
                    hide_index=True,
                )
        else:
            st.warning("Data not available.")

    with tab_teachers:
        st.write("### Faculty Directory")
        if not teachers_df.empty:
            # 🚀 FIX: Sabko Active mark kar diya
            teachers_df["Status"] = "✅ Active"

            # Use: Handles color status behavior in this module.
            # Linked with: Streamlit UI, decorators, tests, or external runtime calls.
            def color_status(val):
                return "color: green; font-weight: bold;"

            st.dataframe(
                teachers_df.style.map(color_status, subset=["Status"]),
                width="stretch",
                hide_index=True,
            )

            st.divider()
            st.subheader("🗑️ Remove Teacher")
            with st.expander("Set a New Teacher Password"):
                reset_teacher = st.selectbox(
                    "Select Teacher",
                    options=["-"] + teachers_df["name"].tolist(),
                    key="reset_teacher_box",
                )
                new_teacher_password = st.text_input(
                    "New Password",
                    type="password",
                    key="reset_teacher_password",
                )
                if reset_teacher != "-" and st.button("Update Teacher Password", type="secondary"):
                    if not new_teacher_password.strip():
                        st.warning("New password enter karo.")
                    else:
                        from src.database.db import update_teacher_password

                        reset_row = teachers_df[teachers_df["name"] == reset_teacher].iloc[0]
                        hashed_pass = bcrypt.hashpw(
                            new_teacher_password.strip().encode("utf-8"), bcrypt.gensalt()
                        ).decode("utf-8")
                        updated = update_teacher_password(reset_row["username"], hashed_pass)
                        if updated is not None:
                            st.success(
                                f"Password updated. Teacher login: {reset_row['username']} / {new_teacher_password.strip()}"
                            )
                        else:
                            st.error("Password update nahi hua. Service role key/RLS settings check karo.")

            with st.expander("Danger Zone: Delete Teacher Account"):
                t_to_del = st.selectbox("Select Teacher to Remove", options=["-"] + teachers_df["name"].tolist(), key="del_teach_box")
                if t_to_del != "-":
                    t_row = teachers_df[teachers_df["name"] == t_to_del].iloc[0]
                    st.warning(f"Are you sure you want to delete {t_to_del} ({t_row['username']})?")
                    if st.button("Confirm Delete Teacher", type="primary"):
                        from src.database.db import delete_teacher
                        deleted = delete_teacher(t_row["username"])
                        if deleted is not None:
                            st.success(f"Teacher {t_to_del} removed.")
                            st.rerun()
                        else:
                            st.error("Teacher delete nahi ho paya. Service role key/RLS settings check karo.")
        else:
            st.info("No teachers registered yet.")

    with tab_raw:
        st.write("### Master Attendance Log")
        if not df.empty:
            st.dataframe(df, width="stretch", hide_index=True)
