import streamlit as st

from src.ui.base_layout import style_background_dashboard, style_base_layout

from src.components.header import header_dashboard
from src.components.footer import footer_dashboard

from PIL import Image
import numpy as np

def student_screen():
    style_background_dashboard()
    style_base_layout()
    
    c1, c2 = st.columns(2, vertical_alignment='center', gap='xxlarge')
    with c1:
        header_dashboard()
    with c2:
        if st.button("Go back to Home", type='secondary', key='loginbackbtn', shortcut="control+backspace"):
            st.session_state['login_type'] = None
            st.rerun()
            
    
    st.header('Login using FaceID', text_alignment='center')
    
    st.markdown("""
    <style>
        [data-testid="stCameraInputButton"] + div video,
        [data-testid="stCameraInput"] video {
            transform: scaleX(-1) !important;
        }
    </style>
    """, unsafe_allow_html=True)

    photo_source = st.camera_input("Position your face in the center")

    if photo_source:
        img = np.array(Image.open(photo_source))
    
    footer_dashboard()