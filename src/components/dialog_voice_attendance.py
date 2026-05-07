import streamlit as st
import pandas as pd
from datetime import datetime

from src.pipelines.voice_pipeline import (
    is_voice_recognition_available,
    process_bulk_audio,
)
from src.database.config import supabase
from src.components.dialog_attendance_results import show_attendance_result

@st.dialog('Voice Attendance')
def voice_attendance_dialog(selected_subject_id):
    st.write('Record audio of students saying "I am present". Then AI will recognize the students.')

    if not is_voice_recognition_available():
        st.error(
            "Voice attendance needs the optional 'resemblyzer' package. "
            "The rest of the dashboard and Voice-RAG chatbot can still run."
        )
        st.code("python -m pip install resemblyzer", language="powershell")
        return

    # Audio input widget
    audio_data = st.audio_input("Record classroom audio")

    if st.button('Analyze Audio', use_container_width=True, type='primary'):
        
        # 👇 FIX 1: Sabse pehle check karein ki audio record hua hai ya nahi
        if audio_data is None:
            st.error("Please record or upload an audio clip first!")
            return  # Yahan se code wapas bhej do, aage mat badho
            
        with st.spinner('Processing Audio data...'): # Typo fixed
            enrolled_res = supabase.table('subject_students').select("*, students(*)").eq('subject_id',selected_subject_id ).execute()
            enrolled_students = enrolled_res.data

            if not enrolled_students:
                st.warning('No students enrolled in this course.')
                return
            
            candidates_dict = {
                s['students']['student_id'] : s['students']['voice_embedding'] 
                for s in enrolled_students if s['students'].get('voice_embedding')
            }

            if not candidates_dict:
                st.error('No enrolled students have voice profiles registered.') # Typo fixed
                return
            
            # 👇 Ab yeh safe hai kyunki humne upar check kar liya hai
            audio_bytes = audio_data.read()

            detected_scores = process_bulk_audio(audio_bytes, candidates_dict)

            results, attendance_to_log  = [], []
            current_timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

            for node in enrolled_students:
                student = node['students']
                score  = detected_scores.get(student['student_id'], 0.0)
                is_present = bool(score > 0)

                results.append({
                    "Name": student['name'],
                    "ID": student['student_id'],
                    "Confidence": f"{score:.2f}" if is_present else "-", # Changed 'Source' to 'Confidence' for better UI
                    "Status": "✅ Present" if is_present else "❌ Absent"
                })

                attendance_to_log.append({
                    'student_id': student['student_id'],
                    'subject_id': selected_subject_id,
                    'timestamp': current_timestamp,
                    'is_present': is_present # Removed redundant bool()
                })
                
            st.session_state.voice_attendance_results = (pd.DataFrame(results), attendance_to_log)

    # Show results outside the button click so it persists
    if st.session_state.get('voice_attendance_results'):
        st.divider()
        df_results, logs = st.session_state.voice_attendance_results
        show_attendance_result(df_results, logs)
