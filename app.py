import streamlit as st

from src.screens.home_screen import home_screen
from src.screens.teacher_screen import teacher_screen
from src.screens.student_screen import student_screen

# 👇 1. Admin screen ko import kiya
from src.screens.admin_screen import admin_dashboard

from src.components.dialog_auto_enroll import auto_enroll_dialog


def main():

    if "login_type" not in st.session_state:
        st.session_state["login_type"] = None

    match st.session_state["login_type"]:
        case "teacher":
            teacher_screen()

        case "student":
            student_screen()

        # 👇 2. Naya case add kiya Admin ke liye
        case "admin":
            admin_dashboard()

        case None:
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
            auto_enroll_dialog(join_code)


main()
