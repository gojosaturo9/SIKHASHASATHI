import streamlit as st
import pandas as pd
from datetime import datetime

from src.pipelines.voice_pipeline import process_bulk_audio
from src.database.config import supabase
from src.components.dialog_attendance_results import show_attendance_result
from src.utils.zero_trust import editable_until


# Use: Handles voice attendance dialog behavior in this module.
# Linked with: teacher_tab_take_attendance
@st.dialog("Voice Attendance")
def voice_attendance_dialog(selected_subject_id):
    st.write(
        'Record audio of students saying "I am present". Then AI will recognize the students.'
    )

    audio_data = st.audio_input("Record classroom audio")

    if st.button("Analyze Audio", use_container_width=True, type="primary"):
        if audio_data is None:
            st.error("Please record or upload an audio clip first!")
            return

        with st.spinner("Processing Audio data..."):
            subject_res = (
                supabase.table("subjects")
                .select("name")
                .eq("subject_id", selected_subject_id)
                .execute()
            )
            subject_name = (
                subject_res.data[0]["name"] if subject_res.data else "Selected Subject"
            )

            enrolled_res = (
                supabase.table("subject_students")
                .select("*, students(*)")
                .eq("subject_id", selected_subject_id)
                .execute()
            )
            enrolled_students = enrolled_res.data

            if not enrolled_students:
                st.warning("No students enrolled in this course.")
                return

            candidates_dict = {
                s["students"]["student_id"]: s["students"]["voice_embedding"]
                for s in enrolled_students
                if s["students"].get("voice_embedding")
            }

            if not candidates_dict:
                st.error("No enrolled students have voice profiles registered.")
                return

            detected_scores = process_bulk_audio(audio_data.read(), candidates_dict)

            results, attendance_to_log = [], []
            current_timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

            for node in enrolled_students:
                student = node["students"]
                score = detected_scores.get(student["student_id"], 0.0)
                is_present = bool(score > 0)

                results.append(
                    {
                        "Name": student["name"],
                        "ID": student["student_id"],
                        "email_id": student.get("email_id"),
                        "is_present": is_present,
                        "Confidence": f"{score:.2f}" if is_present else "-",
                        "Status": "Present" if is_present else "Absent",
                    }
                )

                attendance_to_log.append(
                    {
                        "student_id": student["student_id"],
                        "subject_id": selected_subject_id,
                        "timestamp": current_timestamp,
                        "is_present": is_present,
                        "source": "voice_ai",
                        "photo_detected": False,
                        "manual_override": False,
                        "editable_until": editable_until(datetime.now()),
                    }
                )

            st.session_state.voice_attendance_results = (
                pd.DataFrame(results),
                attendance_to_log,
                subject_name,
            )

    if st.session_state.get("voice_attendance_results"):
        st.divider()
        df_results, logs, subject_name = st.session_state.voice_attendance_results
        show_attendance_result(df_results, logs, subject_name, source_kind="voice")
