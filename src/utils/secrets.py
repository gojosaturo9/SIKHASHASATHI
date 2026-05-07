import os

import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError

from src.utils.env_loader import load_env_file


def get_secret(name, default=None):
    load_env_file()

    try:
        value = st.secrets.get(name, None)
    except (FileNotFoundError, KeyError, StreamlitSecretNotFoundError):
        value = None

    if value in (None, ""):
        value = os.getenv(name)

    return value if value not in (None, "") else default


def require_secret(name):
    value = get_secret(name)
    if value:
        return value

    st.error(f"Missing required secret: {name}")
    st.info(
        "Create `.streamlit/secrets.toml` in the project root and add your Supabase credentials."
    )
    st.code(
        'SUPABASE_URL = "https://your-project.supabase.co"\n'
        'SUPABASE_KEY = "your-supabase-anon-or-service-key"\n'
        'ADMIN_PASSWORD = "your-admin-password"\n'
        '# Optional for LLM chatbot\n'
        'OPENAI_API_KEY = "your-openai-key"\n'
        'OPENAI_MODEL = "gpt-4o-mini"\n'
        '# Optional for email sending\n'
        'SENDER_EMAIL = "your-gmail@gmail.com"\n'
        'SENDER_PASSWORD = "your-gmail-app-password"',
        language="toml",
    )
    st.stop()
