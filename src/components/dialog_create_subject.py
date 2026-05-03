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
            "Automatically fetches all students of a specific class.",
            "Students will enroll themselves using the subject code.",
        ],
    )

    t_branch = None
    t_sem = None
    t_sec = None

    if sub_type_selection == "Class-wise (Smart Auto-Enroll)":
        st.info(
            "Select the target class. All students in this class will be auto-enrolled."
        )
        col1, col2, col3 = st.columns(3)
        with col1:
            t_branch = st.selectbox(
                "Branch",
                [
                    "Computer Science",
                    "Information Tech",
                    "ECE",
                    "Mechanical",
                    "Civil",
                    "AI/ML",
                    "AI/DS",
                    "Cyber",
                    "DS",
                ],
            )
        with col2:
            t_sem = st.selectbox("Semester", [1, 2, 3, 4, 5, 6, 7, 8])
        with col3:
            t_sec = st.selectbox("Section", ["A", "B", "C", "D", "None"])

    # 🚀 FIX: Else block hata diya! Mixed ke liye ab koi input nahi aayega aur t_sec automatically None rahega.

    db_type = (
        "class_wise"
        if sub_type_selection == "Class-wise (Smart Auto-Enroll)"
        else "mixed"
    )

    if st.button("Create Subject Now", type="primary", width="stretch"):
        if sub_id and sub_name:
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
