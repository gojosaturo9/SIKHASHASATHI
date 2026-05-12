import streamlit as st
import bcrypt
import time
from src.database.config import require_admin_supabase
from src.database.db import check_pass


# Use: Handles change password dialog behavior in this module.
# Linked with: teacher_dashboard
@st.dialog("🔐 Change Secure Password")
def change_password_dialog():
    st.write(
        "Please update your auto-generated password to something secure that you can remember."
    )

    current_pass = st.text_input(
        "Current Password",
        type="password",
        placeholder="Enter the password from your email",
    )
    new_pass = st.text_input(
        "New Password", type="password", placeholder="Enter your new password"
    )
    confirm_pass = st.text_input(
        "Confirm New Password",
        type="password",
        placeholder="Re-enter your new password",
    )

    if st.button("Update Password", type="primary", use_container_width=True):
        if not current_pass or not new_pass or not confirm_pass:
            st.warning("⚠️ Please fill all fields.")
            return

        if new_pass != confirm_pass:
            st.error("❌ New passwords do not match!")
            return

        teacher_data = st.session_state.teacher_data

        # 1. Purana password verify karein
        if not check_pass(current_pass, teacher_data["password"]):
            st.error("❌ Incorrect current password!")
            return

        # 2. Naye password ko hash karein
        hashed_pass = bcrypt.hashpw(new_pass.encode("utf-8"), bcrypt.gensalt()).decode(
            "utf-8"
        )

        try:
            with st.spinner("Updating password securely..."):
                # 3. Database mein update karein
                require_admin_supabase().table("teachers").update({"password": hashed_pass}).eq(
                    "username", teacher_data["username"]
                ).execute()

                # 4. Session state update karein taaki turant logout na ho
                st.session_state.teacher_data["password"] = hashed_pass

            st.success(
                "✅ Password updated successfully! Next time, login with your new password."
            )
            time.sleep(2)
            st.rerun()
        except Exception as e:
            st.error(f"Error updating password: {e}")
