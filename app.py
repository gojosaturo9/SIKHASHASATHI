import streamlit as st


# Use: Handles main behavior in this module.
# Linked with: Streamlit UI, decorators, tests, or external runtime calls.
def main():
    """Route the Streamlit app to the selected portal and start background services once."""
    st.set_page_config(
        page_title="SIKHASHASASATHI | AI Powered Attendance",
        page_icon="src/assets/logo1.png",
        layout="wide",
    )

    if "login_type" not in st.session_state:
        st.session_state["login_type"] = None

    try:
        from src.utils.email_automation import start_inbound_email_poller

        start_inbound_email_poller()
    except Exception as exc:
        print(f"Inbound email auto-reply startup skipped: {exc}")

    match st.session_state["login_type"]:
        case "teacher":
            from src.screens.teacher_screen import teacher_screen

            teacher_screen()

        case "student":
            from src.screens.student_screen import student_screen

            student_screen()

        case "admin":
            from src.screens.admin_screen import admin_dashboard

            admin_dashboard()

        case None:
            from src.screens.home_screen import home_screen

            home_screen()

    join_code = st.query_params.get("join-code")
    if join_code:
        if st.session_state.login_type != "student":
            st.session_state.login_type = "student"
            st.rerun()
        if (
            st.session_state.get("is_logged_in")
            and st.session_state.get("user_role") == "student"
        ):
            from src.components.dialog_auto_enroll import auto_enroll_dialog

            auto_enroll_dialog(join_code)


main()
