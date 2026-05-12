import streamlit as st
from src.ui.base_layout import style_background_dashboard, style_base_layout
from src.database.config import is_supabase_configured, render_supabase_setup, require_supabase
from src.components.header import header_dashboard
from src.components.footer import footer_dashboard
from src.components.subject_card import subject_card
from src.components.dialog_share_subject import share_subject_dialog
from src.database.db import (
    cleanup_old_feedback,
    feedback_table_available,
    get_teacher_by_username,
    get_teacher_subjects,
    get_attendance_for_teacher,
    get_editable_attendance_for_teacher,
    get_teacher_feedback,
    check_pass,
    reply_to_subject_feedback,
    sync_teacher_class_subject_enrollments,
    update_attendance_override,
)
from src.components.dialog_create_subject import create_subject_dialog
from src.components.dialog_add_photo import add_photos_dialog

from src.pipelines.face_pipeline import FacePipelineSetupError, predict_attendance
from src.components.dialog_attendance_results import show_attendance_result
import numpy as np
import time

from datetime import datetime

import pandas as pd

from src.components.dialog_voice_attendance import voice_attendance_dialog
from src.components.dialog_change_password import change_password_dialog
from src.components.ai_insights import render_ai_insights
from src.voice_rag.streamlit_ui import render_voice_rag_chatbot
from src.utils.reports import build_attendance_report, filter_report_period
from src.utils.zero_trust import editable_until, validate_crowd_and_roster

# Use: Handles teacher screen behavior in this module.
# Linked with: main
def teacher_screen():
    style_background_dashboard()
    style_base_layout()

    if not is_supabase_configured():
        c1, c2 = st.columns(2, vertical_alignment="center", gap="xxlarge")
        with c1:
            header_dashboard()
        with c2:
            if st.button("Go back to Home", type="secondary", key="loginbackbtn"):
                st.session_state["login_type"] = None
                st.rerun()
        st.header("Teacher Login Panel", anchor=False)
        render_supabase_setup("Teacher Portal")
        footer_dashboard()
        return

    if "teacher_data" in st.session_state:
        teacher_dashboard()
    else:
        teacher_screen_login()


# Use: Handles teacher dashboard behavior in this module.
# Linked with: teacher_screen
def teacher_dashboard():
    teacher_data = st.session_state.teacher_data
    cleanup_old_feedback()

    from src.database.db import get_active_announcements
    try:
        announcements = get_active_announcements()
        if announcements:
            for ann in announcements:
                icon = "🔔" if ann['category'] == "General" else "📅" if ann['category'] == "Holiday" else "🚨" if ann['category'] == "Urgent" else "🎉"
                st.info(f"{icon} **{ann['title']}**: {ann['content']}")
    except Exception:
        pass

    # 🚀 FIX 1: Outer Columns ko wapas '2' kar diya (50-50).
    # Isse SAGE CLASS logo ko apni poori purani jagah mil jayegi aur wo kharab nahi hoga.
    c1, c2 = st.columns(2, vertical_alignment="center", gap="large")
    with c1:
        header_dashboard()
    with c2:
        st.subheader(f"""Welcome, {teacher_data['name']} """)

        # 🚀 FIX 2: Sirf inner buttons ko ratio diya [1.4, 1].
        # Isse Change Password apne aap fit ho jayega bina logo ki jagah khaaye.
        btn_c1, btn_c2 = st.columns([1.4, 1])
        with btn_c1:
            if st.button(
                "Change Password",
                use_container_width=True,
            ):
                change_password_dialog()

        with btn_c2:
            if st.button(
                "Logout",
                type="secondary",
                use_container_width=True,
            ):
                st.session_state["is_logged_in"] = False
                st.session_state["login_type"] = None
                if "teacher_data" in st.session_state:
                    del st.session_state.teacher_data
                st.rerun()

    st.write("")

    if "current_teacher_tab" not in st.session_state:
        st.session_state.current_teacher_tab = "take_attendance"
    tab1, tab2, tab3, tab4, tab5 = st.columns(5)

    with tab1:
        type1 = (
            "primary"
            if st.session_state.current_teacher_tab == "take_attendance"
            else "tertiary"
        )
        if st.button(
            "Attendance", type=type1, width="stretch"
        ):
            st.session_state.current_teacher_tab = "take_attendance"
            st.rerun()

    with tab2:
        type2 = (
            "primary"
            if st.session_state.current_teacher_tab == "manage_subjects"
            else "tertiary"
        )
        if st.button(
            "Subjects",
            type=type2,
            width="stretch",
        ):
            st.session_state.current_teacher_tab = "manage_subjects"
            st.rerun()

    with tab3:
        type3 = (
            "primary"
            if st.session_state.current_teacher_tab == "attendance_records"
            else "tertiary"
        )
        if st.button(
            "Records",
            type=type3,
            width="stretch",
        ):
            st.session_state.current_teacher_tab = "attendance_records"
            st.rerun()

    with tab4:
        type4 = (
            "primary"
            if st.session_state.current_teacher_tab == "student_feedback"
            else "tertiary"
        )
        if st.button(
            "Feedback",
            type=type4,
            width="stretch",
        ):
            st.session_state.current_teacher_tab = "student_feedback"
            st.rerun()

    with tab5:
        type5 = (
            "primary"
            if st.session_state.current_teacher_tab == "ai_insights"
            else "tertiary"
        )
        if st.button(
            "Insights",
            type=type5,
            width="stretch",
        ):
            st.session_state.current_teacher_tab = "ai_insights"
            st.rerun()

    st.divider()

    if st.session_state.current_teacher_tab == "take_attendance":
        teacher_tab_take_attendance()

    if st.session_state.current_teacher_tab == "manage_subjects":
        teacher_tab_manage_subjects()

    if st.session_state.current_teacher_tab == "attendance_records":
        teacher_tab_attendance_records()

    if st.session_state.current_teacher_tab == "student_feedback":
        teacher_tab_student_feedback()

    if st.session_state.current_teacher_tab == "ai_insights":
        render_ai_insights()

    render_voice_rag_chatbot("teacher")
    footer_dashboard()


# Use: Handles teacher tab take attendance behavior in this module.
# Linked with: teacher_dashboard
def teacher_tab_take_attendance():
    teacher_id = st.session_state.teacher_data["teacher_id"]
    st.header("Take Attendance")
    st.caption(
        "Capture a fresh camera photo. The system checks liveness first, then matches only real faces against the roster."
    )

    if "attendance_images" not in st.session_state:
        st.session_state.attendance_images = []
    if "attendance_photo_meta" not in st.session_state:
        st.session_state.attendance_photo_meta = []

    sync_teacher_class_subject_enrollments(teacher_id)
    subjects = get_teacher_subjects(teacher_id)

    if not subjects:
        st.warning("You haven't created any subjects yet! Please create one to begin!")
        return

    # Subject details store karna zaroori hai (Name aur ID dono)
    subject_options = {f"{s['name']} - {s['subject_code']}": s for s in subjects}

    col1, col2 = st.columns([3, 1], vertical_alignment="bottom")
    with col1:
        selected_label = st.selectbox(
            "Select Subject", options=list(subject_options.keys())
        )
        selected_subject = subject_options[selected_label]
        selected_subject_id = selected_subject["subject_id"]
        selected_subject_name = selected_subject["name"]

    with col2:
        if st.button(
            "Capture Photo",
            type="primary",
            width="stretch",
        ):
            add_photos_dialog()

    quick1, quick2, quick3 = st.columns(3)
    with quick1:
        if st.button("Face", type="primary", width="stretch"):
            st.info("Capture a classroom photo below, then run Face Analysis.")
    with quick2:
        if st.button("Voice", width="stretch"):
            voice_attendance_dialog(selected_subject_id)
    with quick3:
        if st.button("Details", width="stretch"):
            share_subject_dialog(selected_subject_name, selected_subject["subject_code"])

    st.divider()

    if st.session_state.attendance_images:
        st.header("Captured Photos")
        gallery_cols = st.columns(4)
        for idx, img in enumerate(st.session_state.attendance_images):
            with gallery_cols[idx % 4]:
                st.image(img, use_container_width=True, caption=f"Photo {idx+1}")

    has_photos = bool(st.session_state.attendance_images)
    c1, c2, c3 = st.columns(3)

    with c1:
        if st.button(
            "Clear Photos",
            width="stretch",
            type="tertiary",
            disabled=not has_photos,
        ):
            st.session_state.attendance_images = []
            st.session_state.attendance_photo_meta = []
            st.rerun()

    with c2:
        if st.button(
            "Run Face",
            width="stretch",
            type="secondary",
            disabled=not has_photos,
        ):
            with st.spinner("Checking liveness and matching classroom faces..."):
                detected_ids_camera = {} # High Trust (Camera)
                detected_ids_upload = {} # Zero Trust (Upload)
                
                spoofed_faces = []
                uncertain_faces = []
                accepted_photo_count = 0

                for idx, img in enumerate(st.session_state.attendance_images):
                    photo_meta = (
                        st.session_state.attendance_photo_meta[idx]
                        if idx < len(st.session_state.attendance_photo_meta)
                        else {"source": "camera", "accepted": True}
                    )
                    source = photo_meta.get("source", "upload")
                    is_upload = (source == "upload")
                    
                    # LAYER 1: Metadata Check (Only for Upload)
                    if is_upload and not photo_meta.get("accepted", True):
                        st.error(f"Photo {idx+1} rejected by Zero Trust (Metadata): {photo_meta.get('reason', 'old_or_invalid_timestamp')}")
                        continue

                    img_np = np.array(img.convert("RGB"))
                    try:
                        detected, _, total_faces = predict_attendance(
                            img_np, selected_subject_id
                        )
                    except FacePipelineSetupError as e:
                        st.error(str(e))
                        return

                    # LAYER 2 & 3: Crowd & roster validation is only for uploaded files.
                    # Fresh camera captures continue after liveness/anti-spoofing.
                    if is_upload:
                        is_valid_photo, zero_trust_reason = validate_crowd_and_roster(
                            total_faces=total_faces,
                            roster_matches=len(detected or {}),
                        )
                        if not is_valid_photo:
                            st.error(f"Photo {idx+1} rejected by Zero Trust (Crowd): {zero_trust_reason}")
                            continue

                    accepted_photo_count += 1
                    liveness = st.session_state.get("_last_face_liveness", {})
                    spoofed_faces.extend(liveness.get("spoofed_faces", []))
                    uncertain_faces.extend(liveness.get("uncertain_faces", []))

                    if detected:
                        for sid, match in detected.items():
                            student_id = int(sid)
                            match_info = (
                                f"Photo {idx+1} ({source}, "
                                f"distance {match.get('distance', '-')})"
                            )
                            if is_upload:
                                detected_ids_upload.setdefault(student_id, []).append(match_info)
                            else:
                                detected_ids_camera.setdefault(student_id, []).append(match_info)

                # 🚀 STEP 3: Smart student fetching & Threshold Calculation
                from src.database.db import get_students_for_subject
                students_list = get_students_for_subject(selected_subject_id)
                total_enrolled = len(students_list) if students_list else 0
                roster_by_id = {
                    int(student["student_id"]): student for student in (students_list or [])
                }
                matched_ids = set(detected_ids_camera) | set(detected_ids_upload)
                roster_matched_ids = matched_ids & set(roster_by_id)
                matched_roster_names = [
                    roster_by_id[student_id].get("name", str(student_id))
                    for student_id in sorted(roster_matched_ids)
                ]
                matched_outside_roster = [
                    student_id
                    for student_id in sorted(matched_ids)
                    if student_id not in roster_by_id
                ]

                if spoofed_faces:
                    st.error(
                        f"Anti-spoofing blocked {len(spoofed_faces)} face(s). Use a live camera/photo, not a screen or printed image."
                    )
                if uncertain_faces:
                    st.warning(
                        f"Anti-spoofing marked {len(uncertain_faces)} face(s) as uncertain but live enough to continue."
                    )
                if accepted_photo_count == 0:
                    st.error("No valid photo was accepted for attendance.")
                    return
                if matched_roster_names:
                    st.success(
                        "Face matched from database: "
                        + ", ".join(matched_roster_names)
                    )
                if matched_outside_roster:
                    st.warning(
                        "Face matched a database student who is not enrolled in this selected subject. "
                        f"Matched student ID(s): {', '.join(str(sid) for sid in matched_outside_roster)}"
                    )
                 
                # LAYER 4: Session Threshold (Only applies to Upload matches)
                unique_upload_matches = len(detected_ids_upload)
                
                # 🚀 FIX: Allow single student attendance capture even if class is large.
                # Relaxed the 50% threshold to allow individual photo attendance.
                threshold_met_upload = (unique_upload_matches >= 1)

                if unique_upload_matches > 0 and not threshold_met_upload:
                    st.warning(f"Upload Threshold Not Met: Only {unique_upload_matches}/{total_enrolled} students detected via uploads.")

                if not students_list:
                    target_branch = ", ".join(selected_subject.get("target_branch") or []) or "-"
                    target_semester = ", ".join(str(item) for item in (selected_subject.get("target_semester") or [])) or "-"
                    target_section = ", ".join(selected_subject.get("target_section") or []) or "-"
                    st.warning(
                        "No students found for this class/subject. "
                        f"Target: Branch={target_branch}, Semester={target_semester}, Section={target_section}."
                    )
                else:
                    if not roster_matched_ids and total_faces > 0:
                        liveness = st.session_state.get("_last_face_liveness", {})
                        st.info(
                            "Face detected, but no roster match crossed the trained-model threshold. "
                            f"Faces={total_faces}, Live={liveness.get('live_faces', 0)}, "
                            f"Spoofed={len(liveness.get('spoofed_faces', []) or [])}, "
                            f"Uncertain={len(liveness.get('uncertain_faces', []) or [])}."
                        )

                    results, attendance_to_log = [], []
                    current_timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

                    for student in students_list:
                        sid = int(student["student_id"])
                        camera_sources = detected_ids_camera.get(sid, [])
                        upload_sources = detected_ids_upload.get(sid, [])
                        
                        face_matched = (len(camera_sources) > 0 or len(upload_sources) > 0)
                        
                        # 🚀 DUAL-TRACK LOGIC
                        # 1. Camera matches are ALWAYS present (High Trust)
                        # 2. Upload matches are present ONLY if threshold is met (Zero Trust)
                        # One camera-captured roster match is enough to mark that student present.
                        is_present = (len(camera_sources) > 0) or (len(upload_sources) > 0 and threshold_met_upload)

                        all_sources = camera_sources + upload_sources
                        results.append(
                            {
                                "Name": student["name"],
                                "ID": student["student_id"],
                                "email_id": student.get("email_id"),
                                "is_present": is_present,
                                "photo_detected": face_matched,
                                "Source": ", ".join(all_sources) if face_matched else "-",
                                "Status": "✅ Present" if is_present else ("🔍 Face Match (Rejected)" if face_matched else "❌ Absent"),
                            }
                        )

                        attendance_to_log.append(
                            {
                                "student_id": student["student_id"],
                                "subject_id": selected_subject_id,
                                "timestamp": current_timestamp,
                                "is_present": bool(is_present),
                                "source": "photo_ai",
                                "photo_detected": bool(face_matched),
                                "manual_override": False,
                                "editable_until": editable_until(datetime.now()),
                            }
                        )

                    st.session_state.pending_attendance_result = {
                        "subject_id": selected_subject_id,
                        "subject_name": selected_subject_name,
                        "total_enrolled": total_enrolled,
                        "total_present": sum(1 for item in results if item["is_present"]),
                        "total_absent": sum(1 for item in results if not item["is_present"]),
                        "roster_matched_count": len(roster_matched_ids),
                        "df": pd.DataFrame(results),
                        "logs": attendance_to_log,
                        "source_kind": "photo",
                    }
                    st.rerun()

    with c3:
        if st.button(
            "Use Voice",
            type="primary",
            width="stretch",
        ):
            voice_attendance_dialog(selected_subject_id)

    pending_result = st.session_state.get("pending_attendance_result")

    if pending_result and pending_result.get("subject_id") == selected_subject_id:
        st.divider()
        st.subheader("Attendance Result")

        show_attendance_result(
            pending_result["df"],
            pending_result["logs"],
            pending_result["subject_name"],
            source_kind=pending_result.get("source_kind", "photo"),
        )


# Use: Handles teacher tab manage subjects behavior in this module.
# Linked with: teacher_dashboard
def teacher_tab_manage_subjects():
    teacher_id = st.session_state.teacher_data["teacher_id"]
    col1, col2 = st.columns(2)
    with col1:
        st.header("Manage Subjects", width="stretch")
    with col2:
        if st.button("Create New Subject", width="stretch"):
            create_subject_dialog(teacher_id)

    sync_teacher_class_subject_enrollments(teacher_id)
    subjects = get_teacher_subjects(teacher_id)
    if subjects:
        for sub in subjects:
            is_class_wise = sub.get("type") == "class_wise"
            sub_type_label = "📍 Class-wise" if is_class_wise else "🌐 Mixed"

            # 🚀 NAYA FIX: Lists/Arrays ko format karke sundar text banana
            if is_class_wise:
                b_list = sub.get("target_branch") or []
                s_list = sub.get("target_semester") or []
                sec_list = sub.get("target_section") or []

                # Agar list khali nahi hai toh comma se join karo, warna "All" likho
                b_str = ", ".join(b_list) if b_list else "All"

                # Semester integers ho sakte hain, isliye string me convert karke join kiya
                s_str = ", ".join([str(x) for x in s_list]) if s_list else "All"

                sec_str = ", ".join(sec_list) if sec_list else "All"

                class_details = f"🎓 {b_str} | Sem {s_str} | Sec {sec_str}"
            else:
                class_details = "🧩 Mixed/Open Class"

            stats = [
                ("🫂", "Students", sub["total_students"]),
                ("🕰️", "Classes", sub["total_classes"]),
                ("🏷️", "Type", sub_type_label),
            ]

            # Use: Handles share btn behavior in this module.
            # Linked with: Streamlit UI, decorators, tests, or external runtime calls.
            def share_btn(current_sub=sub):
                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button(
                        "Details",
                        key=f"share_{current_sub['subject_id']}",
                        use_container_width=True,
                    ):
                        share_subject_dialog(
                            current_sub["name"], current_sub["subject_code"]
                        )
                with col_b:
                    if st.button(
                        "Delete",
                        key=f"del_sub_{current_sub['subject_id']}",
                        type="secondary",
                        use_container_width=True,
                    ):
                        from src.database.db import delete_subject
                        delete_subject(current_sub["subject_id"])
                        st.toast(f"Subject '{current_sub['name']}' deleted.")
                        st.rerun()
                st.write("")

            subject_card(
                name=sub["name"],
                code=sub["subject_code"],
                section=class_details,
                stats=stats,
                footer_callback=share_btn,
            )
    else:
        st.info("NO SUBJECTS FOUND. CREATE ONE ABOVE")


# Use: Handles teacher tab attendance records behavior in this module.
# Linked with: teacher_dashboard
def teacher_tab_attendance_records():
    st.header("Attendance Records")
    st.caption(
        "Teachers can mark Present or Absent for eligible non-photo-detected rows within the audited correction window."
    )

    teacher_id = st.session_state.teacher_data["teacher_id"]
    with st.expander("Teacher present/absent correction audit panel", expanded=False):
        editable_rows = get_editable_attendance_for_teacher(teacher_id)
        if not editable_rows:
            st.info("No editable non-photo-detected attendance rows right now.")
        else:
            options = {}
            for row in editable_rows:
                student = row.get("students") or {}
                subject = row.get("subjects") or {}
                label = (
                    f"{student.get('name', 'Student')} | "
                    f"{subject.get('name', 'Subject')} | "
                    f"{row.get('timestamp', '-')}"
                )
                options[label] = row

            selected_label = st.selectbox(
                "Select student attendance row",
                list(options.keys()),
                key="teacher_override_row",
            )
            selected_row = options[selected_label]
            new_status = st.radio(
                "Set attendance",
                ["Present", "Absent"],
                horizontal=True,
                index=0 if selected_row.get("is_present") else 1,
                key="teacher_override_status",
            )
            reason = st.text_input(
                "Reason",
                value="teacher present/absent correction within audited window",
                key="teacher_override_reason",
            )
            if st.button("Save teacher correction", type="primary"):
                teacher = st.session_state.teacher_data
                updated = update_attendance_override(
                    selected_row["id"],
                    new_status == "Present",
                    "teacher",
                    actor_id=teacher.get("teacher_id"),
                    actor_name=teacher.get("name"),
                    reason=reason,
                )
                if updated:
                    st.success("Attendance correction saved with audit trail.")
                    st.rerun()
                else:
                    st.error("Correction was not saved. The row may be locked or photo-detected.")

    records = get_attendance_for_teacher(teacher_id)

    if not records:
        st.info("No attendance records found.")
        return

    # --- Data Prepare ---
    data = []
    for r in records:
        ts = r.get("timestamp")
        data.append(
            {
                "ts_group": ts.split(".")[0] if ts else None,
                "Date": (
                    datetime.fromisoformat(ts).strftime("%Y-%m-%d") if ts else "N/A"
                ),
                "Time": (
                    datetime.fromisoformat(ts).strftime("%I:%M %p") if ts else "N/A"
                ),
                "Subject": r["subjects"]["name"],
                "Subject Code": r["subjects"]["subject_code"],
                "subject_id": r["subjects"]["subject_id"],
                "Student Name": r["students"]["name"],
                "Email": r["students"].get("email_id"),
                "student_id": r["students"]["student_id"],
                "is_present": bool(r.get("is_present", False)),
                "Status": "✅ Present" if r.get("is_present") else "❌ Absent",
            }
        )

    df = pd.DataFrame(data)

    # --- Subject Filter ---
    subjects = df["Subject"].unique().tolist()
    selected_subject = st.selectbox("📚 Select Subject", ["All Subjects"] + subjects)

    if selected_subject != "All Subjects":
        df = df[df["Subject"] == selected_subject]

    # --- Weekly / Monthly Reports ---
    st.subheader("Download Reports")
    report_col1, report_col2, report_col3 = st.columns([2, 1, 1])
    with report_col1:
        report_period = st.selectbox(
            "Report period",
            ["This Week", "This Month", "All Records"],
        )

    report_df = filter_report_period(df, report_period)
    report_title = f"{report_period} Attendance Report"
    csv_bytes, pdf_bytes = build_attendance_report(report_df, report_title)
    file_prefix = report_period.lower().replace(" ", "_")

    with report_col2:
        st.download_button(
            "Download CSV",
            data=csv_bytes,
            file_name=f"{file_prefix}_attendance_report.csv",
            mime="text/csv",
            width="stretch",
        )
    with report_col3:
        st.download_button(
            "Download PDF",
            data=pdf_bytes,
            file_name=f"{file_prefix}_attendance_report.pdf",
            mime="application/pdf",
            width="stretch",
        )
    st.caption(f"{len(report_df)} row(s) included in this report.")

    # --- Session History ---
    st.subheader("📋 Session History")

    summary = (
        df.groupby(["ts_group", "Date", "Time", "Subject", "Subject Code"])
        .agg(Present=("is_present", "sum"), Total=("is_present", "count"))
        .reset_index()
    )
    summary["Attendance %"] = ((summary["Present"] / summary["Total"]) * 100).round(
        1
    ).astype(str) + "%"
    summary["Stats"] = (
        "✅ " + summary["Present"].astype(str) + " / " + summary["Total"].astype(str)
    )
    summary = summary.sort_values("ts_group", ascending=False).reset_index(drop=True)

    # Summary Table
    st.dataframe(
        summary[["Date", "Time", "Subject", "Subject Code", "Stats", "Attendance %"]],
        hide_index=True,
        use_container_width=True,
    )

    st.write("")

    # --- Session Detail ---
    st.subheader("🔍 Session Detail")
    st.caption("Select any session to see the details ")

    session_options = (
        summary["Date"] + " | " + summary["Time"] + " | " + summary["Subject"]
    ).tolist()
    selected_session_label = st.selectbox(
        "Session Select karo", ["-- Select a Session --"] + session_options
    )

    if selected_session_label != "-- Select a Session --":
        idx = session_options.index(selected_session_label)
        selected_ts = summary.iloc[idx]["ts_group"]
        selected_subj = summary.iloc[idx]["Subject"]

        session_df = df[
            (df["ts_group"] == selected_ts) & (df["Subject"] == selected_subj)
        ]

        st.divider()

        # Metrics
        m1, m2, m3 = st.columns(3)
        present_count = int(session_df["is_present"].sum())
        total_count = len(session_df)
        absent_count = total_count - present_count
        percent = round((present_count / total_count) * 100, 1) if total_count else 0

        m1.metric("Total Students", total_count)
        m2.metric("✅ Present", present_count)
        m3.metric("❌ Absent", absent_count)

        st.metric("Attendance %", f"{percent}%")

        st.write("")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("### ✅ Present Students")
            present_df = session_df[session_df["is_present"] == True][["Student Name"]]
            if present_df.empty:
                st.info("Koi present nahi")
            else:
                st.dataframe(present_df, hide_index=True, use_container_width=True)

        with col2:
            st.markdown("### ❌ Absent Students")
            absent_df = session_df[session_df["is_present"] == False][["Student Name"]]
            if absent_df.empty:
                st.success("All students are present ")
            else:
                st.dataframe(absent_df, hide_index=True, use_container_width=True)

    # --- Overall Student Attendance Summary ---
    st.divider()
    st.subheader("📊 Student-wise Overall Attendance")

    student_summary = (
        df.groupby(["student_id", "Student Name", "Subject"])
        .agg(Total_Classes=("is_present", "count"), Present_Days=("is_present", "sum"))
        .reset_index()
    )
    student_summary["Absent Days"] = (
        student_summary["Total_Classes"] - student_summary["Present_Days"]
    )
    student_summary["Attendance %"] = (
        (student_summary["Present_Days"] / student_summary["Total_Classes"]) * 100
    ).round(1).astype(str) + "%"

    student_summary["⚠️"] = (
        student_summary["Present_Days"] / student_summary["Total_Classes"] * 100 < 75
    ).map({True: "⚠️ Low", False: "✅ Good"})

    st.dataframe(
        student_summary[
            [
                "Student Name",
                "Subject",
                "Total_Classes",
                "Present_Days",
                "Absent Days",
                "Attendance %",
                "⚠️",
            ]
        ],
        hide_index=True,
        use_container_width=True,
    )


# Use: Handles teacher tab student feedback behavior in this module.
# Linked with: teacher_dashboard
def teacher_tab_student_feedback():
    teacher_id = st.session_state.teacher_data["teacher_id"]
    st.header("Student Feedback & Doubts")
    st.caption("Review student questions, doubts, and understanding notes for your subjects.")

    if not feedback_table_available():
        st.warning(
            "Feedback table missing hai. Supabase SQL Editor me "
            "supabase_feedback_migration.sql run karo, phir app refresh karo."
        )
        return

    feedback_rows = get_teacher_feedback(teacher_id)
    if not feedback_rows:
        st.info("No student feedback or doubts yet.")
        return

    subject_names = sorted(
        {
            (row.get("subjects") or {}).get("name", "Subject")
            for row in feedback_rows
        }
    )
    status_filter = st.selectbox("Status", ["All", "Open", "Replied"])
    subject_filter = st.selectbox("Subject", ["All Subjects"] + subject_names)

    rows = feedback_rows
    if status_filter != "All":
        rows = [
            row for row in rows
            if str(row.get("status", "open")).lower() == status_filter.lower()
        ]
    if subject_filter != "All Subjects":
        rows = [
            row for row in rows
            if (row.get("subjects") or {}).get("name", "Subject") == subject_filter
        ]

    open_count = sum(1 for row in feedback_rows if row.get("status", "open") == "open")
    replied_count = sum(1 for row in feedback_rows if row.get("status") == "replied")
    m1, m2, m3 = st.columns(3)
    m1.metric("Total", len(feedback_rows))
    m2.metric("Open", open_count)
    m3.metric("Replied", replied_count)

    for row in rows:
        student = row.get("students") or {}
        subject = row.get("subjects") or {}
        title = (
            f"{student.get('name', 'Student')} | "
            f"{subject.get('name', 'Subject')} | "
            f"{row.get('feedback_type', 'Feedback')} | "
            f"{row.get('status', 'open').title()}"
        )
        with st.expander(title, expanded=row.get("status") == "open"):
            info_rows = [
                {"Field": "Enrollment", "Value": student.get("enrollment_no", "-")},
                {"Field": "Class", "Value": f"{student.get('branch', '-')} | Sem {student.get('semester', '-')} | Sec {student.get('section', '-')}"},
                {"Field": "Subject Code", "Value": subject.get("subject_code", "-")},
                {"Field": "Understanding", "Value": row.get("understanding", "-")},
                {"Field": "Submitted", "Value": str(row.get("created_at", "-")).split(".")[0]},
            ]
            st.dataframe(info_rows, hide_index=True, use_container_width=True)
            st.markdown("**Student Response**")
            st.write(row.get("message", ""))

            if row.get("teacher_reply"):
                st.success(f"Current reply: {row['teacher_reply']}")

            with st.form(f"reply_feedback_{row['id']}"):
                reply_text = st.text_area(
                    "Reply to student",
                    value=row.get("teacher_reply") or "",
                    placeholder="Write a clear answer or guidance for the student.",
                    height=110,
                )
                submitted_reply = st.form_submit_button(
                    "Send Reply",
                    type="primary",
                    use_container_width=True,
                )

            if submitted_reply:
                if not reply_text.strip():
                    st.warning("Please write a reply before sending.")
                else:
                    result = reply_to_subject_feedback(
                        row["id"],
                        teacher_id,
                        reply_text.strip(),
                    )
                    if result["ok"]:
                        st.success("Reply sent to student dashboard.")
                        time.sleep(0.6)
                        st.rerun()
                    else:
                        st.error(result["error"])


# Use: Handles teacher screen login behavior in this module.
# Linked with: teacher_screen
def teacher_screen_login():
    st.markdown(
        """
        <style>
            /* 1. Label Text Color */
            .stTextInput label p {
                color: var(--ss-text) !important; 
                font-weight: 600 !important;
                font-size: 1.1rem !important;
            }
            
            /* 2. Input Box Styling */
            .stTextInput input {
                background: rgba(11, 15, 43, 0.45) !important; 
                color: var(--ss-text) !important; 
                border: 1px solid var(--ss-border) !important; 
                border-radius: 9px !important;
            }
            
            /* 3. Focus / Click Effect */
            .stTextInput input:focus {
                border-color: var(--ss-blue-light) !important; 
                box-shadow: 0 0 0 1px rgba(102, 217, 255, 0.2) !important;
            }
            
            /* Placeholder wapas laane ke liye */
            .stTextInput input::placeholder {
                color: rgba(183, 174, 207, 0.58) !important;
                opacity: 1 !important; /* Ensure visibility */
            }

            /* "Press Enter to apply" gayab karne ke liye */
            div[data-testid="InputInstructions"] {
                display: none !important;
            }
            
            /* 4. Custom Divider */
            hr {
                border: none !important;
                border-top: 1px solid var(--ss-border) !important; 
                margin-top: 2rem !important;
                margin-bottom: 2rem !important;
                opacity: 0.5; 
            }
        </style>
    """,
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns([4, 1], vertical_alignment="center")
    with c1:
        header_dashboard()
    with c2:
        if st.button(
            "Go back to Home",
            type="secondary",
            key="loginbackbtn_2",
            use_container_width=True
        ):
            st.session_state["login_type"] = None
            st.rerun()

    st.markdown(
        "<h2 style='text-align: center;'>Teacher Login Panel</h2>",
        unsafe_allow_html=True,
    )

    st.write("")
    st.write("")

    teacher_username = st.text_input("Enter username", placeholder="Enter username")
    teacher_pass = st.text_input(
        "Enter password", type="password", placeholder="Enter password"
    )

    st.markdown(
        "<hr>",
        unsafe_allow_html=True,
    )

    # 🚀 FIX: Columns hata diye. Ab sirf ek bada 'Login Securely' button hai.
    if st.button(
        "Login Securely",
        type="primary",
        use_container_width=True,
    ):
        teacher_username = teacher_username.strip()
        teacher_pass = teacher_pass.strip()
        if not teacher_username or not teacher_pass:
            st.warning("Please enter both username and password.")
        else:
            try:
                teacher_data = get_teacher_by_username(teacher_username)
            except Exception as exc:
                st.error(
                    "Teacher login abhi complete nahi ho paya because Supabase connection temporarily disconnect ho gaya. "
                    f"Page refresh karke dobara try karein. Detail: {exc}"
                )
                return

            if teacher_data:

                # 🚀 FIX: Seedha password check karo aur login karao (is_verified hata diya)
                if check_pass(teacher_pass, teacher_data["password"]):
                    st.session_state["is_logged_in"] = True
                    st.session_state["user_role"] = "teacher"
                    st.session_state["teacher_data"] = teacher_data

                    st.toast("Welcome back!", icon="👋")
                    import time

                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Invalid password!")
            else:
                st.error("Username not found! Contact Admin if you don't have an account.")

    footer_dashboard()
