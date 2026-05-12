import streamlit as st

from src.components.footer import footer_home
from src.components.header import header_home
from src.ui.base_layout import style_background_home, style_base_layout


# Use: Internal helper for style home screen.
# Linked with: home_screen
def _style_home_screen():
    # Home styles now live in src/ui/styles.css under "7. Home Section".
    return
    st.markdown(
        """
        <style>
            .block-container {
                max-width: 1120px;
                padding-top: 3.4rem !important;
            }

            div[data-testid="column"] {
                min-width: 0;
            }

            .ss-home-brand {
                position: relative;
                z-index: 1;
                max-width: 760px;
                margin: 0 auto 2.4rem;
                text-align: center;
            }

            .ss-logo-mark {
                display: grid;
                width: 74px;
                height: 74px;
                place-items: center;
                margin: 0 auto 1.15rem;
                border: 1px solid var(--ss-border);
                border-radius: 8px;
                background: var(--ss-glass);
                box-shadow: var(--ss-shadow);
                backdrop-filter: blur(18px);
            }

            .ss-logo-mark img {
                width: 52px;
                height: 52px;
                object-fit: contain;
            }

            .ss-eyebrow {
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 0.75rem;
                margin-bottom: 1.15rem;
                color: var(--ss-accent);
                font-size: 0.78rem;
                font-weight: 800;
                text-transform: uppercase;
            }

            .ss-eyebrow span {
                width: 40px;
                height: 1px;
                background: var(--ss-accent);
            }

            .ss-home-brand h1 {
                margin: 0 !important;
            }

            .ss-home-brand h1 strong {
                color: var(--ss-accent);
            }

            .ss-home-brand h1 em {
                color: var(--ss-text);
                font-style: normal;
            }

            .ss-home-brand p {
                max-width: 620px;
                margin: 1.25rem auto 0 !important;
                color: var(--ss-muted) !important;
                font-size: 1rem !important;
                line-height: 1.75;
            }

            .ss-portal-card {
                position: relative;
                overflow: hidden;
                min-height: 274px;
                padding: 1.75rem;
                border: 1px solid var(--ss-border);
                border-radius: 8px;
                background: var(--ss-card);
                text-align: left;
                box-shadow: var(--ss-shadow);
                backdrop-filter: blur(18px);
            }

            .ss-portal-card::before {
                content: "";
                position: absolute;
                inset: 0 0 auto 0;
                height: 3px;
                background: linear-gradient(90deg, var(--ss-accent), transparent);
            }

            .ss-portal-card .ss-card-icon {
                display: grid;
                width: 54px;
                height: 54px;
                place-items: center;
                margin-bottom: 1.25rem;
                border: 1px solid var(--ss-border);
                border-radius: 8px;
                background: rgba(0, 229, 229, 0.1);
                color: var(--ss-accent);
                font-weight: 900;
            }

            .ss-portal-card h3 {
                margin: 0 0 0.65rem !important;
                font-size: 1.25rem !important;
            }

            .ss-portal-card p {
                min-height: 4.2rem;
                margin: 0 0 1.1rem !important;
                color: var(--ss-muted) !important;
                font-size: 0.88rem !important;
                line-height: 1.65;
            }

            .ss-card-list {
                display: flex;
                flex-wrap: wrap;
                gap: 0.45rem;
                margin-top: 1.15rem;
            }

            .ss-card-list span {
                padding: 0.28rem 0.55rem;
                border: 1px solid rgba(0, 229, 229, 0.18);
                border-radius: 7px;
                background: rgba(0, 229, 229, 0.07);
                color: var(--ss-muted);
                font-size: 0.72rem;
                font-weight: 700;
            }

            .ss-admin-panel {
                max-width: 560px;
                margin: 2.1rem auto 0.35rem;
                padding: 1.35rem 1.45rem;
                border: 1px solid var(--ss-border);
                border-radius: 8px;
                background: var(--ss-card);
                box-shadow: var(--ss-shadow);
                backdrop-filter: blur(18px);
            }

            .ss-admin-panel h3 {
                margin: 0 0 0.2rem !important;
                font-size: 1rem !important;
            }

            .ss-admin-panel p {
                margin: 0 0 0.9rem !important;
                color: var(--ss-muted) !important;
                font-size: 0.82rem !important;
            }

            .ss-value-strip {
                display: flex;
                flex-wrap: wrap;
                justify-content: center;
                gap: 0.8rem;
                margin: 2.4rem 0;
                padding: 1.15rem;
                border-top: 1px solid var(--ss-border);
                border-bottom: 1px solid var(--ss-border);
                background: rgba(0, 229, 229, 0.05);
            }

            .ss-value-strip span {
                color: var(--ss-muted);
                font-size: 0.78rem;
                font-weight: 800;
                text-transform: uppercase;
            }

            .ss-admin-input-wrap {
                max-width: 560px;
                margin: 0 auto;
            }

            @media (max-width: 720px) {
                .block-container {
                    padding-top: 2rem !important;
                }

                .stButton > button {
                    position: relative;
                    bottom: auto;
                }

                .ss-home-brand {
                    margin-bottom: 1.7rem;
                }

                .ss-eyebrow span {
                    width: 24px;
                }

                .ss-portal-card {
                    min-height: auto;
                    padding: 1.35rem;
                }

                .ss-portal-card p {
                    min-height: auto;
                }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


# Use: Internal helper for portal card.
# Linked with: home_screen
def _portal_card(role, title, body, chips):
    chips_html = "".join(f"<span>{chip}</span>" for chip in chips)
    st.markdown(
        f"""
        <article class="ss-portal-card">
            <div class="ss-card-icon">{role}</div>
            <h3>{title}</h3>
            <p>{body}</p>
            <div class="ss-card-list">{chips_html}</div>
        </article>
        """,
        unsafe_allow_html=True,
    )


# Use: Internal helper for enter portal.
# Linked with: home_screen
def _enter_portal(role):
    st.session_state["login_type"] = role
    st.session_state["is_logged_in"] = False
    st.session_state["user_role"] = None

    if role == "student":
        st.session_state.pop("teacher_data", None)
    elif role == "teacher":
        st.session_state.pop("student_data", None)

    st.rerun()


# Use: Handles home screen behavior in this module.
# Linked with: main
def home_screen():
    style_background_home()
    style_base_layout()
    _style_home_screen()

    header_home()

    col1, col2 = st.columns(2, gap="large")

    with col1:
        _portal_card(
            "ST",
            "Student Portal",
            "Enroll through QR codes, register biometrics, and view subject-wise attendance records.",
            ["Face login", "QR enrollment", "Attendance status"],
        )
        if st.button(
            "Enter Student Portal",
            key="student_btn",
            type="primary",
            use_container_width=True,
        ):
            _enter_portal("student")

    with col2:
        _portal_card(
            "TR",
            "Teacher Portal",
            "Create courses, share roster links, run face or voice attendance, and confirm records.",
            ["Course setup", "Face AI", "Voice roll-call"],
        )
        if st.button(
            "Enter Teacher Portal",
            key="teacher_btn",
            type="primary",
            use_container_width=True,
        ):
            _enter_portal("teacher")

    st.markdown(
        """
        <div class="ss-value-strip">
            <span>Face Recognition</span>
            <span>Voice Biometrics</span>
            <span>QR Enrollment</span>
            <span>Cloud Records</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="ss-admin-panel">
            <h3>Administrator Access</h3>
            <p>Use the master key to open the control panel for teacher setup and attendance analytics.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="ss-admin-input-wrap">', unsafe_allow_html=True)
    left, mid, right = st.columns([0.001, 1, 0.001])
    with mid:
        inp_col, btn_col = st.columns([3, 1])
        with inp_col:
            admin_pass = st.text_input(
                "Admin password",
                type="password",
                placeholder="Enter master password",
                label_visibility="collapsed",
                key="admin_pass_key",
            )
        with btn_col:
            unlock = st.button("Unlock", use_container_width=True, key="admin_unlock")
    st.markdown("</div>", unsafe_allow_html=True)

    if unlock:
        if not admin_pass:
            st.warning("Password cannot be empty")
        elif admin_pass == st.secrets.get("ADMIN_PASSWORD", ""):
            st.session_state["login_type"] = "admin"
            st.session_state["is_logged_in"] = True
            st.session_state["user_role"] = "admin"
            st.toast("Access granted")
            st.rerun()
        else:
            st.error("Invalid secret key")

    footer_home()
