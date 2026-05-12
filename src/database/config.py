import streamlit as st
from supabase import Client, create_client

from src.utils.secrets import get_secret


# Use: Internal helper for is placeholder.
# Linked with: Streamlit UI, decorators, tests, or external runtime calls.
def _is_placeholder(value):
    if not isinstance(value, str):
        return False

    placeholders = (
        "https://your-project.supabase.co",
        "your-supabase-key",
    )
    return value.strip() in placeholders


SUPABASE_URL = get_secret("SUPABASE_URL")
SUPABASE_KEY = get_secret("SUPABASE_KEY")
SUPABASE_SERVICE_ROLE_KEY = get_secret("SUPABASE_SERVICE_ROLE_KEY")

supabase: Client | None = None
admin_supabase: Client | None = None
SUPABASE_CONFIG_ERROR = None
SUPABASE_ADMIN_CONFIG_ERROR = None
if SUPABASE_URL and SUPABASE_KEY and not (
    _is_placeholder(SUPABASE_URL) or _is_placeholder(SUPABASE_KEY)
):
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as exc:
        SUPABASE_CONFIG_ERROR = str(exc)

if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY and not (
    _is_placeholder(SUPABASE_URL) or _is_placeholder(SUPABASE_SERVICE_ROLE_KEY)
):
    try:
        admin_supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    except Exception as exc:
        SUPABASE_ADMIN_CONFIG_ERROR = str(exc)


# Use: Checks is supabase configured condition for control flow.
# Linked with: admin_dashboard, student_screen, teacher_screen
def is_supabase_configured():
    return supabase is not None


# Use: Handles require supabase behavior in this module.
# Linked with: _execute_attendance_query, _fetch_current_week_feedback, _insert_email_log, _insert_thread_message, _latest_subject_context, _safe_table_select, _update_email_log, _upsert_thread and more
def require_supabase():
    if supabase is None:
        detail = f" Current error: {SUPABASE_CONFIG_ERROR}" if SUPABASE_CONFIG_ERROR else ""
        raise RuntimeError(
            "Supabase is not configured. Add SUPABASE_URL and SUPABASE_KEY to "
            ".streamlit/secrets.toml or set them as environment variables."
            + detail
        )
    return supabase


# Use: Handles require admin supabase behavior in this module.
# Linked with: add_teacher_tab, change_password_dialog, create_student, create_subject, create_teacher, delete_student, delete_teacher, enroll_student_to_matching_class_subjects and more
def require_admin_supabase():
    if admin_supabase is not None:
        return admin_supabase
    return require_supabase()


# Use: Renders the supabase setup UI section.
# Linked with: admin_dashboard, student_screen, teacher_screen
def render_supabase_setup(role="this portal"):
    st.markdown(
        f"""
        <div class="ss-setup-panel">
            <div class="ss-setup-icon">DB</div>
            <div>
                <h3>Database setup required for {role}</h3>
                <p>Add your Supabase credentials to continue. The UI is ready, but login, enrollment,
                teacher accounts, and analytics need the database connection.</p>
                <code>AI-powered-attendance-platform/.streamlit/secrets.toml</code>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.code(
        """SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_KEY = "your-supabase-key"
SUPABASE_SERVICE_ROLE_KEY = "your-service-role-key"
ADMIN_PASSWORD = "your-admin-password"
SENDER_EMAIL = "your-email@example.com"
SENDER_PASSWORD = "your-email-app-password"
""",
        language="toml",
    )
    if SUPABASE_CONFIG_ERROR:
        st.warning(f"Supabase config error: {SUPABASE_CONFIG_ERROR}")
    if SUPABASE_ADMIN_CONFIG_ERROR:
        st.warning(f"Supabase admin config error: {SUPABASE_ADMIN_CONFIG_ERROR}")
