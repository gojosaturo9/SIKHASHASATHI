import streamlit as st
from src.database.config import supabase
from src.database.db import create_attendance


from datetime import datetime
from src.utils.notifier import notify_students_bg

def show_attendance_result(df, logs):
    st.write('Please review attendance before confirming.')
    st.dataframe(df, hide_index=True, width='stretch')

    col1, col2 = st.columns(2)

    with col1:
        if st.button('Discard', width='stretch'):
            st.session_state.voice_attendance_results = None
            st.session_state.attendance_images = []
            st.rerun()

    with col2:
        if st.button('Confirm & Save', width='stretch', type='primary'):
            try:
                # 1. Pehle database me save hoga
                create_attendance(logs)
                
                # 👇 2. EMAIL BHEJNE KA LOGIC YAHAN AAYEGA
                today_date = datetime.now().strftime("%d %b %Y")
                
                # DataFrame (df) ko dictionary ki list me convert kiya taaki loop chal sake
                records = df.to_dict('records') 
                
                # Background me email bhejne wala function call kiya
                # (Note: Abhi 'Your Class' likha hai, aap chaho toh subject pass kar sakte ho)
                notify_students_bg(records, "Your Class", today_date) 
                
                # Success message update kar diya
                st.toast("Attendance taken & Emails sent! 🚀")
                
                # 3. State clear aur rerun
                st.session_state.attendance_images = []
                st.session_state.voice_attendance_results = None
                st.rerun()
                
            except Exception as e:
                st.error(f'Sync failed! Error: {e}')

@st.dialog("Attendance Reports")
def attendance_result_dialog(df, logs):
    show_attendance_result(df, logs)