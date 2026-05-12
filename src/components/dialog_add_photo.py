import streamlit as st
from PIL import Image

from src.utils.zero_trust import extract_photo_metadata


# Use: Handles add photos dialog behavior in this module.
# Linked with: teacher_tab_take_attendance
@st.dialog("Capture or upload photos")
def add_photos_dialog():
    st.write("Capture a fresh classroom photo with the camera. Anti-spoofing runs before face recognition.")

    if "attendance_photo_meta" not in st.session_state:
        st.session_state.attendance_photo_meta = []

    cam_photo = st.camera_input("Take snapshot", key="dialog_cam")
    if cam_photo:
        image = Image.open(cam_photo).convert("RGB")
        st.session_state.attendance_images.append(image)
        st.session_state.attendance_photo_meta.append(
            extract_photo_metadata(image, "camera", "camera_capture.jpg")
        )
        st.toast("Photo captured")
        st.rerun()

    st.divider()
    if st.button("Done", type="primary", width="stretch"):
        st.rerun()
