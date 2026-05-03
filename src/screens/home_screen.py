import streamlit as st
from src.ui.base_layout import style_base_layout


def style_background_home():
    st.markdown(
        """
        <style>
            .stApp {
                background: #0F1117 !important;
                height: 100vh !important;
                overflow-y: auto !important;
            }
            .stApp div[data-testid="stColumn"]{
                background-color:#1A1D2E !important;
                border: 1px solid rgba(255,255,255,.08) !important;
                padding: 1.75rem 1.25rem 1.5rem !important;
                border-radius: 1.6rem !important;
                text-align: center;
            }
        </style>
    """,
        unsafe_allow_html=True,
    )


def home_screen():
    style_background_home()
    style_base_layout()

    # Blobs
    st.markdown(
        """
        <style>
        .stApp::before {
            content: '';position: fixed;
            width: 360px;height: 360px;border-radius: 50%;
            background: #6C63FF;filter: blur(90px);opacity: 0.22;
            top: -100px;left: -100px;pointer-events: none;z-index: 0;
        }
        .stApp::after {
            content: '';position: fixed;
            width: 300px;height: 300px;border-radius: 50%;
            background: #00C896;filter: blur(90px);opacity: 0.2;
            bottom: -80px;right: -80px;pointer-events: none;z-index: 0;
        }
        </style>
    """,
        unsafe_allow_html=True,
    )

    # Header
    logo_url = "https://i.ibb.co/YTYGn5qV/logo.png"
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Climate+Crisis:YEAR@1979&display=swap');
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600&display=swap');
        </style>
        <div style="display:flex;flex-direction:column;align-items:center;margin:1.5rem 0 2rem;z-index:2;position:relative;">
            <div style="width:80px;height:80px;border-radius:50%;background:rgba(108,99,255,.18);border:1.5px solid rgba(108,99,255,.4);display:flex;align-items:center;justify-content:center;margin-bottom:.9rem;">
                <img src='{logo_url}' style='width:54px;height:54px;object-fit:contain;'/>
            </div>
            <h1 style="font-family:'Climate Crisis',sans-serif;font-size:2.8rem;color:#F0F0FF;text-align:center;line-height:1;letter-spacing:.04em;margin:0;">SAGE<br/>CLASS</h1>
            <p style="font-size:.75rem;color:rgba(240,240,255,.4);margin-top:.5rem;letter-spacing:.18em;text-transform:uppercase;font-weight:300;font-family:'Outfit',sans-serif;">Attendance Management System</p>
            <div style="margin-top:.8rem;background:rgba(0,200,150,.12);border:1px solid rgba(0,200,150,.25);border-radius:99px;padding:4px 14px;font-size:.72rem;color:#00C896;letter-spacing:.08em;font-weight:500;font-family:'Outfit',sans-serif;">AI-Powered Face Recognition</div>
        </div>
    """,
        unsafe_allow_html=True,
    )

    # Portal Cards
    col1, col2 = st.columns(2, gap="large")

    with col1:
        st.markdown(
            """
            <div style="display:flex;flex-direction:column;align-items:center;gap:.6rem;padding:.5rem 0;">
                <span style="font-size:.62rem;font-weight:600;letter-spacing:.16em;text-transform:uppercase;padding:3px 10px;border-radius:99px;background:rgba(108,99,255,.15);color:#9B8FFF;border:1px solid rgba(108,99,255,.25);font-family:'Outfit',sans-serif;">Student</span>
                <img src='https://i.ibb.co/844D9Lrt/mascot-student.png' style='width:90px;height:90px;object-fit:contain;'/>
                <h2 style="font-family:'Climate Crisis',sans-serif;font-size:1.25rem;color:#F0F0FF;text-align:center;line-height:1.15;margin:0;">I'm a<br/>Student</h2>
                <p style="font-size:.76rem;color:rgba(240,240,255,.4);text-align:center;line-height:1.45;font-family:'Outfit',sans-serif;margin:0;">View your attendance &amp; records</p>
            </div>
        """,
            unsafe_allow_html=True,
        )
        if st.button("Enter Portal →", key="student_btn", use_container_width=True):
            st.session_state["login_type"] = "student"
            st.rerun()

    with col2:
        st.markdown(
            """
            <div style="display:flex;flex-direction:column;align-items:center;gap:.6rem;padding:.5rem 0;">
                <span style="font-size:.62rem;font-weight:600;letter-spacing:.16em;text-transform:uppercase;padding:3px 10px;border-radius:99px;background:rgba(0,200,150,.12);color:#00C896;border:1px solid rgba(0,200,150,.22);font-family:'Outfit',sans-serif;">Teacher</span>
                <img src='https://i.ibb.co/CsmQQV6X/mascot-prof.png' style='width:90px;height:100px;object-fit:contain;'/>
                <h2 style="font-family:'Climate Crisis',sans-serif;font-size:1.25rem;color:#F0F0FF;text-align:center;line-height:1.15;margin:0;">I'm a<br/>Teacher</h2>
                <p style="font-size:.76rem;color:rgba(240,240,255,.4);text-align:center;line-height:1.45;font-family:'Outfit',sans-serif;margin:0;">Mark &amp; manage class attendance</p>
            </div>
        """,
            unsafe_allow_html=True,
        )
        if st.button("Enter Portal →", key="teacher_btn", use_container_width=True):
            st.session_state["login_type"] = "teacher"
            st.rerun()

    # Divider
    st.markdown(
        """
        <div style="display:flex;align-items:center;gap:12px;margin:1.5rem 0 1.1rem;">
            <div style="flex:1;height:1px;background:rgba(255,255,255,.08);"></div>
            <span style="font-size:.68rem;color:rgba(240,240,255,.3);letter-spacing:.12em;text-transform:uppercase;font-family:'Outfit',sans-serif;">Admin Access</span>
            <div style="flex:1;height:1px;background:rgba(255,255,255,.08);"></div>
        </div>
    """,
        unsafe_allow_html=True,
    )

    # Admin Card HTML (UI only)
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600&display=swap');
        .admin-wrap {
            max-width: 520px;
            margin: 0 auto .5rem;
            background: #1A1D2E;
            border: 1px solid rgba(255,255,255,.08);
            border-radius: 1.4rem;
            padding: 1.25rem 1.5rem;
        }
        .admin-top { display:flex;align-items:center;gap:10px;margin-bottom:.75rem; }
        .admin-icon {
            width:38px;height:38px;border-radius:10px;
            background:rgba(255,107,107,.12);border:1px solid rgba(255,107,107,.22);
            display:flex;align-items:center;justify-content:center;font-size:17px;flex-shrink:0;
        }
        .admin-title { font-size:.9rem;font-weight:500;color:#F0F0FF;margin:0;font-family:'Outfit',sans-serif; }
        .admin-sub { font-size:.72rem;color:rgba(240,240,255,.35);margin:0;font-family:'Outfit',sans-serif; }

        /* Hidden streamlit widgets style karo */
        .admin-real .stTextInput input {
            background: rgba(255,255,255,.06) !important;
            border: 1px solid rgba(255,255,255,.1) !important;
            border-radius: 10px !important;
            color: #F0F0FF !important;
            font-family: 'Outfit', sans-serif !important;
            font-size: .85rem !important;
        }
        .admin-real .stTextInput input::placeholder { color: rgba(240,240,255,.28) !important; }
        .admin-real .stTextInput input:focus { border-color: rgba(255,107,107,.45) !important; box-shadow: none !important; }
        .admin-real .stTextInput label { display: none !important; }
        div[data-testid="InputInstructions"] { display: none !important; }
        .admin-real button {
            background: #2A2D3E !important;
            border: 1px solid rgba(255,255,255,.1) !important;
            color: #F0F0FF !important;
            border-radius: 10px !important;
            font-family: 'Outfit', sans-serif !important;
        }
        .admin-real button:hover { background: #33364A !important; }
        </style>

        <div class="admin-wrap">
            <div class="admin-top">
                <div class="admin-icon">🔒</div>
                <div>
                    <p class="admin-title">System Admin Panel</p>
                    <p class="admin-sub">Identity verification required</p>
                </div>
            </div>
        </div>
    """,
        unsafe_allow_html=True,
    )

    # Actual working Streamlit input+button (styled to match)
    left, mid, right = st.columns([0.001, 3, 0.001])
    with mid:
        with st.container():
            st.markdown('<div class="admin-real">', unsafe_allow_html=True)

            inp_col, btn_col = st.columns([3, 1])
            with inp_col:
                admin_pass = st.text_input(
                    "admin_pass",
                    type="password",
                    placeholder="Enter master password...",
                    label_visibility="collapsed",
                    key="admin_pass_key",
                )
            with btn_col:
                unlock = st.button(
                    "🔑 Unlock", use_container_width=True, key="admin_unlock"
                )

            st.markdown("</div>", unsafe_allow_html=True)

    if unlock:
        if not admin_pass:
            st.warning("Password cannot be empty")
        elif admin_pass == st.secrets.get("ADMIN_PASSWORD", ""):
            st.session_state["login_type"] = "admin"
            st.session_state["is_logged_in"] = True
            st.session_state["user_role"] = "admin"
            st.toast("Access Granted", icon="🔓")
            import time

            time.sleep(1)
            st.rerun()
        else:
            st.error("Invalid secret key")

    # Footer
    st.markdown(
        """
        <div style="text-align:center;margin-top:1.2rem;">
            <p style="font-size:.75rem;color:rgba(240,240,255,.25);font-family:'Outfit',sans-serif;letter-spacing:.05em;">
                Created with <span style='color:#FF6B6B'>♥</span> by Team Apex
            </p>
        </div>
    """,
        unsafe_allow_html=True,
    )
