from pathlib import Path

import streamlit as st


# Use: Internal helper for load stylesheet.
# Linked with: style_background_home, style_base_layout
def _load_stylesheet():
    return (Path(__file__).with_name("styles.css")).read_text(encoding="utf-8")


# Use: Handles style background home behavior in this module.
# Linked with: home_screen
def style_background_home():
    st.markdown(
        """
        <style>
            .stApp, [data-testid="stAppViewContainer"] {
                background:
                    radial-gradient(circle at 18% 8%, rgba(0, 229, 229, 0.14), transparent 30%),
                    linear-gradient(145deg, #050607 0%, #0b0f12 50%, #101418 100%) !important;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(f"<style>{_load_stylesheet()}</style>", unsafe_allow_html=True)


# Use: Handles style background dashboard behavior in this module.
# Linked with: admin_dashboard, student_screen, teacher_screen
def style_background_dashboard():
    st.markdown(
        """
        <style>
            .stApp, [data-testid="stAppViewContainer"] {
                background:
                    radial-gradient(circle at 12% 0%, rgba(0, 229, 229, 0.12), transparent 28%),
                    linear-gradient(145deg, #050607 0%, #0b0f12 52%, #101418 100%) !important;
            }
            .stApp {
                overflow-y: auto !important;
                min-height: 100vh !important;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


# Use: Handles apply attendance theme behavior in this module.
# Linked with: student_dashboard
def apply_attendance_theme(percentage):
    """Applies a subtle red, yellow, or green glow based on attendance percentage."""
    if percentage < 50:
        glow_color = "rgba(255, 71, 87, 0.15)"  # Soft Red
        accent_color = "#FF4757"
    elif percentage < 75:
        glow_color = "rgba(255, 175, 64, 0.12)"  # Soft Yellow
        accent_color = "#FFAF40"
    else:
        glow_color = "rgba(40, 200, 100, 0.12)"  # Soft Green
        accent_color = "#28C864"

    st.markdown(
        f"""
        <style>
            .stApp, [data-testid="stAppViewContainer"] {{
                background:
                    radial-gradient(circle at 12% 0%, {glow_color}, transparent 30%),
                    linear-gradient(145deg, #050607 0%, #0b0f12 52%, #101418 100%) !important;
            }}
            :root {{
                --ss-status: {accent_color};
                --ss-status-glow: {glow_color.replace('0.15', '0.4').replace('0.12', '0.4')};
            }}
            .ss-subject-card::before {{
                background: var(--ss-status) !important;
            }}
        </style>
        """,
        unsafe_allow_html=True,
    )


# Use: Handles style base layout behavior in this module.
# Linked with: admin_dashboard, home_screen, student_screen, teacher_screen
def style_base_layout():
    st.markdown(
        """
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
        
        <style>
            :root {
                --ss-bg: #050607;
                --ss-bg-deep: #020303;
                --ss-accent: #00E5E5;
                --ss-cyan: #00E5E5;
                --ss-accent-glow: rgba(0, 229, 229, 0.34);
                --ss-surface: rgba(17, 23, 28, 0.74);
                --ss-surface-solid: #12181d;
                --ss-card: rgba(16, 22, 27, 0.68);
                --ss-text: #f5fbfb;
                --ss-muted: #a6b7bd;
                --ss-border: rgba(0, 229, 229, 0.18);
                --ss-glass: rgba(16, 22, 27, 0.7);
                --ss-shadow: 0 22px 70px rgba(0, 0, 0, 0.34);
                --ss-font-display: 'Inter', sans-serif;
                --ss-font-body: 'Inter', sans-serif;
            }

            header, footer, #MainMenu {
                visibility: hidden;
                height: 0;
            }

            html, body, .stApp, [data-testid="stAppViewContainer"] {
                color: var(--ss-text) !important;
                font-family: var(--ss-font-body) !important;
                scroll-behavior: smooth;
            }

            .main .block-container {
                /* Animation removed to prevent glitchy login on rerun */
            }

            [data-testid="stHeader"] {
                background: transparent !important;
            }

            .block-container {
                max-width: 1100px;
                padding: 2.5rem 1.5rem 7.5rem !important;
            }

            h1, h2, h3, h4, h5, h6 {
                font-family: var(--ss-font-display) !important;
                font-weight: 800 !important;
                letter-spacing: 0 !important;
            }

            h1 {
                color: var(--ss-text) !important;
                font-size: 3.7rem !important;
                line-height: 1.1 !important;
                margin-bottom: 1rem !important;
            }

            h2 {
                color: var(--ss-text) !important;
                font-size: 2.1rem !important;
                margin-bottom: 1rem !important;
            }

            h3, .stMarkdown h3 {
                color: var(--ss-text) !important;
                font-size: 1.4rem !important;
                font-weight: 600 !important;
            }

            p, .stMarkdown p, label, [data-testid="stMarkdownContainer"] {
                color: var(--ss-muted);
                line-height: 1.6;
            }

            /* Buttons */
            .stButton > button, .stFormSubmitButton > button {
                background: linear-gradient(180deg, rgba(255, 255, 255, 0.08), rgba(255, 255, 255, 0.03)) !important;
                border: 1px solid var(--ss-border) !important;
                border-radius: 6px !important;
                color: var(--ss-text) !important;
                min-height: 48px !important;
                padding: 0.85rem 1.5rem !important;
                font-weight: 600 !important;
                font-family: var(--ss-font-body) !important;
                box-shadow: 0 12px 32px rgba(0, 0, 0, 0.24) !important;
                transition: transform 0.18s ease, background 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease !important;
            }

            .stButton > button:hover {
                background: rgba(0, 229, 229, 0.11) !important;
                border-color: rgba(0, 229, 229, 0.5) !important;
                box-shadow: 0 14px 34px rgba(0, 229, 229, 0.12) !important;
                transform: translateY(-1px);
            }

            .stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {
                background: linear-gradient(135deg, var(--ss-accent), #67ffff) !important;
                color: #001313 !important;
                border: none !important;
                box-shadow: 0 16px 38px rgba(0, 229, 229, 0.22) !important;
            }

            .stButton > button[kind="primary"]:hover {
                background: linear-gradient(135deg, #67ffff, var(--ss-accent)) !important;
                box-shadow: 0 18px 44px rgba(0, 229, 229, 0.3) !important;
            }

            /* Inputs */
            .stTextInput input, .stSelectbox div[data-baseweb="select"] > div,
            .stMultiSelect div[data-baseweb="select"] > div, textarea {
                background: rgba(6, 10, 12, 0.72) !important;
                border: 1px solid var(--ss-border) !important;
                border-radius: 6px !important;
                color: var(--ss-text) !important;
                backdrop-filter: blur(18px);
            }

            /* Cards */
            div[data-testid="stForm"], div[data-testid="stExpander"] {
                background: var(--ss-glass) !important;
                border: 1px solid var(--ss-border) !important;
                border-radius: 8px !important;
                box-shadow: var(--ss-shadow) !important;
                backdrop-filter: blur(18px);
            }

            .ss-subject-card {
                position: relative;
                overflow: hidden;
                background: var(--ss-card) !important;
                border: 1px solid var(--ss-border) !important;
                border-radius: 8px !important;
                padding: 1.5rem !important;
                margin-bottom: 1.2rem;
                box-shadow: var(--ss-shadow);
                backdrop-filter: blur(18px);
                transition: border-color 0.18s ease, background 0.18s ease, transform 0.18s ease;
            }

            .ss-subject-card::before {
                content: "";
                position: absolute;
                inset: 0 auto 0 0;
                width: 3px;
                background: var(--ss-accent);
            }

            .ss-subject-card:hover {
                background: rgba(18, 28, 33, 0.82) !important;
                border-color: var(--ss-accent);
                transform: translateY(-2px);
            }

            .ss-subject-top {
                display: flex;
                align-items: center;
                gap: 1rem;
                margin-bottom: 1.2rem;
            }

            .ss-subject-icon {
                background: rgba(0, 229, 229, 0.12);
                color: var(--ss-accent);
                width: 45px;
                height: 45px;
                border-radius: 6px;
                border: 1px solid rgba(0, 229, 229, 0.28);
                display: flex;
                align-items: center;
                justify-content: center;
                font-weight: 800;
                font-size: 1.1rem;
            }

            .ss-subject-top h3 {
                margin: 0 !important;
                font-size: 1.2rem !important;
            }

            .ss-subject-top p {
                margin: 0 !important;
                font-size: 0.85rem !important;
                opacity: 0.8;
            }

            /* Table Layout for Stats */
            .ss-subject-stats-table {
                width: 100%;
                border-collapse: collapse;
                margin-top: 0.5rem;
            }

            .ss-subject-stats-table td {
                padding: 0.5rem;
                text-align: center;
                border: 1px solid rgba(0, 229, 229, 0.1);
            }

            .ss-subject-stats-table .stat-value {
                display: block;
                font-weight: 700;
                font-size: 1.1rem;
                color: var(--ss-text);
            }

            .ss-subject-stats-table .stat-label {
                display: block;
                font-size: 0.7rem;
                text-transform: uppercase;
                letter-spacing: 0.05em;
                color: var(--ss-muted);
            }

            /* Welcome Section Fix */
            .ss-welcome-container {
                display: flex !important;
                flex-direction: row !important;
                align-items: center !important;
                justify-content: flex-start !important;
                gap: 15px !important;
                margin-top: -10px !important;
                margin-bottom: 1.5rem !important;
                width: 100% !important;
            }

            .ss-welcome-container h2 {
                margin: 0 !important;
                padding: 0 !important;
                font-size: 1.8rem !important;
                white-space: nowrap !important;
                line-height: 1.2 !important;
            }

            /* Metric Cards */
            [data-testid="stMetric"] {
                background: var(--ss-surface) !important;
                backdrop-filter: blur(12px);
                border: 1px solid var(--ss-border) !important;
                border-radius: 8px !important;
                box-shadow: var(--ss-shadow) !important;
            }

            /* Custom Brand */
            .ss-dashboard-brand {
                display: flex;
                align-items: center;
                gap: 1rem;
                padding-bottom: 2rem;
            }

            .ss-dashboard-brand img {
                width: 50px;
                height: 50px;
                border-radius: 8px;
                box-shadow: none;
            }

            .ss-dashboard-brand strong {
                font-family: var(--ss-font-display);
                font-size: 1.5rem;
                font-weight: 800;
                letter-spacing: 0;
            }

            .ss-dashboard-brand span {
                display: block;
                color: var(--ss-muted);
                font-size: 0.82rem;
                font-weight: 500;
            }

            .ss-footer-note {
                display: flex;
                justify-content: center;
                gap: 1rem;
                flex-wrap: wrap;
                padding: 1.2rem 0 0;
                color: var(--ss-muted);
                font-size: 0.78rem;
            }

            @media (max-width: 720px) {
                .block-container {
                    padding: 1.5rem 1rem 8.5rem !important;
                }

                h1 {
                    font-size: 2.65rem !important;
                }

                h2 {
                    font-size: 1.55rem !important;
                }

                .stButton > button, .stFormSubmitButton > button {
                    min-height: 52px !important;
                }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(f"<style>{_load_stylesheet()}</style>", unsafe_allow_html=True)
