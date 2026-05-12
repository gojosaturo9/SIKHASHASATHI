import streamlit as st


# Use: Handles auto enroll dialog behavior in this module.
# Linked with: main
@st.dialog("Subject Assignment")
def auto_enroll_dialog(subject_code):
    st.info(
        "Students are assigned automatically from their registered branch, semester, and section. No subject code enrollment is required."
    )
    st.caption(f"Scanned code: {subject_code}")
    if st.button("Got it", type="primary", width="stretch"):
        st.query_params.clear()
        st.rerun()
