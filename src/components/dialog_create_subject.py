import streamlit as st
from src.database.db import create_subject


@st.dialog("Create New Subject")
def create_subject_dialog(teacher_id):
    st.write("Enter the details of new subject")

    sub_id = st.text_input("Subject Code", placeholder="CS101")
    sub_name = st.text_input(
        "Subject Name", placeholder="Introduction to Computer Science"
    )

    st.divider()

    sub_type_selection = st.radio(
        "Enrollment Type",
        options=["Class-wise (Smart Auto-Enroll)", "Mixed/Open (Manual Enroll)"],
        captions=[
            "Automatically fetches all students of selected classes.",
            "Students will enroll themselves using the subject code.",
        ],
    )

    # Ab by default empty lists rahenge
    t_branch, t_sem, t_sec = [], [], []

    if sub_type_selection == "Class-wise (Smart Auto-Enroll)":
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
                "Ai/ML",
                "Ai/DS",
                "DS",
                "Cyber"
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
        if sub_type_selection == "Class-wise (Smart Auto-Enroll)"
        else "mixed"
    )

    if st.button("Create Subject Now", type="primary", width="stretch"):
        if sub_id and sub_name:
            if db_type == "class_wise" and (not t_branch or not t_sem or not t_sec):
                st.warning(
                    "Please select at least one Branch, Semester, and Section for Class-wise enrollment."
                )
                return

            try:
                create_subject(
                    teacher_id=teacher_id,
                    code=sub_id,
                    name=sub_name,
                    sub_type=db_type,
                    target_branch=t_branch,
                    target_semester=t_sem,
                    target_section=t_sec,
                )
                st.toast("Subject Created Successfully!")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {str(e)}")
        else:
            st.warning("Please fill the Subject Code and Subject Name")
