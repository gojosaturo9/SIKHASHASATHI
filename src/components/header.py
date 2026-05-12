import streamlit as st
from pathlib import Path
import base64


# Use: Internal helper for logo src.
# Linked with: header_dashboard, header_home
def _logo_src():
    logo_path = Path(__file__).resolve().parents[1] / "assets" / "logo1.png"
    if not logo_path.exists():
        return "https://i.ibb.co/YTYGn5qV/logo.png"
    encoded = base64.b64encode(logo_path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


# Use: Handles header home behavior in this module.
# Linked with: home_screen
def header_home():
    logo_src = _logo_src()
    st.markdown(
        f"""
        <div class="ss-home-brand">
            <div class="ss-logo-mark">
                <img src="{logo_src}" alt="SIKHASHASASATHI logo" />
            </div>
            <div class="ss-eyebrow"><span></span> Professional AI Solution <span></span></div>
            <h1>AI-Powered<br><strong>Attendance</strong><br><em>System</em></h1>
            <p>Computer vision, voice biometrics, QR enrollment, and clean attendance records for every classroom role.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


# Use: Handles header dashboard behavior in this module.
# Linked with: student_dashboard, student_screen, teacher_dashboard, teacher_screen, teacher_screen_login
def header_dashboard():
    logo_src = _logo_src()
    st.markdown(
        f"""
        <div class="ss-dashboard-brand">
            <img src="{logo_src}" alt="SIKHASHASASATHI logo" />
            <div>
                <strong>SIKHASHASASATHI</strong>
                <span>AI Powered Attendance</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
