import streamlit as st
import io
import os


# Use: Internal helper for make qr png.
# Linked with: share_subject_dialog
def _make_qr_png(join_url):
    try:
        import segno
    except ModuleNotFoundError:
        return None

    out = io.BytesIO()
    qr = segno.make(join_url)
    qr.save(out, kind="png", scale=10, border=1)
    return out.getvalue()


# Use: Handles share subject dialog behavior in this module.
# Linked with: teacher_tab_manage_subjects.share_btn, teacher_tab_take_attendance
@st.dialog("Class Details")
def share_subject_dialog(subject_name, subject_code):
    app_domain = os.environ.get(
        "TRUEPRESENCE_APP_URL",
        os.environ.get("SIKHSHASATHI_APP_URL", "http://localhost:8501"),
    )
    join_url = f"{app_domain}/?join-code={subject_code}"

    st.header(subject_name)

    qr_png = _make_qr_png(join_url)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Subject Code")
        st.code(join_url, language="text")
        st.code(subject_code, language="text")
        st.info("Students are assigned automatically from their registered class details.")

    with col2:
        st.markdown("### QR Code")
        if qr_png:
            st.image(qr_png, caption="Subject details QR code")
        else:
            st.warning("QR generation needs the `segno` package. The join link above is ready to use.")
