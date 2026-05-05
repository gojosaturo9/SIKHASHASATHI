import os
import sys
import base64
import numpy as np
import cv2
from flask import Flask, request, jsonify
from flask_cors import CORS

# 🔥 1. IMPORT YOUR EXISTING PROJECT MODULES 🔥
# Isse Python ko samajh aayega ki 'src' folder kahan hai
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

try:
    # Seedha aapke db.py aur face_pipeline.py se import kar rahe hain
    from src.database.db import create_subject, create_attendance
    from src.pipelines.face_pipeline import predict_attendance

    print("✅ Custom DB and Face Pipeline imported successfully!")
except ImportError as e:
    print(f"❌ Error importing custom modules: {e}")
    sys.exit(1)


app = Flask(__name__)
CORS(app)


@app.route("/sync-attendance", methods=["POST"])
def sync_data():
    try:
        data = request.json
        subjects_data = data.get("subjects", [])
        attendance_data = data.get("attendance", [])

        # ==========================================
        # 📚 1. SYNC SUBJECTS (USING db.py)
        # ==========================================
        if subjects_data:
            for sub in subjects_data:
                # db.py ke create_subject function ko call kar rahe hain
                create_subject(
                    teacher_id=sub.get("teacher_id"),
                    code=sub.get("subject_code"),
                    name=sub.get("name"),
                    sub_type=sub.get("type", "mixed"),
                    target_branch=sub.get("target_branch", []),
                    target_semester=sub.get("target_semester", []),
                    target_section=sub.get("target_section", []),
                )
            print(f"✅ {len(subjects_data)} Subjects Created via db.py!")

        # ==========================================
        # 📸 2. PROCESS ATTENDANCE (USING face_pipeline & db.py)
        # ==========================================
        if attendance_data:
            for att in attendance_data:
                subject_code = att.get("subject_code")
                photo_base64 = att.get("photo_base64")
                timestamp = att.get("time")

                print(f"⚙️ Running ML Pipeline for Subject: {subject_code}")

                # STEP A: Decode Base64 aur OpenCV image (RGB) banayein
                if "," in photo_base64:
                    photo_base64 = photo_base64.split(",")[1]

                img_bytes = base64.b64decode(photo_base64)
                nparr = np.frombuffer(img_bytes, np.uint8)
                img_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

                # 🔥 STEP B: Aapke Face Pipeline ko call kiya
                detected_students, all_students, total_faces = predict_attendance(
                    class_image_np=img_rgb, subject_id=subject_code
                )

                print(f"👥 Faces extracted: {total_faces}")

                # STEP C: Attendance list taiyar karein (Present & Absent dono)
                if all_students:
                    attendance_logs = []

                    for student_id in all_students:
                        # Check agar yeh student_id detected (Present) hai
                        is_present = bool(detected_students.get(student_id, False))

                        attendance_logs.append(
                            {
                                "student_id": int(student_id),
                                "subject_id": subject_code,
                                "is_present": is_present,
                                "timestamp": timestamp,
                            }
                        )

                    # 🔥 STEP D: Aapke db.py ke create_attendance ko list bhej di
                    create_attendance(attendance_logs)
                    print(
                        f"✅ Saved Attendance for {len(attendance_logs)} enrolled students via db.py!"
                    )
                else:
                    print(f"⚠️ No enrolled students found in DB for {subject_code}.")

        return (
            jsonify(
                {
                    "message": "Data Synced and ML Processing Complete!",
                    "subjects_synced": len(subjects_data),
                    "attendance_processed": len(attendance_data),
                }
            ),
            200,
        )

    except Exception as e:
        print(f"❌ Sync API Error: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    print(f"🚀 Master API Bridge Running on port 5000...")
    app.run(port=5000)
