import streamlit as st


# Use: Handles footer home behavior in this module.
# Linked with: home_screen
def footer_home():
    st.markdown(
        """
        <div class="ss-footer-note">
            <span>Created with Apex Coders.</span>
            <span>Copyright 2026 SIKHASHASASATHI</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


# Use: Handles footer dashboard behavior in this module.
# Linked with: admin_dashboard, student_dashboard, student_screen, teacher_dashboard, teacher_screen, teacher_screen_login
def footer_dashboard():
    st.markdown(
        """
        <div class="ss-footer-note ss-footer-dashboard">
            <span>Created with Apex Coders.</span>
            <span>Copyright 2026 SIKHASHASASATHI</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
