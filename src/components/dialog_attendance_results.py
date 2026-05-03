import streamlit as st
import pandas as pd
from src.database.db import create_attendance
from datetime import datetime
from src.utils.notifier import (
    notify_students_bg,
)  # confirm karein notifier.py ka path yahi hai
import time


def show_attendance_result(df, logs, subject_name):
    st.write("Please review attendance before confirming.")

    # 🚀 Naya UI Fix: Attendance summary dikhao
    present_count = len(df[df["is_present"] == True])
    absent_count = len(df[df["is_present"] == False])
    st.info(
        f"📊 Summary for **{subject_name}**: {present_count} Present, {absent_count} Absent"
    )

    st.dataframe(df, hide_index=True, width="stretch")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Discard", width="stretch"):
            st.session_state.voice_attendance_results = None
            st.session_state.attendance_images = []
            st.rerun()

    with col2:
        if st.button("Confirm & Save", width="stretch", type="primary"):
            try:
                # 1. Database me save logic
                create_attendance(logs)

                # 🚀 2. DYNAMIC EMAIL LOGIC
                today_date = datetime.now().strftime("%d %b %Y")

                # DataFrame ko records me convert kiya taaki notifier.py ko sahi data mile
                # Ensure karein ki df me 'email_id' aur 'Name' columns maujood hain
                records = df.to_dict("records")

                # Background notification call with real subject name
                notify_students_bg(records, subject_name, today_date)

                st.toast(f"Attendance saved for {subject_name} & Emails queued! 🚀")

                # 3. Cleanup
                st.session_state.attendance_images = []
                st.session_state.voice_attendance_results = None
                time.sleep(1.5)  # User ko toast padhne ka time mile
                st.rerun()

            except Exception as e:
                st.error(f"Sync failed! Error: {e}")


@st.dialog("Attendance Reports")
def attendance_result_dialog(df, logs, subject_name="Selected Subject"):
    show_attendance_result(df, logs, subject_name)
