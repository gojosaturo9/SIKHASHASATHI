import streamlit as st

def style_background_home():
    st.markdown("""
        <style>
            .stApp {
                background: #5865F2 !important;
                min-height: 100vh !important; /* height ko min-height kiya */
                overflow-y: auto !important; /* hidden ko auto kiya taaki scroll ho sake */
            }
            .stApp div[data-testid="stColumn"]{
                background-color:#E0E3FF !important;
                padding: 1rem 2rem !important; 
                border-radius: 3rem !important; 
                text-align: center;
            }
        </style>
        """, unsafe_allow_html=True)

def style_background_dashboard():
    st.markdown("""
        <style>
            .stApp, [data-testid="stAppViewContainer"] {
                background-color:#E0E3FF !important;
            }
            .stApp {
                overflow-y: auto !important; 
                height: auto !important;
            }
        </style>
    """, unsafe_allow_html=True)

def style_base_layout():
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Climate+Crisis:YEAR@1979&display=swap');
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@100..900&display=swap');
        
         /* Hide Top Bar of streamlit */
            header, footer, #MainMenu {
                visibility: hidden;
                height: 0;
            }
                
            .block-container {
                padding-top: 2rem !important; /* Thoda top padding add kiya taaki content upar na dabe */
                padding-bottom: 5rem !important; /* Scroll karne ke baad niche jagah mile */
                min-height: 100vh !important; /* YAHAN MAIN FIX HAI */
                display: flex;
                flex-direction: column;
                justify-content: flex-start; /* YAHAN MAIN FIX HAI: center ki jagah flex-start lagaya */
            }

            h1 {
                font-family: 'Climate Crisis', sans-serif !important;
                font-size: 3.5rem !important;
                line-height:1.1 !important;
                margin-bottom:0rem !important;
            }

            h2 {
                font-family: 'Climate Crisis', sans-serif !important;
                font-size: 2rem !important;
                line-height:0.9 !important;
                margin-bottom:0rem !important;
            }
                
            h3, h4, p {
                font-family: 'Outfit', sans-serif;    
            }

            button{
                border-radius: 1.5rem !important;
                background-color: #5865F2 !important;
                color: white !important;
                padding: 10px 20px !important;
                border: none !important;
                transition: transform 0.25s ease-in-out !important;
                }

            button[kind="secondary"]{
                border-radius: 1.5rem !important;
                background-color: #EB459E !important;
                color: white !important;
                padding: 10px 20px !important;
                border: none !important;
                transition: transform 0.25s ease-in-out !important;
                }

            button[kind="tertiary"]{
                border-radius: 1.5rem !important;
                background-color: black !important;
                color: white !important;
                padding: 10px 20px !important;
                border: none !important;
                transition: transform 0.25s ease-in-out !important;
                }

            button:hover{
                transform :scale(1.05)
            }
        </style>  
        """
    ,unsafe_allow_html=True)