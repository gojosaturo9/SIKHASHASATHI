import streamlit as st
import pandas as pd
from src.database.config import supabase
from src.database.db import get_all_attendance_records
from src.utils.notifier import send_verification_mail
from src.ui.base_layout import style_base_layout
from src.components.footer import footer_dashboard


def teacher_verification_tab():
    st.header("Pending Teacher Approvals")

    # Fetch teachers where is_verified = false
    response = supabase.table("teachers").select("*").eq("is_verified", False).execute()
    pending_teachers = response.data

    if not pending_teachers:
        st.info("🎉 All caught up! No pending teacher approvals at the moment.")
        return

    for t in pending_teachers:
        with st.container(border=True):
            # Layout ko 3 columns mein baanta hai taaki buttons side-by-side aayein
            col1, col2, col3 = st.columns([2, 1, 1], vertical_alignment="center")

            with col1:
                st.write(f"**Name:** {t['name']} | **Username:** {t['username']}")
                st.caption(f"Email: {t.get('email_id', 'No Email')}")

            with col2:
                if st.button(
                    "Approve ✅",
                    key=f"app_{t['username']}",
                    type="primary",
                    width='stretch',
                ):
                    # 1. Update DB to Verified
                    supabase.table("teachers").update({"is_verified": True}).eq(
                        "username", t["username"]
                    ).execute()

                    # 2. Approval Mail
                    if t.get("email_id"):
                        send_verification_mail(t["email_id"], t["name"], True)

                    st.toast(f"Verified {t['name']} successfully!")
                    st.rerun()

            with col3:
                # Naya Reject Button (Secondary/Danger feel ke liye)
                if st.button(
                    "Reject ❌",
                    key=f"rej_{t['username']}",
                    type="secondary",
                    width='stretch',
                ):
                    # 1. Database se teacher ko delete kar dein
                    supabase.table("teachers").delete().eq(
                        "username", t["username"]
                    ).execute()

                    # 2. Rejection Mail (Optionally teacher ko batane ke liye ki unhe reject kiya gaya)
                    if t.get("email_id"):
                        send_verification_mail(t["email_id"], t["name"], False)

                    st.error(f"Rejected and deleted {t['name']}")
                    import time

                    time.sleep(1)
                    st.rerun()


# Yeh main function hai jo app.py se call hoga
def admin_dashboard():
    style_base_layout()
    st.title("🛡️ Admin Control Panel")

    if st.button("Logout", type="secondary", icon=":material/logout:"):
        # 1. Saare relevant session states ko saaf karein
        st.session_state["is_logged_in"] = False
        st.session_state["user_role"] = None
        st.session_state["login_type"] = None  # 👈 Yeh line sabse zaruri hai

        # 2. Agar koi purana data hai toh use bhi clear kar dein
        if "teacher_data" in st.session_state:
            del st.session_state["teacher_data"]

        st.toast("Logged out successfully!")
        st.rerun()

    st.divider()

    tab1, tab2 = st.tabs(["👨‍🏫 Teacher Verification", "📊 Attendance Analytics"])

    with tab1:
        teacher_verification_tab()
    with tab2:
        attendance_analytics_tab()

    footer_dashboard()














def attendance_analytics_tab():
    st.header("📊 Deep Analytics & College Dashboard")

    # 1. Fetch Attendance Records
    records = get_all_attendance_records()
    df = pd.DataFrame(records) if records else pd.DataFrame()

    # 2. Fetch Teacher & Student Details directly from Database
    try:
        teachers_data = supabase.table("teachers").select("name, username, email_id, is_verified").execute().data
        students_data = supabase.table("students").select("*").execute().data
        
        teachers_df = pd.DataFrame(teachers_data)
        students_df = pd.DataFrame(students_data)
        
        # 🚀 FIX: Remove heavy/unnecessary columns like face/voice embeddings
        cols_to_drop = ["face_embedding", "voice_embedding", "face_encodings", "voice_data"]
        students_df = students_df.drop(columns=[c for c in cols_to_drop if c in students_df.columns], errors='ignore')

    except Exception as e:
        st.error(f"Database Error: Could not fetch extra details - {e}")
        teachers_df = pd.DataFrame()
        students_df = pd.DataFrame()

    if df.empty and students_df.empty:
        st.warning("No records found in the database yet.")
        return

    # --- TOP LEVEL METRICS (KPIs) ---
    st.subheader("Key Performance Indicators")
    m1, m2, m3, m4 = st.columns(4)

    with m1:
        total_students = len(students_df) if not students_df.empty else (df["Student Name"].nunique() if not df.empty else 0)
        st.metric("Total Enrolled Students 🎓", total_students)
    with m2:
        total_teachers = len(teachers_df[teachers_df["is_verified"] == True]) if not teachers_df.empty else 0
        st.metric("Verified Teachers 👨‍🏫", total_teachers)
    with m3:
        total_days = df["Date"].nunique() if not df.empty else 0
        st.metric("Total Class Days 📅", total_days)
    with m4:
        avg_attendance = (df["Status"] == "✅ Present").mean() * 100 if not df.empty else 0
        st.metric("College Avg. Attendance", f"{avg_attendance:.1f}%")

    st.divider()

    # --- 5 DETAILED TABS ---
    tab_overview, tab_students, tab_defaulters, tab_teachers, tab_raw = st.tabs([
        "📈 Analytics Overview", 
        "🎓 Student Directory", 
        "🚨 Defaulters List",
        "👨‍🏫 Teacher Directory", 
        "📄 Raw Data"
    ])

    # ----------------------------------------
    # TAB 1: ATTENDANCE OVERVIEW (IMPROVED CHARTS)
    # ----------------------------------------
    with tab_overview:
        if not df.empty:
            c1, c2 = st.columns(2)
            
            with c1:
                st.write("#### 📊 Branch-wise Student Strength")
                branch_counts = df.groupby("branch")["Student Name"].nunique()
                st.bar_chart(branch_counts, color="#0984e3")

            with c2:
                st.write("#### 📈 Daily Attendance Trend")
                daily_trend = df[df["Status"] == "✅ Present"].groupby("Date").count()["Status"]
                st.line_chart(daily_trend, color="#00b894")
                
            st.divider()
            
            # Naya Chart: Subject Wise Performance
            st.write("#### 📚 Subject-wise Average Attendance (%)")
            if "Subject" in df.columns:
                # Calculate percentage of present students per subject
                subject_stats = df.groupby("Subject").apply(
                    lambda x: (x["Status"] == "✅ Present").mean() * 100
                ).round(1)
                st.bar_chart(subject_stats, color="#fdcb6e")
        else:
            st.info("Not enough attendance data for charts.")

    # --- MASTER CALCULATION FOR STUDENTS & DEFAULTERS ---
    if not students_df.empty and not df.empty:
        student_report = df.groupby("Student Name").agg(
            Total_Classes=("Status", "count"),
            Present_Days=("Status", lambda x: (x == "✅ Present").sum()),
        ).reset_index()
        
        student_report["Present_Days"] = student_report["Present_Days"].astype(float)
        student_report["Total_Classes"] = student_report["Total_Classes"].astype(float)
        student_report["Attendance_%"] = (student_report["Present_Days"] / student_report["Total_Classes"] * 100).round(1)

        col_to_merge = 'name' if 'name' in students_df.columns else students_df.columns[0]
        full_student_data = pd.merge(students_df, student_report, left_on=col_to_merge, right_on="Student Name", how="left")
        full_student_data.fillna({"Total_Classes": 0, "Present_Days": 0, "Attendance_%": 0.0}, inplace=True)
        
        if "Student Name" in full_student_data.columns:
            full_student_data.drop(columns=["Student Name"], inplace=True)

        def color_low_attendance(val):
            if pd.isna(val): return ''
            color = "red" if float(val) < 75 else "green"
            return f"color: {color}; font-weight: bold;"
            
    else:
        full_student_data = pd.DataFrame()

    # ----------------------------------------
    # TAB 2: STUDENT DIRECTORY
    # ----------------------------------------
    with tab_students:
        st.write("### Complete Student Profiles & Attendance Stats")
        
        if not full_student_data.empty:
            search_stu = st.text_input("🔍 Search Student Name/Roll No", placeholder="Type here...", key="search_all")
            
            # --- ADDED FILTERS HERE ---
            f1, f2, f3 = st.columns(3)
            with f1:
                branch_filter = st.selectbox("Branch", ["All"] + list(full_student_data.get("branch", pd.Series()).dropna().unique()), key="branch_all")
            with f2:
                sem_filter = st.selectbox("Semester", ["All"] + list(full_student_data.get("semester", pd.Series()).dropna().unique()), key="sem_all")
            with f3:
                sec_filter = st.selectbox("Section", ["All"] + list(full_student_data.get("section", pd.Series()).dropna().unique()), key="sec_all")
            
            display_df = full_student_data.copy()
            
            # Apply Filters
            if branch_filter != "All":
                display_df = display_df[display_df["branch"] == branch_filter]
            if sem_filter != "All":
                display_df = display_df[display_df["semester"] == sem_filter]
            if sec_filter != "All":
                display_df = display_df[display_df["section"] == sec_filter]

            if search_stu:
                display_df = display_df[display_df.astype(str).apply(lambda x: x.str.contains(search_stu, case=False)).any(axis=1)]

            st.dataframe(
                display_df.style.map(color_low_attendance, subset=["Attendance_%"]),
                width="stretch",
                hide_index=True,
            )
        else:
            st.warning("Either Student records or Attendance records are missing.")

    # ----------------------------------------
    # TAB 3: DEFAULTERS LIST (< 75%)
    # ----------------------------------------
    with tab_defaulters:
        st.write("### 🚨 Critical Attention Required (Attendance < 75%)")
        
        if not full_student_data.empty:
            
            # --- ADDED FILTERS HERE AS WELL ---
            df1, df2, df3 = st.columns(3)
            with df1:
                d_branch_filter = st.selectbox("Branch", ["All"] + list(full_student_data.get("branch", pd.Series()).dropna().unique()), key="d_branch")
            with df2:
                d_sem_filter = st.selectbox("Semester", ["All"] + list(full_student_data.get("semester", pd.Series()).dropna().unique()), key="d_sem")
            with df3:
                d_sec_filter = st.selectbox("Section", ["All"] + list(full_student_data.get("section", pd.Series()).dropna().unique()), key="d_sec")
                
            defaulters_df = full_student_data[full_student_data["Attendance_%"] < 75.0].sort_values(by="Attendance_%")
            
            # Apply Filters
            if d_branch_filter != "All":
                defaulters_df = defaulters_df[defaulters_df["branch"] == d_branch_filter]
            if d_sem_filter != "All":
                defaulters_df = defaulters_df[defaulters_df["semester"] == d_sem_filter]
            if d_sec_filter != "All":
                defaulters_df = defaulters_df[defaulters_df["section"] == d_sec_filter]
            
            if defaulters_df.empty:
                st.success("Great news! No defaulters found with the selected filters. 🎉")
            else:
                st.error(f"Found {len(defaulters_df)} students with low attendance.")
                st.dataframe(
                    defaulters_df.style.map(lambda x: "color: red; font-weight: bold;", subset=["Attendance_%"]),
                    width="stretch",
                    hide_index=True,
                )
        else:
             st.warning("Data not available.")

    # ----------------------------------------
    # TAB 4: TEACHER DIRECTORY
    # ----------------------------------------
    with tab_teachers:
        st.write("### Faculty Directory")
        if not teachers_df.empty:
            teachers_df["Status"] = teachers_df["is_verified"].apply(lambda x: "✅ Active" if x else "⏳ Pending")
            display_teachers = teachers_df.drop(columns=["is_verified"])
            
            def color_status(val):
                color = "green" if "Active" in str(val) else "orange"
                return f"color: {color}; font-weight: bold;"

            st.dataframe(
                display_teachers.style.map(color_status, subset=["Status"]),
                width="stretch",
                hide_index=True,
            )
        else:
            st.info("No teachers registered yet.")

    # ----------------------------------------
    # TAB 5: RAW DATA LOGS
    # ----------------------------------------
    with tab_raw:
        st.write("### Master Attendance Log")
        if not df.empty:
            st.dataframe(df, width="stretch", hide_index=True)