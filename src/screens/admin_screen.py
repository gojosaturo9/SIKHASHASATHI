import streamlit as st
import pandas as pd
import random
import string
import bcrypt  # 🚀 Password hash karne ke liye
from src.database.config import supabase
from src.database.db import get_all_attendance_records

# 🚀 FIX: Naya email function import kiya
from src.utils.notifier import send_teacher_credentials_email
from src.ui.base_layout import style_base_layout
from src.components.footer import footer_dashboard
from src.components.ai_insights import render_ai_insights


# --- 🚀 NAYA FIX: ADD TEACHER TAB (Purana verification tab hata diya) ---
def add_teacher_tab():
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
                            supabase.table("teachers").insert(
                                {
                                    "name": t_name,
                                    "username": t_username,
                                    "email_id": t_email,
                                    "password": hashed_pass,
                                }
                            ).execute()

                            # 5. Send Email with Credentials
                            send_teacher_credentials_email(
                                t_email, t_name, t_username, raw_pass
                            )

                            st.success(f"✅ Account for {t_name} created successfully!")
                            st.info(f"Credentials have been emailed to {t_email}")
                        except Exception as e:
                            st.error(f"⚠️ Error creating account: {e}")


def admin_dashboard():
    style_base_layout()
    st.title("🛡️ Admin Control Panel")

    if st.button("Logout", type="secondary", icon=":material/logout:"):
        st.session_state["is_logged_in"] = False
        st.session_state["user_role"] = None
        st.session_state["login_type"] = None

        if "teacher_data" in st.session_state:
            del st.session_state["teacher_data"]

        st.toast("Logged out successfully!")
        st.rerun()

    st.divider()

    # 🚀 FIX: Tab ka naam change kar diya
    tab1, tab2, tab3 = st.tabs(
        ["👨‍🏫 Add Teacher", "📊 Attendance Analytics", "AI Insights"]
    )

    with tab1:
        add_teacher_tab()  # 🚀 FIX: Naya function call kiya
    with tab2:
        attendance_analytics_tab()
    with tab3:
        render_ai_insights()

    footer_dashboard()


def attendance_analytics_tab():
    st.header("📊 Deep Analytics & College Dashboard")

    records = get_all_attendance_records()
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
        else:
            st.warning("Either Student records or Attendance records are missing.")

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

            def color_status(val):
                return "color: green; font-weight: bold;"

            st.dataframe(
                teachers_df.style.map(color_status, subset=["Status"]),
                width="stretch",
                hide_index=True,
            )
        else:
            st.info("No teachers registered yet.")

    with tab_raw:
        st.write("### Master Attendance Log")
        if not df.empty:
            st.dataframe(df, width="stretch", hide_index=True)
