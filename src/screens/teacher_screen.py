import streamlit as st
from src.ui.base_layout import style_background_dashboard,style_base_layout
from src.components.header import header_dashboard
from src.components.footer import footer_dashboard

def teacher_screen():
    style_base_layout()
    style_background_dashboard()
    
    
    if 'teacher_login_type' not in st.session_state or st.session_state.teacher_login_type=="login":
        teacher_screen_login()
    elif st.session_state.teacher_login_type == "register":
        teacher_screen_register()
    
    

def teacher_screen_login():
    st.markdown("""
        <style>
            /* 1. Label Text Color */
            .stTextInput label p {
                color: #2D3436 !important; 
                font-weight: 600 !important;
                font-size: 1.1rem !important;
            }
            
            /* 2. Input Box Styling */
            .stTextInput input {
                background-color: #FFFFFF !important; 
                color: #000000 !important; 
                border: 2px solid #5865F2 !important; 
                border-radius: 0.8rem !important;
            }
            
            /* 3. Focus / Click Effect */
            .stTextInput input:focus {
                border-color: #EB459E !important; 
                box-shadow: 0 0 5px rgba(235, 69, 158, 0.5) !important;
            }
            
            /* 👇 NAYA FIX 1: Placeholder wapas laane ke liye 👇 */
            .stTextInput input::placeholder {
                color: #A0AAB2 !important; /* Halka grey color */
                opacity: 1 !important; /* Ensure visibility */
            }

            /* 👇 NAYA FIX 2: "Press Enter to apply" gayab karne ke liye 👇 */
            div[data-testid="InputInstructions"] {
                display: none !important;
            }
            
            /* 4. Custom Divider */
            hr {
                border: none !important;
                border-top: 2px solid #5865F2 !important; 
                margin-top: 2rem !important;
                margin-bottom: 2rem !important;
                opacity: 0.5; 
            }
        </style>
    """, unsafe_allow_html=True)

    # --- Baki ka code same rahega ---
    c1, c2 = st.columns(2, vertical_alignment='center', gap='xxlarge')
    with c1:
        header_dashboard()
    with c2:
        if st.button("Go back to Home", type='secondary', key='loginbackbtn', shortcut="control+backspace"):
            st.session_state['login_type'] = None
            st.rerun()
    
    st.markdown("<h2 style='text-align: center; color:black;'>Login using password</h2>", unsafe_allow_html=True)
    
    st.write("")
    st.write("")

    teacher_username = st.text_input("Enter username", placeholder='Enter username')
    teacher_pass = st.text_input("Enter password", type='password', placeholder="Enter password")
    
    st.markdown("<hr style='border: 2px solid #5865F2; border-radius: 5px; opacity: 0.5;'>", unsafe_allow_html=True)
    
    
    btnc1, btnc2 = st.columns(2)
    with btnc1:
        st.button('Login', icon=':material/passkey:', shortcut='control+enter', width='stretch')
        
    
    with btnc2:
        if st.button('Register Instead', type="primary", icon=':material/passkey:', width='stretch'):
            st.session_state.teacher_login_type = 'register'
    
    
    
    footer_dashboard()
    




def teacher_screen_register():
    st.markdown("""
        <style>
            /* 1. Label Text Color */
            .stTextInput label p {
                color: #2D3436 !important; 
                font-weight: 600 !important;
                font-size: 1.1rem !important;
            }
            
            /* 2. Input Box Styling */
            .stTextInput input {
                background-color: #FFFFFF !important; 
                color: #000000 !important; 
                border: 2px solid #5865F2 !important; 
                border-radius: 0.8rem !important;
            }
            
            /* 3. Focus / Click Effect */
            .stTextInput input:focus {
                border-color: #EB459E !important; 
                box-shadow: 0 0 5px rgba(235, 69, 158, 0.5) !important;
            }
            
            /* 👇 NAYA FIX 1: Placeholder wapas laane ke liye 👇 */
            .stTextInput input::placeholder {
                color: #A0AAB2 !important; /* Halka grey color */
                opacity: 1 !important; /* Ensure visibility */
            }

            /* 👇 NAYA FIX 2: "Press Enter to apply" gayab karne ke liye 👇 */
            div[data-testid="InputInstructions"] {
                display: none !important;
            }
            
            /* 4. Custom Divider */
            hr {
                border: none !important;
                border-top: 2px solid #5865F2 !important; 
                margin-top: 2rem !important;
                margin-bottom: 2rem !important;
                opacity: 0.5; 
            }
        </style>
    """, unsafe_allow_html=True)
    c1, c2 = st.columns(2, vertical_alignment='center', gap='xxlarge')
    with c1:
        header_dashboard()
    with c2:
        if st.button("Go back to Home", type='secondary', key='loginbackbtn', shortcut="control+backspace"):
            st.session_state['login_type'] = None
            st.rerun()

    st.markdown("<h2 style='text-align: center; color:black;'>Register your teacher profile</h2>", unsafe_allow_html=True)

    
    teacher_username = st.text_input("Enter username", placeholder='Enter username here')

    teacher_name = st.text_input("Enter name", placeholder='Enter your name here')

    teacher_pass = st.text_input("Enter password", type='password', placeholder="Enter password")

    teacher_pass_confirm = st.text_input("Confirm your password", type='password', placeholder="Enter password")

    st.divider()

    btnc1, btnc2 = st.columns(2)

    with btnc1:
        st.button('Register now', icon=':material/passkey:', shortcut='control+enter', width='stretch')
        

    with btnc2:
        if st.button('Login Instead', type="primary", icon=':material/passkey:', width='stretch'):
            st.session_state.teacher_login_type = 'login'

    footer_dashboard()