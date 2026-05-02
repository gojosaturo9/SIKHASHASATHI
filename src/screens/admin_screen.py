import streamlit as st
import pandas as pd
from src.database.config import supabase
from src.database.db import get_all_attendance_records
from src.utils.notifier import send_verification_mail
from src.ui.base_layout import style_base_layout


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
                    use_container_width=True,
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
                    use_container_width=True,
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


def attendance_analytics_tab():
    st.header("Global Attendance Analytics")

    # Get all attendance records joined with students and subjects
    records = get_all_attendance_records()

    if not records:
        st.warning("No attendance records found yet!")
        return

    df = pd.DataFrame(records)

    # Filters (Using 'smester' exactly as it is in your DB)
    col1, col2, col3 = st.columns(3)
    with col1:
        branch_list = ["All"] + list(df["branch"].dropna().unique())
        branch = st.selectbox("Branch", branch_list)
    with col2:
        sem_list = ["All"] + list(df["semester"].dropna().unique())
        sem = st.selectbox("Semester", sem_list)
    with col3:
        sec_list = ["All"] + list(df["section"].dropna().unique())
        sec = st.selectbox("Section", sec_list)

    # Apply Filters
    filtered_df = df.copy()
    if branch != "All":
        filtered_df = filtered_df[filtered_df["branch"] == branch]
    if sem != "All":
        filtered_df = filtered_df[filtered_df["semester"] == sem]
    if sec != "All":
        filtered_df = filtered_df[filtered_df["section"] == sec]

    st.dataframe(filtered_df, use_container_width=True, hide_index=True)


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
