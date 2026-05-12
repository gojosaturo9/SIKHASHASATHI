import streamlit as st
from src.database.db import create_subject


# Use: Creates subject dialog data in the app/database flow.
# Linked with: teacher_tab_manage_subjects
@st.dialog("Create New Subject")
def create_subject_dialog(teacher_id):
    st.write("Enter the details of the new subject.")

    sub_id = st.text_input("Subject Code", placeholder="CS101")
    sub_name = st.text_input(
        "Subject Name", placeholder="Introduction to Computer Science"
    )

    st.divider()

    sub_type_selection = st.radio(
        "Enrollment Type",
        options=["Class-wise (Auto-Enroll)", "Mixed/Open"],
        captions=[
            "Automatically enrolls registered students from the selected branch, semester, and section.",
            "Use only when the subject should not be tied to one class.",
        ],
    )

    # Ab by default empty lists rahenge
    t_branch, t_sem, t_sec = [], [], []

    if sub_type_selection == "Class-wise (Auto-Enroll)":
        st.info(
            "Select the target classes. You can choose multiple branches, semesters, and sections."
        )

        # 🚀 NAYA FIX: st.multiselect lagaya
        t_branch = st.multiselect(
            "Branches",
            [
                "Computer Science",
                "Information Tech",
                "ECE",
                "Mechanical",
                "Civil",
                "AI/ML",
                "AI/DS",
                "DS",
                "Cyber",
            ],
            placeholder="Select one or more",
        )

        col1, col2 = st.columns(2)
        with col1:
            t_sem = st.multiselect(
                "Semesters", [1, 2, 3, 4, 5, 6, 7, 8], placeholder="e.g. 3, 4"
            )
        with col2:
            t_sec = st.multiselect(
                "Sections", ["A", "B", "C", "D"], placeholder="e.g. A, B"
            )

    db_type = (
        "class_wise"
        if sub_type_selection == "Class-wise (Auto-Enroll)"
        else "mixed"
    )

    if st.button("Create Subject", type="primary", width="stretch"):
        if sub_id and sub_name:
            if db_type == "class_wise" and (not t_branch or not t_sem or not t_sec):
                st.warning(
                    "Please select at least one Branch, Semester, and Section for Class-wise enrollment."
                )
                return

            try:
                result = create_subject(
                    teacher_id=teacher_id,
                    code=sub_id,
                    name=sub_name,
                    sub_type=db_type,
                    target_branch=t_branch,
                    target_semester=t_sem,
                    target_section=t_sec,
                )
                enrolled_count = result.get("enrolled_count", 0) if result else 0
                st.toast(f"Subject created. {enrolled_count} student(s) auto-enrolled.")
                st.rerun()
            except Exception as e:
                error_text = str(e)
                if "42501" in error_text or "row-level security" in error_text.lower():
                    st.error(
                        "Subject create nahi ho paya because Supabase RLS subjects table par insert allow nahi kar rahi. "
                        "SUPABASE_SERVICE_ROLE_KEY secrets.toml me add karo ya supabase_rls_policies.sql run karo."
                    )
                else:
                    st.error(f"Error: {error_text}")
        else:
            st.warning("Please fill the Subject Code and Subject Name")
