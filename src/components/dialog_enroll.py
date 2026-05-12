import streamlit as st


# Use: Handles enroll dialog behavior in this module.
# Linked with: Streamlit UI, decorators, tests, or external runtime calls.
@st.dialog("Subject Assignment")
def enroll_dialog():
    st.info(
        "Subject enrollment is automatic. Register your branch, semester, and section; matching subjects will appear when teachers create classes."
    )
    if st.button("Got it", type="primary", width="stretch"):
        st.rerun()
