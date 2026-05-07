from supabase import create_client, Client
import streamlit as st

from src.utils.env_loader import load_env_file
from src.utils.secrets import require_secret

load_env_file()

supabase_url = require_secret("SUPABASE_URL")
supabase_key = require_secret("SUPABASE_KEY")

try:
    supabase: Client = create_client(supabase_url, supabase_key)
except Exception as exc:
    st.error("Supabase client could not be created. Check SUPABASE_URL and SUPABASE_KEY.")
    st.exception(exc)
    st.stop()
