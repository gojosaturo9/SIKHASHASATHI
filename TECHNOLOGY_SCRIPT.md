# TRUEPRESENCE Technology Script

## Project Overview

TRUEPRESENCE is an AI-powered attendance platform built for colleges. It separates Admin, Teacher, and Student roles. Admin manages teachers and analytics, teachers create subjects and mark attendance, and students use live face login to view their attendance.

## Technology Used

### Python

Use: Python powers the full application logic, AI pipelines, database calls, report generation, and background notifications.

Advantages: Python has mature AI, data science, image processing, and web app libraries. This makes it faster to build an AI attendance system without switching languages for every module.

Why better here: Compared with Java or PHP, Python gives easier integration with face recognition, NumPy, pandas, ONNX Runtime, and machine learning models.

Example: The face pipeline uses Python with NumPy arrays to process camera images and compare face embeddings.

Implementation: Python files inside `src/` are divided into screens, components, database helpers, pipelines, and utilities.

### Streamlit

Use: Streamlit creates the web interface for Admin, Teacher, and Student panels.

Advantages: It is fast for data-driven dashboards, camera input, audio input, tables, charts, forms, and file downloads.

Why better here: Compared with a full React plus backend setup, Streamlit reduces development time because Python UI and AI code can run in the same app.

Example: Teacher attendance uses `st.camera_input`, `st.dataframe`, `st.button`, and dialogs to collect classroom photos and show attendance results.

Implementation: `app.py` routes users by `st.session_state["login_type"]`, and each role screen lives in `src/screens/`.

### Supabase

Use: Supabase stores teachers, students, subjects, subject enrollments, and attendance logs.

Advantages: Supabase provides a hosted PostgreSQL database with a simple Python client and structured tables.

Why better here: Compared with local SQLite, Supabase is better for multi-user access because teachers, students, and admin can share the same live database.

Example: Attendance logs are inserted into the `attendance_logs` table and joined with `students` and `subjects` for reports.

Implementation: `src/database/db.py` contains all database operations, and `src/database/config.py` manages Supabase connection setup.

### Face Recognition With dlib

Use: dlib detects faces, extracts facial landmarks, and creates face embeddings for student recognition.

Advantages: dlib gives stable face landmarks and embeddings, which are useful for both recognition and blink detection.

Why better here: Compared with simple image matching, face embeddings handle different lighting, angle, and camera quality better.

Example: A student face is converted into a numerical embedding and matched against stored student embeddings.

Implementation: `src/pipelines/face_pipeline.py` loads dlib models, detects faces, creates embeddings, and predicts the matching student.

### Anti-Spoofing and Liveness Detection

Use: Anti-spoofing blocks printed photos, phone screens, and suspicious fake faces.

Advantages: It improves trust by checking if the detected face looks live before attendance or login is accepted.

Why better here: Plain face recognition can be fooled by a photo. Liveness adds a security layer before identity matching.

Example: If a student shows a phone photo to the camera, the liveness model can reject the face before login.

Implementation: `src/pipelines/anti_spoofing_pipeline.py` uses the custom liveness model or ONNX anti-spoofing model. `face_pipeline.py` calls it before generating embeddings.

### Eye Blink Login

Use: Student login now requires a blink challenge before face matching.

Advantages: Blink verification proves the student is interacting live with the camera.

Why better here: A static photo cannot naturally pass a blink challenge, so it is stronger than only matching a face image.

Example: The student first captures an open-eye frame, then captures a blink frame. Login continues only if one live face and a blink are detected.

Implementation: `detect_blink_challenge()` in `src/pipelines/face_pipeline.py` uses dlib eye landmarks and eye aspect ratio. `src/screens/student_screen.py` calls it before running face recognition.

### Four-Layer Attendance System

Use: Teacher attendance is protected by four checks before final save.

Advantages: The system reduces fake attendance, old photo misuse, wrong-class scans, and untracked manual edits.

Why better here: A single AI prediction is not enough for institutional attendance. Layered checks make the result more reliable and auditable.

Implementation:

Layer 1: Fresh photo metadata check in `src/utils/zero_trust.py` rejects old uploads or images without valid capture metadata.

Layer 2: Face liveness check in `src/pipelines/anti_spoofing_pipeline.py` rejects spoof faces.

Layer 3: Roster and crowd validation in `validate_crowd_and_roster()` verifies enough faces match the selected class roster.

Layer 4: Teacher-only audited correction lets teachers mark Present or Absent only for eligible non-photo-detected rows within the edit window.

### pandas

Use: pandas prepares attendance analytics, student summaries, defaulter lists, and downloadable reports.

Advantages: It makes grouping, filtering, merging, and percentage calculations simple.

Why better here: Compared with manually looping over every row for analytics, pandas is shorter, clearer, and less error-prone.

Example: Teacher reports group attendance by student and subject to calculate present days and attendance percentage.

Implementation: Admin and teacher screens convert database results into DataFrames before rendering charts and tables.

### bcrypt

Use: bcrypt hashes teacher passwords before storing them.

Advantages: Passwords are never stored as plain text.

Why better here: Compared with simple hashing like MD5 or SHA256, bcrypt is intentionally slow and safer against brute-force attacks.

Example: When admin creates a teacher, the generated password is hashed before insertion into Supabase.

Implementation: `src/screens/admin_screen.py` uses `bcrypt.hashpw()`, and `src/database/db.py` verifies passwords with `bcrypt.checkpw()`.

### ONNX Runtime

Use: ONNX Runtime runs the anti-spoofing model locally.

Advantages: It supports optimized model inference on CPU without needing a full training framework.

Why better here: Compared with loading a full deep learning stack for inference, ONNX Runtime is lighter and deployment-friendly.

Example: The liveness model checks face crops and returns real/spoof confidence.

Implementation: `src/pipelines/anti_spoofing_pipeline.py` loads the ONNX model and runs predictions through CPU execution.

## Final Implementation Summary

Admin is now focused on teacher creation and read-only analytics. Teacher owns attendance marking and correction. Student login requires live face recognition plus an eye blink challenge. The four-layer attendance system combines photo freshness, liveness detection, roster validation, and audited teacher correction.
